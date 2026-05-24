"""BPR pairwise rank loss: -log σ(score_pos - score_neg). Paper Eq.10."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def bpr_loss(score_pos: torch.Tensor, score_neg: torch.Tensor) -> torch.Tensor:
    return -F.logsigmoid(score_pos - score_neg).mean()