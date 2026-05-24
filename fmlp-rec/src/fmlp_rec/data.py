"""Datasets + DataModule for FMLP-Rec on Beauty: left-pad sequences, dynamic train neg, cached eval 99-neg."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Sequence

import lightning.pytorch as pl
import torch
from torch.utils.data import DataLoader, Dataset


def pad_and_truncate(seq: Sequence[int], max_len: int) -> list[int]:
    seq = list(seq)[-max_len:]
    return [0] * (max_len - len(seq)) + seq


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


class FMLPTrainDataset(Dataset):
    def __init__(self, records: list[dict], num_items: int, max_seq_len: int, seed: int = 42):
        self.instances: list[tuple[list[int], int]] = []
        for rec in records:
            seq = rec["train_seq"]
            for t in range(1, len(seq)):
                self.instances.append((seq[:t], seq[t]))
        self.num_items = num_items
        self.max_seq_len = max_seq_len
        self.rng = random.Random(seed)

    def __len__(self) -> int:
        return len(self.instances)

    def __getitem__(self, idx: int) -> dict:
        history, target = self.instances[idx]
        input_seq = pad_and_truncate(history, self.max_seq_len)
        neg = self.rng.randint(1, self.num_items)
        while neg == target:
            neg = self.rng.randint(1, self.num_items)
        return {
            "input_seq": torch.tensor(input_seq, dtype=torch.long),
            "pos": torch.tensor(target, dtype=torch.long),
            "neg": torch.tensor(neg, dtype=torch.long),
        }


class FMLPEvalDataset(Dataset):
    def __init__(self, records: list[dict], max_seq_len: int):
        self.records = records
        self.max_seq_len = max_seq_len

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> dict:
        rec = self.records[idx]
        input_seq = pad_and_truncate(rec["history"], self.max_seq_len)
        candidates = [rec["target"]] + rec["negatives"]
        return {
            "input_seq": torch.tensor(input_seq, dtype=torch.long),
            "candidates": torch.tensor(candidates, dtype=torch.long),
        }


class FMLPDataModule(pl.LightningDataModule):
    def __init__(
        self,
        processed_dir: str | Path,
        max_seq_len: int,
        batch_size: int,
        num_workers: int = 0,
        seed: int = 42,
    ):
        super().__init__()
        self.processed_dir = Path(processed_dir)
        self.max_seq_len = max_seq_len
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.seed = seed

    def setup(self, stage: str | None = None):
        meta = json.loads((self.processed_dir / "meta.json").read_text())
        self.num_items = meta["num_items"]
        self.train_dataset = FMLPTrainDataset(
            load_jsonl(self.processed_dir / "train.jsonl"),
            self.num_items,
            self.max_seq_len,
            seed=self.seed,
        )
        self.val_dataset = FMLPEvalDataset(
            load_jsonl(self.processed_dir / "val.jsonl"),
            self.max_seq_len,
        )
        self.test_dataset = FMLPEvalDataset(
            load_jsonl(self.processed_dir / "test.jsonl"),
            self.max_seq_len,
        )

    def train_dataloader(self) -> DataLoader:
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            num_workers=self.num_workers,
        )

    def val_dataloader(self) -> DataLoader:
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
        )

    def test_dataloader(self) -> DataLoader:
        return DataLoader(
            self.test_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=self.num_workers,
        )