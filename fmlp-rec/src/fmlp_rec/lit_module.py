"""FMLPRecLit: LightningModule wiring model + BPR loss + AdamW + 99-neg eval metrics + early stop on val_mrr.
   Plus IntermediateTestCallback for mid-training test-set probing (catches over-fitting collapse early)."""
from __future__ import annotations

import lightning.pytorch as pl
import torch

from fmlp_rec.losses import bpr_loss
from fmlp_rec.metrics import compute_ranks, hit_rate_at_k, mrr, ndcg_at_k
from fmlp_rec.model import FMLPRec


class IntermediateTestCallback(pl.Callback):
    """每 N 个 epoch 在 val 结束后跑一次 test_dataloader，log test_mid_* 指标。
       用途：捕捉 test 集崩盘（早期 over-fitting 信号），不影响 best ckpt 选择。"""

    def __init__(self, every_n_epochs: int = 20):
        super().__init__()
        self.every_n_epochs = every_n_epochs

    def on_validation_epoch_end(self, trainer, pl_module):
        if trainer.sanity_checking:
            return
        if (trainer.current_epoch + 1) % self.every_n_epochs != 0:
            return
        test_dl = trainer.datamodule.test_dataloader()
        ranks_list = []
        was_training = pl_module.training
        pl_module.eval()
        with torch.no_grad():
            for batch in test_dl:
                batch = {k: v.to(pl_module.device) for k, v in batch.items()}
                ranks_list.append(pl_module._batch_ranks(batch))
        if was_training:
            pl_module.train()
        ranks = torch.cat(ranks_list)
        for k in pl_module.topk:
            pl_module.log(f"test_mid_hr{k}", hit_rate_at_k(ranks, k), prog_bar=(k == 10))
            pl_module.log(f"test_mid_ndcg{k}", ndcg_at_k(ranks, k), prog_bar=False)
        pl_module.log("test_mid_mrr", mrr(ranks), prog_bar=True)


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
        weight_decay: float = 1e-4,
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
        return torch.optim.AdamW(
            self.parameters(),
            lr=self.hparams.learning_rate,
            weight_decay=self.hparams.weight_decay,
        )