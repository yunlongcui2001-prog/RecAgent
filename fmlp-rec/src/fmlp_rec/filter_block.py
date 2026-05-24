"""Learnable filter block: FFT → W⊙X → iFFT → skip/LN → FFN → skip/LN. Paper §4.1.2, Eq.4-8."""
from __future__ import annotations

import torch
from torch import nn


class FilterLayer(nn.Module):
    def __init__(self, seq_len: int, embed_dim: int, dropout: float):
        super().__init__()
        freq_bins = seq_len // 2 + 1
        self.W = nn.Parameter(torch.randn(freq_bins, embed_dim, dtype=torch.complex64) * 0.02)
        self.dropout = nn.Dropout(dropout)
        self.layernorm = nn.LayerNorm(embed_dim)
        self._seq_len = seq_len

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        X = torch.fft.rfft(x, dim=-2)
        Y = self.W * X
        y = torch.fft.irfft(Y, n=self._seq_len, dim=-2)
        return self.layernorm(x + self.dropout(y))


class FilterBlock(nn.Module):
    def __init__(self, seq_len: int, embed_dim: int, ffn_hidden_dim: int, dropout: float):
        super().__init__()
        self.filter_layer = FilterLayer(seq_len, embed_dim, dropout)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, ffn_hidden_dim),
            nn.ReLU(),
            nn.Linear(ffn_hidden_dim, embed_dim),
        )
        self.dropout = nn.Dropout(dropout)
        self.layernorm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.filter_layer(x)
        return self.layernorm(h + self.dropout(self.ffn(h)))