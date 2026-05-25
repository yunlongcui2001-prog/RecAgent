"""FMLPTrainDataset / FMLPEvalDataset: left pad, right truncate, neg ≠ pos, eval 100 candidates with pos first."""
from fmlp_rec.data import FMLPEvalDataset, FMLPTrainDataset, pad_and_truncate


def test_pad_and_truncate_left_pads_short_sequence():
    assert pad_and_truncate([10, 20, 30], max_len=8) == [0, 0, 0, 0, 0, 10, 20, 30]


def test_pad_and_truncate_keeps_most_recent_when_too_long():
    assert pad_and_truncate(list(range(1, 100)), max_len=5) == [95, 96, 97, 98, 99]


def test_train_dataset_neg_never_equals_target_or_history():
    records = [{"train_seq": [1, 2, 3, 4, 5]}]
    ds = FMLPTrainDataset(records, num_items=10, max_seq_len=10, seed=0)
    history_set = set(records[0]["train_seq"])
    for i in range(len(ds)):
        sample = ds[i]
        neg = sample["neg"].item()
        assert neg != sample["pos"].item()
        assert neg not in history_set


def test_eval_dataset_100_candidates_pos_first_and_left_pad():
    records = [{"history": [1, 2, 3], "target": 7, "negatives": list(range(20, 119))}]
    ds = FMLPEvalDataset(records, max_seq_len=10)
    sample = ds[0]
    assert sample["candidates"].shape == (100,)
    assert sample["candidates"][0].item() == 7
    assert sample["input_seq"].tolist() == [0, 0, 0, 0, 0, 0, 0, 1, 2, 3]