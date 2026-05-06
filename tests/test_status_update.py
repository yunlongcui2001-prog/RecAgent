"""Unit tests for scripts/status_update.py invariant enforcement."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "status_update.py"


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def make_tasks_json(path: Path, task_ids: list[str]) -> None:
    path.write_text(json.dumps({
        "tasks": [
            {"id": t, "op": "create", "path": f"dummy/{t}.py", "spec": "..."}
            for t in task_ids
        ],
        "success_criteria": {"smoke_cmd": "echo ok", "asserts": []},
    }))


def read_status(exp_dir: Path) -> dict:
    return json.loads((exp_dir / "status.json").read_text())


def init_loop(tmp_path: Path, loop_id: str, task_ids: list[str], controller_round: int = 1) -> Path:
    exp = tmp_path / "experiments" / loop_id
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", task_ids)
    result = run(
        ["init", "--loop-id", loop_id, "--controller-round", str(controller_round),
         "--tasks-json", str(exp / "tasks.json")],
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    return exp


# ── init ──────────────────────────────────────────────────────────────────────

def test_init_creates_status(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1", "t2"])
    s = read_status(exp)
    assert s["loop_id"] == "loop-001"
    assert s["controller_round"] == 1
    assert s["smoke_round"] == 0
    assert s["tasks_total"] == 2
    assert len(s["tasks"]) == 2
    assert all(t["unit_test"] is False for t in s["tasks"])
    assert all(t["verdict"] == "pending" for t in s["tasks"])
    assert s["all_units_pass"] is False
    assert s["smoke_test"] is False
    assert s["overall_complete"] is False
    assert "created_at" in s


def test_init_fails_without_tasks_json(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-002"
    exp.mkdir(parents=True)
    result = run(
        ["init", "--loop-id", "loop-002", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")],
        tmp_path,
    )
    assert result.returncode != 0


# ── mark-task ─────────────────────────────────────────────────────────────────

def test_mark_task_flips_unit_test(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    result = run(
        ["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"],
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    s = read_status(exp)
    assert s["tasks"][0]["unit_test"] is True
    assert s["tasks"][0]["verdict"] == "real_impl"
    assert s["tasks"][0]["checker_rounds"] == 1
    assert s["all_units_pass"] is True


def test_mark_task_rejects_non_real_impl(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    result = run(
        ["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "hacky", "--checker-rounds", "3"],
        tmp_path,
    )
    assert result.returncode != 0
    assert read_status(exp)["tasks"][0]["unit_test"] is False


def test_mark_task_rejects_unknown_task_id(tmp_path: Path):
    init_loop(tmp_path, "loop-001", ["t1"])
    result = run(
        ["mark-task", "--loop-id", "loop-001", "--task-id", "t99",
         "--verdict", "real_impl", "--checker-rounds", "1"],
        tmp_path,
    )
    assert result.returncode != 0


def test_mark_task_is_idempotent(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    for _ in range(2):
        result = run(
            ["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
             "--verdict", "real_impl", "--checker-rounds", "1"],
            tmp_path,
        )
        assert result.returncode == 0, result.stderr
    assert read_status(exp)["tasks"][0]["unit_test"] is True


def test_cannot_overwrite_true_with_non_real_impl(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    result = run(
        ["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "hacky", "--checker-rounds", "3"],
        tmp_path,
    )
    assert result.returncode != 0
    assert read_status(exp)["tasks"][0]["unit_test"] is True


# ── mark-smoke ────────────────────────────────────────────────────────────────

def test_mark_smoke_requires_all_units(tmp_path: Path):
    init_loop(tmp_path, "loop-001", ["t1", "t2"])
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    result = run(["mark-smoke", "--loop-id", "loop-001"], tmp_path)
    assert result.returncode != 0
    assert "all_units_pass" in result.stderr.lower()


def test_mark_smoke_succeeds_when_all_units_pass(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    result = run(["mark-smoke", "--loop-id", "loop-001"], tmp_path)
    assert result.returncode == 0, result.stderr
    s = read_status(exp)
    assert s["smoke_test"] is True
    assert s["overall_complete"] is True


# ── reset ─────────────────────────────────────────────────────────────────────

def test_reset_rolls_back_tasks_preserves_smoke_round(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    run(["bump-round", "--loop-id", "loop-001"], tmp_path)
    result = run(["reset", "--loop-id", "loop-001"], tmp_path)
    assert result.returncode == 0, result.stderr
    s = read_status(exp)
    assert s["tasks"][0]["unit_test"] is False
    assert s["tasks"][0]["verdict"] == "pending"
    assert s["smoke_test"] is False
    assert s["overall_complete"] is False
    assert s["smoke_round"] == 1  # bump-round already ran; reset does NOT clear it


# ── bump-round ────────────────────────────────────────────────────────────────

def test_bump_round_increments(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    run(["bump-round", "--loop-id", "loop-001"], tmp_path)
    run(["bump-round", "--loop-id", "loop-001"], tmp_path)
    assert read_status(exp)["smoke_round"] == 2


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_prints_json(tmp_path: Path):
    init_loop(tmp_path, "loop-001", ["t1"])
    result = run(["get", "--loop-id", "loop-001"], tmp_path)
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed["loop_id"] == "loop-001"


# ── task ID anchoring ─────────────────────────────────────────────────────────

def test_init_phase_is_tasks(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    assert read_status(exp)["phase"] == "tasks"


def test_set_phase_transitions(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    for phase in ["checker", "smoke", "done", "failed", "tasks"]:
        result = run(["set-phase", "--loop-id", "loop-001", "--phase", phase], tmp_path)
        assert result.returncode == 0, result.stderr
        assert read_status(exp)["phase"] == phase


def test_set_phase_rejects_invalid(tmp_path: Path):
    init_loop(tmp_path, "loop-001", ["t1"])
    result = run(["set-phase", "--loop-id", "loop-001", "--phase", "flying"], tmp_path)
    assert result.returncode != 0


def test_mark_smoke_sets_phase_done(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    run(["mark-smoke", "--loop-id", "loop-001"], tmp_path)
    assert read_status(exp)["phase"] == "done"


def test_reset_sets_phase_tasks(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1"])
    run(["set-phase", "--loop-id", "loop-001", "--phase", "smoke"], tmp_path)
    run(["reset", "--loop-id", "loop-001"], tmp_path)
    assert read_status(exp)["phase"] == "tasks"


def test_mark_task_rejects_id_added_after_init(tmp_path: Path):
    exp = init_loop(tmp_path, "loop-001", ["t1", "t2"])
    # Simulate tasks.json being rewritten with a new id (Translator bug)
    make_tasks_json(exp / "tasks.json", ["t1", "t2", "t3"])
    result = run(
        ["mark-task", "--loop-id", "loop-001", "--task-id", "t3",
         "--verdict", "real_impl", "--checker-rounds", "1"],
        tmp_path,
    )
    assert result.returncode != 0
