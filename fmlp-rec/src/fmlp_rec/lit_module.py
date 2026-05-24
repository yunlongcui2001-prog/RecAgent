"""FMLPRecLit: LightningModule wiring model + BPR loss + Adam + 99-neg eval metrics + early stop on val_mrr."""
from __future__ import annotations

import lightning.pytorch as pl
import torch

from fmlp_rec.losses import bpr_loss
from fmlp_rec.metrics import compute_ranks, hit_rate_at_k, mrr, ndcg_at_k
from fmlp_rec.model import FMLPRec


class FMLPRecLit(pl.LightningModule):
    def __init__(
        self,
        num_items: int,
        embed_dim: int,
        max_seq_len: int,
        num_blocks: int,
        ffn_hidden_dim: int,
        dropout: float,
        learning_rate: float,
        topk: list[int],
    ):
        super().__init__()
        self.save_hyperparameters()
        self.model = FMLPRec(num_items, embed_dim, max_seq_len, num_blocks, ffn_hidden_dim, dropout)
        self.topk = topk
        self._val_ranks: list[torch.Tensor] = []
        self._test_ranks: list[torch.Tensor] = []

    def training_step(self, batch, batch_idx):
        seq = batch["input_seq"]
        items = torch.stack([batch["pos"], batch["neg"]], dim=-1)
        scores = self.model.score(seq, items)
        loss = bpr_loss(scores[:, 0], scores[:, 1])
        self.log("train_loss", loss, prog_bar=True)
        return loss

    def validation_step(self, batch, batch_idx):
        self._val_ranks.append(self._batch_ranks(batch))

    def test_step(self, batch, batch_idx):
        self._test_ranks.append(self._batch_ranks(batch))

    def _batch_ranks(self, batch) -> torch.Tensor:
        scores = self.model.score(batch["input_seq"], batch["candidates"])
        return compute_ranks(scores[:, 0], scores[:, 1:])

    def on_validation_epoch_end(self):
        self._log_metrics(torch.cat(self._val_ranks), prefix="val")
        self._val_ranks.clear()

    def on_test_epoch_end(self):
        self._log_metrics(torch.cat(self._test_ranks), prefix="test")
        self._test_ranks.clear()

    def _log_metrics(self, ranks: torch.Tensor, prefix: str):
        for k in self.topk:
            self.log(f"{prefix}_hr{k}", hit_rate_at_k(ranks, k), prog_bar=(k == 10))
            self.log(f"{prefix}_ndcg{k}", ndcg_at_k(ranks, k), prog_bar=(k == 10))
        self.log(f"{prefix}_mrr", mrr(ranks), prog_bar=True)

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.hparams.learning_rate)