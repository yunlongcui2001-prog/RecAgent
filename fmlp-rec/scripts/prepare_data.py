"""Preprocess Amazon Beauty 5-core: build sequences, leave-one-out split, cache 99-neg eval set."""
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--raw", type=Path, default=Path("data/raw/reviews_Beauty_5.json.gz"))
    p.add_argument("--out-dir", type=Path, default=Path("data/processed/beauty"))
    p.add_argument("--num-neg", type=int, default=99)
    p.add_argument("--min-seq-len", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def load_interactions(raw_path: Path) -> list[tuple[str, str, int]]:
    out = []
    with gzip.open(raw_path, "rt") as f:
        for line in f:
            rec = json.loads(line)
            out.append((rec["reviewerID"], rec["asin"], int(rec["unixReviewTime"])))
    return out


def build_sequences(interactions, min_seq_len: int):
    user_to_items = defaultdict(list)
    for u, i, t in interactions:
        user_to_items[u].append((t, i))

    sequences = {}
    for u, items in user_to_items.items():
        if len(items) < min_seq_len:
            continue
        items.sort(key=lambda x: x[0])
        sequences[u] = [i for _, i in items]
    return sequences


def remap_ids(sequences):
    items = sorted({i for seq in sequences.values() for i in seq})
    item_map = {asin: idx + 1 for idx, asin in enumerate(items)}
    users = sorted(sequences.keys())
    user_map = {u: idx for idx, u in enumerate(users)}
    remapped = {user_map[u]: [item_map[i] for i in seq] for u, seq in sequences.items()}
    return remapped, item_map, user_map


def sample_negatives(rng: np.random.Generator, num_items: int, excluded: set[int], n: int) -> list[int]:
    negs: list[int] = []
    seen = set(excluded)
    while len(negs) < n:
        cand = int(rng.integers(1, num_items + 1))
        if cand in seen:
            continue
        seen.add(cand)
        negs.append(cand)
    return negs


def leave_one_out_split(sequences, num_items: int, num_neg: int, seed: int):
    rng = np.random.default_rng(seed)
    train, val, test = [], [], []
    for u, seq in sequences.items():
        train_seq = seq[:-2]
        val_target = seq[-2]
        test_target = seq[-1]
        all_interacted = set(seq)
        val_negs = sample_negatives(rng, num_items, all_interacted, num_neg)
        test_negs = sample_negatives(rng, num_items, all_interacted, num_neg)
        train.append({"user": u, "train_seq": train_seq})
        val.append({"user": u, "history": train_seq, "target": val_target, "negatives": val_negs})
        test.append({"user": u, "history": seq[:-1], "target": test_target, "negatives": test_negs})
    return train, val, test


def write_jsonl(records, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def main():
    args = parse_args()

    print(f"[1/5] loading {args.raw}")
    interactions = load_interactions(args.raw)
    print(f"      {len(interactions):,} interactions")

    print(f"[2/5] grouping by user, filtering seq_len >= {args.min_seq_len}")
    sequences = build_sequences(interactions, args.min_seq_len)
    print(f"      {len(sequences):,} users after filtering")

    print("[3/5] remapping ids (item ids start at 1; 0 reserved for padding)")
    sequences, item_map, user_map = remap_ids(sequences)
    num_items = len(item_map)
    num_users = len(user_map)
    print(f"      {num_users:,} users, {num_items:,} items")

    print(f"[4/5] leave-one-out split + sampling {args.num_neg} negatives per user")
    train, val, test = leave_one_out_split(sequences, num_items, args.num_neg, args.seed)

    print(f"[5/5] writing outputs to {args.out_dir}")
    out = args.out_dir
    write_jsonl(train, out / "train.jsonl")
    write_jsonl(val, out / "val.jsonl")
    write_jsonl(test, out / "test.jsonl")
    with open(out / "item_map.json", "w") as f:
        json.dump(item_map, f)
    with open(out / "meta.json", "w") as f:
        json.dump(
            {
                "num_users": num_users,
                "num_items": num_items,
                "num_neg": args.num_neg,
                "min_seq_len": args.min_seq_len,
                "seed": args.seed,
                "source": str(args.raw),
            },
            f,
            indent=2,
        )

    print("done.")


if __name__ == "__main__":
    main()