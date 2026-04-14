# RecAgent Quick-Start

A minimal sequential recommendation demo using **GRU4REC** on the **MovieLens-100k** dataset.

## Dataset — MovieLens 100k

MovieLens 100k (ml-100k) is one of the most widely used benchmarks in recommendation system research. It contains 100,000 ratings from 943 users on 1,682 movies, collected by the GroupLens Research Project. Each record includes a user ID, movie ID, rating (1–5), and timestamp.

This project uses the interaction sequences sorted by timestamp to simulate a real-world scenario where the model predicts the next movie a user will interact with, based on their past history.

## Model — GRU4REC

GRU4REC (Hidasi et al., 2016) is a classic session-based recommendation model that uses a Gated Recurrent Unit (GRU) to model sequential user behaviour. The key idea is straightforward: treat each user's interaction history as a sequence, encode it with a GRU, and predict the next item from the hidden state.

Compared to matrix-factorisation methods, GRU4REC captures the **order** of interactions, making it well-suited for sequential recommendation tasks. It is lightweight, easy to train, and a solid baseline for more advanced models.

```
input sequence: [movie_1, movie_2, ..., movie_n]
      ↓ GRU encoder
session representation
      ↓ linear layer
scores over all items → top-k predictions
```

## Setup

```bash
pip install -r requirements.txt
```

## Project Structure

```
quick-start/
├── dataset/
│   └── ml-100k/           # raw data files
│       ├── train_interactions.csv
│       ├── test_interactions.csv
│       ├── item_map.json
│       └── user_map.json
├── models/
│   └── GRU4REC.py         # model definition
├── utils/
│   ├── metrics.py         # hit@k, ndcg@k, evaluate()
│   ├── helpers.py         # set_random_seed, get_device
│   └── logger.py          # get_logger
├── scripts/
│   └── run.sh             # one-shot pipeline script
├── tmp/                   # auto-created: train_sequence.csv, test_sequence.csv, item_dict.npy
├── checkpoints/           # auto-created: gru4rec_best.ckpt
├── data_process.py        # step 1 — build sequences from raw data
├── train_model.py         # step 2 — train & evaluate
├── requirements.txt
└── README.md
```

## Run

**Option A — one command (recommended)**

```bash
bash scripts/run.sh
```

Override any parameter as needed:

```bash
bash scripts/run.sh --epochs 50 --lr 0.0005 --gpu 1
```

**Option B — step by step**

```bash
# Step 1: process raw data into sequences
python data_process.py

# Step 2: train GRU4REC
python train_model.py --epochs 30 --batch_size 256 --embed_dim 128
```

## Key Arguments

| Argument | Default | Description |
|---|---|---|
| `--epochs` | 30 | Training epochs |
| `--batch_size` | 256 | Batch size |
| `--embed_dim` | 128 | Embedding & hidden size |
| `--lr` | 0.001 | Learning rate |
| `--gpu` | 0 | GPU device id (ignored on CPU) |
| `--seed` | 42 | Random seed |

## Output

| File | Description |
|---|---|
| `tmp/train_log.txt` | Loss and validation metrics per epoch |
| `checkpoints/gru4rec_best.ckpt` | Best model weights (by val hit@5) |

Evaluation reports Hit Rate and NDCG at @5, @10, @20.
