"""HR@k / NDCG@k / MRR from per-user rank among 100 candidates. Paper §5.1.2."""
import math

import torch

from fmlp_rec.metrics import compute_ranks, hit_rate_at_k, mrr, ndcg_at_k


def test_compute_ranks_basic():
    score_pos = torch.tensor([5.0, 5.0, 5.0])
    score_negs = torch.tensor([
        [1.0, 2.0, 3.0, 4.0],     # no neg > pos → rank 1
        [1.0, 6.0, 3.0, 4.0],     # 1 neg > pos → rank 2
        [6.0, 7.0, 8.0, 9.0],     # 4 negs > pos → rank 5
    ])
    ranks = compute_ranks(score_pos, score_negs)
    assert torch.equal(ranks, torch.tensor([1, 2, 5]))


def test_hit_rate_at_k():
    ranks = torch.tensor([1, 2, 5, 100])
    assert hit_rate_at_k(ranks, 1) == 0.25
    assert hit_rate_at_k(ranks, 5) == 0.75
    assert hit_rate_at_k(ranks, 10) == 0.75
    assert hit_rate_at_k(ranks, 100) == 1.0


def test_ndcg_at_k_matches_hand_computation():
    ranks = torch.tensor([1, 2, 5, 100])
    expected = (1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(6) + 0) / 4
    assert abs(ndcg_at_k(ranks, 5) - expected) < 1e-6


def test_mrr_matches_hand_computation():
    ranks = torch.tensor([1, 2, 4])
    expected = (1.0 + 0.5 + 0.25) / 3
    assert abs(mrr(ranks) - expected) < 1e-6