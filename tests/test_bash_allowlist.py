"""Unit tests for the PreToolUse hook that enforces Coder capability boundaries."""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parent.parent / "scripts" / "bash_allowlist.py"


def run_hook(event: dict) -> subprocess.CompletedProcess:
    """Invoke the hook with the event on stdin; return completed process."""
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )


# --- Orchestrator Bash allowlist ---

def test_orchestrator_allowed_git_commit():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m '[loop-001][ctlr-r1][coder] feat: ...'"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-abc123.jsonl",
    }
    assert run_hook(event).returncode == 0


def test_orchestrator_allowed_smoke_cmd():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "bash scripts/run.sh --epochs 1 --batch_size 64"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-abc123.jsonl",
    }
    assert run_hook(event).returncode == 0


def test_orchestrator_denied_git_push():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "git push origin loop-001"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-abc123.jsonl",
    }
    result = run_hook(event)
    assert result.returncode != 0
    assert "DENY" in result.stderr


def test_orchestrator_denied_rm_rf():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf experiments/"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-abc123.jsonl",
    }
    assert run_hook(event).returncode != 0


# --- Executor Bash allowlist ---

def test_executor_allowed_python():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "python scripts/run.py --epochs 1"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode == 0


def test_executor_denied_git():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "git add -A"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


# --- Checker has no Bash ---

def test_checker_denied_any_bash():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-checker-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


# --- Edit/Write path allowlist ---

def test_orchestrator_can_write_status_json():
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/experiments/loop-001/status.json", "content": "{}"},
        "cwd": "/repo",
        "transcript_path": "/sessions/subagents/coder-abc.jsonl",
    }
    assert run_hook(event).returncode == 0


def test_orchestrator_cannot_write_tasks_json():
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/experiments/loop-001/tasks.json", "content": "{}"},
        "cwd": "/repo",
        "transcript_path": "/sessions/subagents/coder-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


def test_executor_can_write_worktree():
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/experiments/loop-001/code/models/LSTM4REC.py", "content": "..."},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode == 0


def test_executor_cannot_write_tasks_json():
    event = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/repo/experiments/loop-001/tasks.json"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


def test_executor_cannot_write_outside_experiments():
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/knowledge/wiki/hack.md", "content": "..."},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


# --- Non-matching tool falls through ---

def test_read_tool_always_allowed():
    event = {
        "tool_name": "Read",
        "tool_input": {"file_path": "/repo/anything"},
        "cwd": "/repo",
        "transcript_path": "/sessions/subagents/coder-abc.jsonl",
    }
    assert run_hook(event).returncode == 0


# --- Adversarial tests (C1, C2, I1, C3) ---

def test_executor_denied_command_chaining_semicolon():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -V ; git push"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


def test_executor_denied_command_chaining_ampersand():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -V && rm -rf experiments/"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


def test_executor_denied_python_dash_c():
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -c \"import os; os.system('git push')\""},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    assert run_hook(event).returncode != 0


def test_windows_transcript_path_detected():
    """On Windows, transcript_path may use backslashes. Detection must still work."""
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": "git push"},
        "cwd": "C:\\repo\\experiments\\loop-001\\code",
        "transcript_path": "C:\\sessions\\subagents\\coder-executor-abc.jsonl",
    }
    # Should be detected as executor and denied (executor can't run git)
    result = run_hook(event)
    assert result.returncode != 0
    assert "executor" in result.stderr.lower()


def test_executor_denied_path_traversal():
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/experiments/loop-001/code/../../tasks.json", "content": "{}"},
        "cwd": "/repo/experiments/loop-001/code",
        "transcript_path": "/sessions/subagents/coder-executor-abc.jsonl",
    }
    result = run_hook(event)
    assert result.returncode != 0
    assert ".." in result.stderr or "traversal" in result.stderr.lower()


def test_malformed_json_fails_closed():
    """Empty/malformed stdin must deny, not allow (fail-closed)."""
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="{not valid json",
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "HOOK MISCONFIGURED" in result.stderr
