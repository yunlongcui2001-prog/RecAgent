"""FMLPRec: ItemEmbed + PosEmbed → ×L FilterBlock → dot-product prediction. Paper §4.1."""
from __future__ import annotations

import torch
from torch import nn

from fmlp_rec.filter_block import FilterBlock


class FMLPRec(nn.Module):
    def __init__(
        self,
        num_items: int,
        embed_dim: int,
        max_seq_len: int,
        num_blocks: int,
        ffn_hidden_dim: int,
        dropout: float,
    ):
        super().__init__()
        self.item_embed = nn.Embedding(num_items + 1, embed_dim, padding_idx=0)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.input_dropout = nn.Dropout(dropout)
        self.input_layernorm = nn.LayerNorm(embed_dim)
        self.blocks = nn.ModuleList(
            [FilterBlock(max_seq_len, embed_dim, ffn_hidden_dim, dropout) for _ in range(num_blocks)]
        )
        self.max_seq_len = max_seq_len

    def encode(self, seq: torch.Tensor) -> torch.Tensor:
        b, n = seq.shape
        positions = torch.arange(n, device=seq.device).unsqueeze(0).expand(b, n)
        x = self.item_embed(seq) + self.pos_embed(positions)
        x = self.input_dropout(self.input_layernorm(x))
        for block in self.blocks:
            x = block(x)
        return x

    def score(self, seq: torch.Tensor, items: torch.Tensor) -> torch.Tensor:
        h_last = self.encode(seq)[:, -1, :]
        item_emb = self.item_embed(items)
        return (h_last.unsqueeze(1) * item_emb).sum(dim=-1)