"""
Data processing script for ml-100k dataset.
Reads train_interactions.csv and test_interactions.csv,
builds user interaction sequences, and saves them for model training.
"""

import pandas as pd
import numpy as np
import json
from collections import Counter

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR    = './datasets/ml-100k/'
OUTPUT_DIR  = './tmp/'
MIN_SEQ_LEN = 2
MAX_SEQ_LEN = 200


def load_data():
    """Load raw interaction files and ID mappings."""
    train = pd.read_csv(DATA_DIR + 'train_interactions.csv')
    test  = pd.read_csv(DATA_DIR + 'test_interactions.csv')

    with open(DATA_DIR + 'item_map.json', 'r') as f:
        item_map = json.load(f)   # {original_id -> int_id}
    with open(DATA_DIR + 'user_map.json', 'r') as f:
        user_map = json.load(f)   # {original_id -> int_id}

    print(f"Loaded  train: {len(train)} rows | test: {len(test)} rows")
    print(f"Items: {len(item_map)} | Users: {len(user_map)}")
    print("Train columns:", train.columns.tolist())
    return train, test, item_map, user_map


def normalize_columns(df):
    """
    Rename columns to a standard format (user_id, item_id, timestamp).
    Adjust the mapping below if your CSV uses different column names.
    """
    col_map = {}
    for c in df.columns:
        lc = c.lower()
        if 'user' in lc:
            col_map[c] = 'user_id'
        elif 'item' in lc or 'movie' in lc:
            col_map[c] = 'item_id'
        elif 'time' in lc or 'stamp' in lc:
            col_map[c] = 'timestamp'
    return df.rename(columns=col_map)


def build_sequences(train_df, test_df):
    """
    Build (sequence, target) pairs for train and test.

    Train: sliding-window augmentation over each user's history.
    Test:  use full training history as context, predict each test item.
    """
    train_sequences, train_targets, train_users = [], [], []
    test_sequences,  test_targets,  test_users  = [], [], []

    # ── Training sequences ────────────────────────────────────────────────────
    for user, group in train_df.groupby('user_id'):
        items = group.sort_values('timestamp')['item_id'].tolist()
        # sliding window: each prefix predicts the next item
        for i in range(MIN_SEQ_LEN, min(len(items), MAX_SEQ_LEN)):
            train_sequences.append(items[:i])
            train_targets.append(items[i])
            train_users.append(user)

    # ── Testing sequences ─────────────────────────────────────────────────────
    for user, group in test_df.groupby('user_id'):
        # user must have training history
        if user not in train_df['user_id'].values:
            continue

        history = (train_df[train_df['user_id'] == user]
                   .sort_values('timestamp')['item_id'].tolist())

        if len(history) < MIN_SEQ_LEN:
            continue

        test_items = group.sort_values('timestamp')['item_id'].tolist()
        seq = history.copy()

        for i, target_item in enumerate(test_items):
            ctx = seq[-MAX_SEQ_LEN:] if len(seq) > MAX_SEQ_LEN else seq
            test_sequences.append(ctx)
            test_targets.append(target_item)
            test_users.append(user)
            seq.append(target_item)   # roll context forward

    return (train_sequences, train_targets, train_users,
            test_sequences,  test_targets,  test_users)


def save_outputs(train_sequences, train_targets, train_users,
                 test_sequences,  test_targets,  test_users,
                 item_map):
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── train_sequence.csv ────────────────────────────────────────────────────
    train_df = pd.DataFrame({
        'sequence':    train_sequences,
        'target':      train_targets,
        'user':        train_users,
        'length':      [len(s) for s in train_sequences],
        'sequence_id': np.arange(len(train_sequences)),
    })
    train_df.to_csv(OUTPUT_DIR + 'train_sequence.csv', index=False)

    # ── test_sequence.csv ─────────────────────────────────────────────────────
    test_df = pd.DataFrame({
        'sequence':    test_sequences,
        'target':      test_targets,
        'user':        test_users,
        'length':      [len(s) for s in test_sequences],
        'sequence_id': np.arange(len(test_sequences)),
    })
    test_df.to_csv(OUTPUT_DIR + 'test_sequence.csv', index=False)

    # ── item_dict.npy  (needed by train_model.py to get n_items) ─────────────
    np.save(OUTPUT_DIR + 'item_dict.npy', item_map)

    print(f"\nSaved to {OUTPUT_DIR}")
    print(f"  train sequences : {len(train_df)}")
    print(f"  test  sequences : {len(test_df)}")
    print(f"  n_items         : {len(item_map)}")

    # quick sanity check on sequence lengths
    lengths = [len(s) for s in train_sequences]
    print(f"  train seq len   : min={min(lengths)}, max={max(lengths)}, "
          f"mean={np.mean(lengths):.1f}")


def main():
    train, test, item_map, user_map = load_data()

    train = normalize_columns(train)
    test  = normalize_columns(test)

    # map IDs to integers (keep only known users/items)
    # JSON keys are strings; CSV values are integers — convert before mapping
    train['user_id'] = train['user_id'].astype(str).map(user_map)
    train['item_id'] = train['item_id'].astype(str).map(item_map)
    test['user_id']  = test['user_id'].astype(str).map(user_map)
    test['item_id']  = test['item_id'].astype(str).map(item_map)

    # drop rows where mapping failed
    train.dropna(subset=['user_id', 'item_id'], inplace=True)
    test.dropna(subset=['user_id', 'item_id'], inplace=True)
    train = train.astype({'user_id': int, 'item_id': int})
    test  = test.astype({'user_id': int, 'item_id': int})

    results = build_sequences(train, test)
    save_outputs(*results, item_map=item_map)


if __name__ == '__main__':
    main()
