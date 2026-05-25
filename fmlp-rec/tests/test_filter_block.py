"""FilterLayer / FilterBlock invariants: rfft W shape, shape preservation, complex grad flow, finite outputs, end-to-end backward."""
import pytest
import torch

from fmlp_rec.filter_block import FilterBlock, FilterLayer


SEQ_LEN = 50
EMBED_DIM = 64
FFN_HIDDEN = 64
DROPOUT = 0.5


def make_input(batch_size: int = 4) -> torch.Tensor:
    torch.manual_seed(0)
    return torch.randn(batch_size, SEQ_LEN, EMBED_DIM)


def test_filter_layer_W_shape_and_dtype():
    """Per阶段2.3 + D 推导：用 rfft，可学习滤波器 W 应是 (n//2+1, d) 的复数张量。"""
    layer = FilterLayer(seq_len=SEQ_LEN, embed_dim=EMBED_DIM, dropout=DROPOUT)
    assert layer.W.shape == (SEQ_LEN // 2 + 1, EMBED_DIM)
    assert layer.W.is_complex()
    assert layer.W.requires_grad


def test_filter_layer_shape_preserved():
    """Filter Layer 输入输出形状一致 (B, n, d) → (B, n, d)。"""
    layer = FilterLayer(seq_len=SEQ_LEN, embed_dim=EMBED_DIM, dropout=DROPOUT)
    x = make_input(batch_size=4)
    y = layer(x)
    assert y.shape == x.shape
    assert y.dtype == torch.float32


def test_filter_layer_W_has_gradient():
    """复数 W 经 FFT/iFFT 后仍能传梯度——FFT-based 模型的核心踩坑点。"""
    layer = FilterLayer(seq_len=SEQ_LEN, embed_dim=EMBED_DIM, dropout=0.0)
    x = make_input(batch_size=2)
    loss = layer(x).sum()
    loss.backward()
    assert layer.W.grad is not None
    assert torch.is_complex(layer.W.grad)
    assert layer.W.grad.abs().sum().item() > 0


def test_filter_block_forward_finite():
    """FilterBlock 整体 forward 输出无 NaN / Inf。"""
    block = FilterBlock(seq_len=SEQ_LEN, embed_dim=EMBED_DIM, ffn_hidden_dim=FFN_HIDDEN, dropout=DROPOUT)
    block.eval()
    for batch_size in (1, 8, 256):
        y = block(make_input(batch_size))
        assert y.shape == (batch_size, SEQ_LEN, EMBED_DIM)
        assert torch.isfinite(y).all(), f"non-finite values at B={batch_size}"


def test_filter_block_end_to_end_backward():
    """FilterBlock 的所有可训练参数在 loss.backward() 后都拿到非零梯度。"""
    block = FilterBlock(seq_len=SEQ_LEN, embed_dim=EMBED_DIM, ffn_hidden_dim=FFN_HIDDEN, dropout=0.0)
    x = make_input(batch_size=4)
    loss = block(x).sum()
    loss.backward()
    for name, p in block.named_parameters():
        assert p.grad is not None, f"{name} has no grad"
        assert p.grad.abs().sum().item() > 0, f"{name} grad is all-zero"