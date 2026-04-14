"""
Training script for GRU4REC on ml-100k.
Usage:
    python train_model.py --epochs 20 --batch_size 256 --embed_dim 128
"""

from __future__ import absolute_import, division, print_function

import os
import math
import argparse
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split

from models.GRU4REC import GRU4REC

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = './datasets/ml-100k/'
CKPT_DIR   = './checkpoints/'
LOG_FILE   = './checkpoints/train_log.txt'


# ── Data Loader ───────────────────────────────────────────────────────────────
class SequenceDataLoader:
    """Mini-batch loader for sequence data stored as a DataFrame."""

    def __init__(self, data: pd.DataFrame, batch_size: int):
        self.data          = data.reset_index(drop=True)
        self.num_sequences = len(data)
        self.batch_size    = batch_size
        self.reset()

    def reset(self):
        self._start_idx = 0
        self._has_next  = True

    def has_next(self):
        return self._has_next

    def get_batch(self):
        if not self._has_next:
            return None

        end_idx = min(self._start_idx + self.batch_size, self.num_sequences)
        rows    = self.data.iloc[self._start_idx:end_idx]

        seqs    = rows['sequence'].tolist()
        lengths = rows['length'].tolist()
        targets = rows['target'].tolist()
        users   = rows['user'].tolist()
        seq_ids = rows['sequence_id'].tolist()

        # pad sequences to the longest one in this batch
        max_len          = max(lengths)
        padded           = torch.zeros(len(seqs), max_len, dtype=torch.long)
        for i, (seq, l) in enumerate(zip(seqs, lengths)):
            padded[i, :l] = torch.LongTensor(seq)

        self._has_next  = end_idx < self.num_sequences
        self._start_idx = end_idx

        # shape: (batch, max_len)
        return (padded,
                lengths,
                torch.tensor(targets, dtype=torch.long),
                users,
                seq_ids)


# ── Metrics ───────────────────────────────────────────────────────────────────
def hit_ratio(topk_preds: torch.Tensor, target: torch.Tensor) -> int:
    return int(target in topk_preds)

def ndcg(topk_preds: torch.Tensor, target: torch.Tensor) -> float:
    for rank, pred in enumerate(topk_preds):
        if pred == target:
            return math.log(2) / math.log(rank + 2)
    return 0.0


# ── Evaluate ──────────────────────────────────────────────────────────────────
def evaluate(model: nn.Module,
             dataloader: SequenceDataLoader,
             device: torch.device,
             ks=(5, 10, 20)) -> dict:
    model.eval()
    results = {f'hit@{k}': [] for k in ks}
    results.update({f'ndcg@{k}': [] for k in ks})

    with torch.no_grad():
        dataloader.reset()
        while dataloader.has_next():
            batch = dataloader.get_batch()
            seqs, lengths, targets, _, _ = batch
            seqs = seqs.to(device)

            _, scores = model(seqs, lengths)   # (batch, n_items+1)

            for k in ks:
                topk = torch.topk(scores, k, dim=1).indices  # (batch, k)
                for i, target in enumerate(targets):
                    results[f'hit@{k}'].append(hit_ratio(topk[i].cpu(), target))
                    results[f'ndcg@{k}'].append(ndcg(topk[i].cpu(), target))

    return {key: float(np.mean(vals)) * 100 for key, vals in results.items()}


# ── Train ─────────────────────────────────────────────────────────────────────
def train(args):
    os.makedirs(CKPT_DIR,  exist_ok=True)

    # ── load data ─────────────────────────────────────────────────────────────
    def load_seq_csv(path):
        df = pd.read_csv(path)
        df['sequence'] = df['sequence'].apply(eval)
        df['length']   = df['sequence'].apply(len)
        df.sort_values('length', ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
        df['sequence_id'] = np.arange(len(df))
        return df

    train_df = load_seq_csv(DATA_DIR + 'train_sequence.csv')
    test_df  = load_seq_csv(DATA_DIR + 'test_sequence.csv')

    n_items = len(np.load(DATA_DIR + 'item_dict.npy', allow_pickle=True).item())
    print(f"n_items={n_items} | train={len(train_df)} | test={len(test_df)}")

    # ── model ─────────────────────────────────────────────────────────────────
    model = GRU4REC(
        embedding_dim = args.embed_dim,
        hidden_dim    = args.embed_dim,
        n_items       = n_items,
    ).to(args.device)

    # ── split train → train + val ─────────────────────────────────────────────
    tr, val = train_test_split(train_df, test_size=0.1, random_state=args.seed)
    train_loader = SequenceDataLoader(tr,      args.batch_size)
    val_loader   = SequenceDataLoader(val,     args.batch_size)
    test_loader  = SequenceDataLoader(test_df, args.batch_size)

    optimizer  = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion  = nn.CrossEntropyLoss()
    total_steps = args.epochs * (len(tr) // args.batch_size + 1)

    best_hit5 = 0.0
    step      = 0

    log_fh = open(LOG_FILE, 'w')
    def log(msg):
        print(msg)
        log_fh.write(msg + '\n')
        log_fh.flush()

    log(str(args))

    # ── training loop ─────────────────────────────────────────────────────────
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loader.reset()
        epoch_losses = []

        while train_loader.has_next():
            seqs, lengths, targets, _, _ = train_loader.get_batch()
            seqs    = seqs.to(args.device)
            targets = targets.to(args.device)

            optimizer.zero_grad()
            _, scores = model(seqs, lengths)
            loss = criterion(scores, targets)
            loss.backward()
            optimizer.step()

            # learning-rate decay
            step += 1
            lr = args.lr * max(1e-4, 1.0 - step / total_steps)
            for pg in optimizer.param_groups:
                pg['lr'] = lr

            epoch_losses.append(loss.item())

        avg_loss = np.mean(epoch_losses)

        # ── validate ──────────────────────────────────────────────────────────
        val_metrics = evaluate(model, val_loader, args.device)
        log(f"Epoch {epoch:3d} | loss={avg_loss:.4f} | "
            f"val hit@5={val_metrics['hit@5']:.2f}%  "
            f"ndcg@5={val_metrics['ndcg@5']:.2f}%  "
            f"hit@10={val_metrics['hit@10']:.2f}%")

        if val_metrics['hit@5'] > best_hit5:
            best_hit5 = val_metrics['hit@5']
            ckpt = CKPT_DIR + 'gru4rec_best.ckpt'
            torch.save(model.state_dict(), ckpt)
            log(f"  ✓ Best model saved → {ckpt}")

    # ── final test ────────────────────────────────────────────────────────────
    log("\n── Final Test ──────────────────────────────────────────")
    model.load_state_dict(torch.load(CKPT_DIR + 'gru4rec_best.ckpt'))
    test_metrics = evaluate(model, test_loader, args.device)
    for key, val in sorted(test_metrics.items()):
        log(f"  {key}: {val:.2f}%")

    log_fh.close()


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Train GRU4REC on ml-100k')
    parser.add_argument('--seed',       type=int,   default=42)
    parser.add_argument('--epochs',     type=int,   default=30)
    parser.add_argument('--batch_size', type=int,   default=256)
    parser.add_argument('--embed_dim',  type=int,   default=128,
                        help='Embedding & hidden dimension')
    parser.add_argument('--lr',         type=float, default=1e-3)
    parser.add_argument('--gpu',        type=str,   default='0')
    args = parser.parse_args()

    os.environ['CUDA_VISIBLE_DEVICES'] = args.gpu
    args.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {args.device}")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    train(args)


if __name__ == '__main__':
    main()
