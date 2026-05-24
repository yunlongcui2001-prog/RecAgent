"""Training entry: parse --config, build DataModule + LitModule, fit with Lightning Trainer."""
from __future__ import annotations

import argparse
from pathlib import Path

import lightning.pytorch as pl
import yaml
from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint

from fmlp_rec.data import FMLPDataModule
from fmlp_rec.lit_module import FMLPRecLit


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("configs/beauty_default.yaml"))
    p.add_argument("--max-epochs", type=int, default=None, help="override config max_epochs (for smoke test)")
    p.add_argument("--limit-train-batches", type=float, default=None, help="for smoke test, e.g. 0.05")
    return p.parse_args()


def main():
    args = parse_args()
    cfg = yaml.safe_load(args.config.read_text())

    pl.seed_everything(cfg["training"]["seed"])

    dm = FMLPDataModule(
        processed_dir=cfg["dataset"]["processed_dir"],
        max_seq_len=cfg["dataset"]["max_seq_len"],
        batch_size=cfg["training"]["batch_size"],
        seed=cfg["training"]["seed"],
    )
    dm.setup()

    lit = FMLPRecLit(
        num_items=dm.num_items,
        embed_dim=cfg["model"]["embed_dim"],
        max_seq_len=cfg["dataset"]["max_seq_len"],
        num_blocks=cfg["model"]["num_blocks"],
        ffn_hidden_dim=cfg["model"]["ffn_hidden_dim"],
        dropout=cfg["model"]["dropout"],
        learning_rate=cfg["training"]["learning_rate"],
        topk=cfg["eval"]["topk"],
    )

    callbacks = [
        EarlyStopping(
            monitor=cfg["training"]["early_stop_metric"],
            mode=cfg["training"]["early_stop_mode"],
            patience=cfg["training"]["early_stop_patience"],
        ),
        ModelCheckpoint(
            monitor=cfg["training"]["early_stop_metric"],
            mode=cfg["training"]["early_stop_mode"],
            save_top_k=1,
            filename="best-{epoch}-{val_mrr:.4f}",
        ),
    ]

    trainer = pl.Trainer(
        max_epochs=args.max_epochs or cfg["training"]["max_epochs"],
        limit_train_batches=args.limit_train_batches or 1.0,
        callbacks=callbacks,
        accelerator="cpu",
    )

    trainer.fit(lit, dm)
    trainer.test(lit, dm, ckpt_path="best")


if __name__ == "__main__":
    main()