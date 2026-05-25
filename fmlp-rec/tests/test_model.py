"""FMLPRec end-to-end: encode/score shape, padding_idx grad zero, BPR-loss backward, finite forward."""
import pytest
import torch

from fmlp_rec.losses import bpr_loss
from fmlp_rec.model import FMLPRec


NUM_ITEMS = 1000
EMBED_DIM = 64
MAX_SEQ_LEN = 50
NUM_BLOCKS = 2
FFN_HIDDEN = 64
DROPOUT = 0.0


def make_model() -> FMLPRec:
    torch.manual_seed(0)
    return FMLPRec(NUM_ITEMS, EMBED_DIM, MAX_SEQ_LEN, NUM_BLOCKS, FFN_HIDDEN, DROPOUT)


def make_seq(batch_size: int, pad_left: int = 10) -> torch.Tensor:
    torch.manual_seed(1)
    seq = torch.randint(1, NUM_ITEMS + 1, (batch_size, MAX_SEQ_LEN))
    seq[:, :pad_left] = 0
    return seq


def test_encode_shape():
    m = make_model()
    out = m.encode(make_seq(4))
    assert out.shape == (4, MAX_SEQ_LEN, EMBED_DIM)
    assert torch.isfinite(out).all()


def test_score_shape():
    m = make_model()
    seq = make_seq(4)
    items = torch.randint(1, NUM_ITEMS + 1, (4, 100))
    scores = m.score(seq, items)
    assert scores.shape == (4, 100)
    assert torch.isfinite(scores).all()


def test_padding_idx_embedding_is_zero_and_grad_zero():
    m = make_model()
    assert m.item_embed.weight[0].abs().sum().item() == 0, "pad row should init to zero"
    seq = make_seq(2)
    items = torch.randint(1, NUM_ITEMS + 1, (2, 4))
    m.score(seq, items).sum().backward()
    assert m.item_embed.weight.grad[0].abs().sum().item() == 0, "pad row should receive zero grad"


def test_bpr_loss_backward_all_params_have_grad():
    m = make_model()
    seq = make_seq(8)
    pos = torch.randint(1, NUM_ITEMS + 1, (8, 1))
    neg = torch.randint(1, NUM_ITEMS + 1, (8, 1))
    scores = m.score(seq, torch.cat([pos, neg], dim=1))
    loss = bpr_loss(scores[:, 0], scores[:, 1])
    loss.backward()
    for name, p in m.named_parameters():
        assert p.grad is not None, f"{name} has no grad"
        if "padding_idx" in name or name == "item_embed.weight":
            continue
        assert p.grad.abs().sum().item() > 0, f"{name} grad is all-zero"


def test_multiple_batch_sizes_no_nan():
    m = make_model()
    m.eval()
    for batch_size in (1, 8, 256):
        out = m.encode(make_seq(batch_size))
        assert torch.isfinite(out).all(), f"non-finite at B={batch_size}"