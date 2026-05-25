"""BPR pairwise rank loss: -log σ(score_pos - score_neg). Paper Eq.10."""
import math

import torch

from fmlp_rec.losses import bpr_loss


def test_bpr_loss_near_zero_when_pos_dominates():
    score_pos = torch.tensor([20.0, 20.0])
    score_neg = torch.tensor([-20.0, -20.0])
    assert bpr_loss(score_pos, score_neg).item() < 1e-6


def test_bpr_loss_equals_ln2_when_equal():
    score_pos = torch.zeros(8)
    score_neg = torch.zeros(8)
    assert abs(bpr_loss(score_pos, score_neg).item() - math.log(2)) < 1e-6


def test_bpr_loss_has_gradient():
    score_pos = torch.tensor([1.0, 1.0], requires_grad=True)
    score_neg = torch.tensor([0.5, 0.7], requires_grad=True)
    bpr_loss(score_pos, score_neg).backward()
    assert score_pos.grad is not None and score_pos.grad.abs().sum().item() > 0
    assert score_neg.grad is not None and score_neg.grad.abs().sum().item() > 0