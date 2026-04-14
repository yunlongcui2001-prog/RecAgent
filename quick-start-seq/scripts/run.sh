#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# run.sh  —  One-shot pipeline: preprocess → train → done
#
# Usage:
#   bash scripts/run.sh                        # defaults
#   bash scripts/run.sh --epochs 50 --gpu 1   # custom args
#
# Run from the quick-start/ root directory.
# ─────────────────────────────────────────────────────────────────────────────

set -e   # exit immediately on error

# ── default hyper-parameters (can be overridden by CLI flags) ─────────────────
EPOCHS=30
BATCH_SIZE=256
EMBED_DIM=128
LR=0.001
GPU=0
SEED=42

# ── parse optional flags ───────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --epochs)     EPOCHS="$2";     shift 2 ;;
        --batch_size) BATCH_SIZE="$2"; shift 2 ;;
        --embed_dim)  EMBED_DIM="$2";  shift 2 ;;
        --lr)         LR="$2";         shift 2 ;;
        --gpu)        GPU="$2";        shift 2 ;;
        --seed)       SEED="$2";       shift 2 ;;
        *) echo "Unknown flag: $1"; exit 1 ;;
    esac
done

# ── banner ─────────────────────────────────────────────────────────────────────
echo "======================================================"
echo "  RecAgent Quick-Start  |  GRU4REC on ml-100k"
echo "======================================================"
echo "  epochs=${EPOCHS}  batch=${BATCH_SIZE}  embed=${EMBED_DIM}"
echo "  lr=${LR}  gpu=${GPU}  seed=${SEED}"
echo "======================================================"

# ── train & evaluate ──────────────────────────────────────────────────────────
echo ""
echo "[1/1] Training GRU4REC..."
python3 train_model.py \
    --epochs     "$EPOCHS"     \
    --batch_size "$BATCH_SIZE" \
    --embed_dim  "$EMBED_DIM"  \
    --lr         "$LR"         \
    --gpu        "$GPU"        \
    --seed       "$SEED"

echo ""
echo "======================================================"
echo "  All done!  Best model → ./checkpoints/gru4rec_best.ckpt"
echo "  Training log → ./checkpoints/train_log.txt"
echo "======================================================"
