"""HR@k / NDCG@k / MRR computed from the rank of the positive item among 100 candidates. Paper §5.1.2."""
from __future__ import annotations

import torch


def compute_ranks(score_pos: torch.Tensor, score_negs: torch.Tensor) -> torch.Tensor:
    return 1 + (score_negs > score_pos.unsqueeze(-1)).sum(dim=-1)


def hit_rate_at_k(ranks: torch.Tensor, k: int) -> float:
    return (ranks <= k).float().mean().item()


def ndcg_at_k(ranks: torch.Tensor, k: int) -> float:
    hits = (ranks <= k).float()
    gains = hits / torch.log2(ranks.float() + 1)
    return gains.mean().item()


def mrr(ranks: torch.Tensor) -> float:
    return (1.0 / ranks.float()).mean().item()