# Coder Subagent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 3-subagent Coder system (orchestrator + executor + checker) with a PreToolUse Hook for capability enforcement, following the spec in `RecAgent_plan.md §三`.

**Architecture:** Three Claude Code subagents (`coder`, `coder-executor`, `coder-checker`) coordinated by the orchestrator via the Task tool. State lives in `experiments/<loop_id>/` as JSON/patch artifacts. Capability boundaries enforced by `scripts/bash_allowlist.py` PreToolUse hook. `status.json` append-forward-only invariants enforced by `scripts/status_update.py` CLI. A `scripts/init_loop.py` dev harness stands in for the Controller until that role is designed.

**Tech Stack:** Python 3.10+, Claude Code subagents (`claude-opus-4-7`), git worktree, pytest.

---

## File Structure

### Files to create

| Path | Purpose |
|---|---|
| `.claude/agents/coder.md` | orchestrator subagent prompt |
| `.claude/agents/coder-executor.md` | executor subagent prompt |
| `.claude/agents/coder-checker.md` | checker subagent prompt |
| `scripts/bash_allowlist.py` | PreToolUse hook |
| `scripts/status_update.py` | status.json mutation CLI |
| `scripts/init_loop.py` | dev harness / mock Controller |
| `tests/test_bash_allowlist.py` | unit tests for hook |
| `tests/test_status_update.py` | unit tests for status CLI |
| `tests/fixtures/loop-smoke/tasks.json` | integration-test fixture |
| `docs/coder-system.md` | usage README |

### Files to modify

| Path | Change |
|---|---|
| `.claude/settings.json` | register PreToolUse hook |
| `.gitignore` | ignore `experiments/<id>/code/` worktree content but keep artifacts |

---

### Task 1: Directory scaffold + .gitignore

**Files:**
- Create: `scripts/.gitkeep`
- Create: `tests/.gitkeep`
- Create: `tests/fixtures/.gitkeep`
- Create: `experiments/.gitkeep`
- Create: `.claude/agents/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create directory markers**

```bash
mkdir -p scripts tests/fixtures experiments .claude/agents
touch scripts/.gitkeep tests/.gitkeep tests/fixtures/.gitkeep experiments/.gitkeep .claude/agents/.gitkeep
```

- [ ] **Step 2: Update .gitignore — ignore worktree code dirs but keep artifacts**

Append to `.gitignore`:

```gitignore

# RecAgent experiment artifacts: track artifacts, ignore worktree code checkouts
experiments/*/code/
!experiments/.gitkeep
```

Rationale: `experiments/<loop_id>/code/` is a git worktree (already tracked by git as a separate checkout), so we don't want it double-tracked in main's index. Artifacts like `tasks.json`, `status.json`, `coder_report_*.json` still get committed.

- [ ] **Step 3: Commit scaffold**

```bash
git add .claude/agents/.gitkeep scripts/.gitkeep tests/.gitkeep tests/fixtures/.gitkeep experiments/.gitkeep .gitignore
git commit -m "chore: scaffold dirs for coder subagent system"
```

---

### Task 2: `scripts/bash_allowlist.py` — PreToolUse hook (TDD)

**Files:**
- Create: `scripts/bash_allowlist.py`
- Create: `tests/test_bash_allowlist.py`
- Create: `tests/__init__.py` (empty)

**Hook event contract (assumption, verified in step 1):** Claude Code's PreToolUse hook receives a JSON event on stdin with at least `{tool_name, tool_input, cwd, transcript_path}`. Subagent identity is detected via `transcript_path` filename inspection (transcripts live in paths like `.../subagents/<subagent-name>-<id>.jsonl`). Exit 0 = allow, non-zero = deny.

- [ ] **Step 1: Verify hook event schema**

Check `~/.claude/docs/` or run a trivial hook that dumps stdin to `/tmp/hook_event.json` to confirm the shape of the event. Record findings in a comment at the top of `bash_allowlist.py`. If `transcript_path` doesn't contain subagent name, fallback is to inspect the transcript file's first few lines (which contain the agent's frontmatter).

- [ ] **Step 2: Write failing tests**

Create `tests/test_bash_allowlist.py`:

```python
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
        "tool_input": {"command": "python -c 'from models.LSTM4REC import LSTM4REC'"},
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
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd F:/RecAgent
python -m pytest tests/test_bash_allowlist.py -v
```

Expected: all 13 tests FAIL (hook doesn't exist yet).

- [ ] **Step 4: Implement `scripts/bash_allowlist.py`**

```python
#!/usr/bin/env python
"""PreToolUse hook enforcing Coder capability boundaries (RecAgent_plan.md §3.5).

Invoked by Claude Code before each Bash / Edit / Write call. Reads hook event on
stdin; exits 0 = allow, non-zero = deny with reason on stderr.

Subagent identification: we inspect `transcript_path` from the event. Claude Code
writes each subagent's conversation to a path like
  `<session_dir>/subagents/<subagent-name>-<uuid>.jsonl`
so a substring match on the filename reliably identifies the caller.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import PurePosixPath


# ---------- Allowlist tables ----------

BASH_ALLOW: dict[str, list[str]] = {
    "coder-orchestrator": [
        # Git ops the orchestrator needs for worktree + commit workflow
        r"^git status(\s|$)",
        r"^git diff(\s|$)",
        r"^git rev-parse(\s|$)",
        r"^git merge-base(\s|$)",
        r"^git add -A(\s|$)",
        r"^git commit\b",
        r"^git reset --hard\b",
        # Smoke test command (any bash scripts/run.sh ... invocation)
        r"^bash scripts/run\.sh(\s|$)",
        # status_update CLI
        r"^python\s+scripts/status_update\.py\b",
        # Generic python for small helpers
        r"^python(\s|$)",
        # Safe inspection
        r"^(ls|cat|pwd)(\s|$)",
    ],
    "coder-executor": [
        r"^python(\s|$)",
        r"^pytest(\s|$)",
        r"^(ls|cat|pwd)(\s|$)",
    ],
    # coder-checker: no Bash at all
}

# file_path prefix -> allowed subagents (earliest match wins)
WRITE_ALLOW: list[tuple[re.Pattern[str], set[str]]] = [
    # tasks.json is ALWAYS denied (it's Translator's output, immutable to Coder)
    (re.compile(r"experiments/[^/]+/tasks\.json$"), set()),
    # Orchestrator writes coordination artifacts
    (re.compile(r"experiments/[^/]+/status\.json$"), {"coder-orchestrator"}),
    (re.compile(r"experiments/[^/]+/round_\d+/"), {"coder-orchestrator"}),
    (re.compile(r"experiments/[^/]+/coder_report_r\d+\.json$"), {"coder-orchestrator"}),
    (re.compile(r"experiments/[^/]+/coder_failed_r\d+\.patch$"), {"coder-orchestrator"}),
    # Executor writes into the worktree
    (re.compile(r"experiments/[^/]+/code/"), {"coder-executor"}),
]


# ---------- Subagent detection ----------

def detect_subagent(event: dict) -> str | None:
    """Derive the calling subagent from the transcript path filename."""
    transcript = event.get("transcript_path", "")
    name = PurePosixPath(transcript).name  # e.g. 'coder-executor-abc.jsonl'
    # Longest match first so 'coder-executor' beats 'coder'
    for candidate in ("coder-executor", "coder-checker", "coder"):
        if name.startswith(candidate + "-") or name == candidate + ".jsonl":
            # Our canonical names inside allowlists
            return {
                "coder": "coder-orchestrator",
                "coder-executor": "coder-executor",
                "coder-checker": "coder-checker",
            }[candidate]
    return None


# ---------- Decision logic ----------

def check_bash(agent: str | None, command: str) -> tuple[bool, str]:
    if agent is None:
        return True, "non-coder caller; pass through"
    patterns = BASH_ALLOW.get(agent, [])
    if not patterns:
        return False, f"subagent '{agent}' is not allowed to run Bash"
    for p in patterns:
        if re.match(p, command):
            return True, f"matched pattern {p!r}"
    return False, f"subagent '{agent}' command not in allowlist: {command!r}"


def check_write(agent: str | None, file_path: str) -> tuple[bool, str]:
    if agent is None:
        return True, "non-coder caller; pass through"
    # Normalize to forward slashes + strip any repo-root prefix for matching
    normalized = file_path.replace("\\", "/")
    for pattern, allowed_agents in WRITE_ALLOW:
        if pattern.search(normalized):
            if agent in allowed_agents:
                return True, f"path matched {pattern.pattern!r}"
            return False, f"'{agent}' cannot write path matching {pattern.pattern!r}"
    # Default deny: Coder subagents can only write inside experiments/<id>/
    return False, f"'{agent}' attempted write outside experiments/: {file_path}"


# ---------- Main ----------

def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"hook error: invalid JSON on stdin: {e}", file=sys.stderr)
        return 0  # fail open if event is malformed (don't brick Claude Code)

    tool = event.get("tool_name", "")
    agent = detect_subagent(event)

    # Read is always allowed; we don't guard read access
    if tool == "Read":
        return 0

    if tool == "Bash":
        cmd = event.get("tool_input", {}).get("command", "")
        ok, reason = check_bash(agent, cmd)
        if not ok:
            print(f"DENY Bash [{agent}]: {reason}", file=sys.stderr)
            return 2
        return 0

    if tool in ("Edit", "Write"):
        path = event.get("tool_input", {}).get("file_path", "")
        ok, reason = check_write(agent, path)
        if not ok:
            print(f"DENY {tool} [{agent}]: {reason}", file=sys.stderr)
            return 2
        return 0

    # Any other tool: pass through
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python -m pytest tests/test_bash_allowlist.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/bash_allowlist.py tests/test_bash_allowlist.py tests/__init__.py
git commit -m "feat: add PreToolUse hook enforcing Coder capability boundaries"
```

---

### Task 3: `scripts/status_update.py` — status.json CLI (TDD)

Enforces the append-forward-only invariants from §3.4. Orchestrator invokes via Bash instead of editing `status.json` directly, so the invariant is mechanical, not prompt-dependent.

**Files:**
- Create: `scripts/status_update.py`
- Create: `tests/test_status_update.py`

**CLI surface:**

```
python scripts/status_update.py init       --loop-id ID --controller-round N --tasks-json PATH
python scripts/status_update.py mark-task  --loop-id ID --task-id TID --verdict real_impl --checker-rounds K
python scripts/status_update.py mark-smoke --loop-id ID           # requires all_units_pass
python scripts/status_update.py reset      --loop-id ID           # resets tasks[*] + smoke; used between smoke rounds
python scripts/status_update.py bump-round --loop-id ID           # smoke_round += 1
python scripts/status_update.py get        --loop-id ID           # prints status.json
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_status_update.py`:

```python
"""Unit tests for status_update.py invariant enforcement."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "status_update.py"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def make_tasks_json(path: Path, task_ids: list[str]) -> None:
    path.write_text(json.dumps({
        "tasks": [{"id": t, "op": "create", "path": f"dummy/{t}.py", "spec": "..."} for t in task_ids],
        "success_criteria": {"smoke_cmd": "echo ok", "asserts": []},
    }))


def read_status(exp_dir: Path) -> dict:
    return json.loads((exp_dir / "status.json").read_text())


def test_init_creates_status(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1", "t2"])
    result = run(["init", "--loop-id", "loop-001", "--controller-round", "1",
                  "--tasks-json", str(exp / "tasks.json")], tmp_path)
    assert result.returncode == 0, result.stderr
    s = read_status(exp)
    assert s["loop_id"] == "loop-001"
    assert s["controller_round"] == 1
    assert s["smoke_round"] == 0
    assert len(s["tasks"]) == 2
    assert all(t["unit_test"] is False for t in s["tasks"])
    assert s["all_units_pass"] is False
    assert s["smoke_test"] is False
    assert s["overall_complete"] is False


def test_mark_task_flips_unit_test(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1"])
    run(["init", "--loop-id", "loop-001", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")], tmp_path)
    result = run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
                  "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    assert result.returncode == 0, result.stderr
    s = read_status(exp)
    assert s["tasks"][0]["unit_test"] is True
    assert s["tasks"][0]["verdict"] == "real_impl"
    assert s["all_units_pass"] is True  # derived


def test_mark_task_rejects_non_real_impl(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1"])
    run(["init", "--loop-id", "loop-001", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")], tmp_path)
    result = run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
                  "--verdict", "hacky", "--checker-rounds", "3"], tmp_path)
    # hacky should NOT flip unit_test to true
    assert result.returncode != 0 or read_status(exp)["tasks"][0]["unit_test"] is False


def test_mark_smoke_requires_all_units(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1", "t2"])
    run(["init", "--loop-id", "loop-001", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")], tmp_path)
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    # Only t1 done, not t2 — mark-smoke must fail
    result = run(["mark-smoke", "--loop-id", "loop-001"], tmp_path)
    assert result.returncode != 0
    assert "all_units_pass" in result.stderr.lower()


def test_mark_smoke_succeeds_when_all_units_pass(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1"])
    run(["init", "--loop-id", "loop-001", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")], tmp_path)
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    result = run(["mark-smoke", "--loop-id", "loop-001"], tmp_path)
    assert result.returncode == 0, result.stderr
    s = read_status(exp)
    assert s["smoke_test"] is True
    assert s["overall_complete"] is True


def test_cannot_flip_true_back_to_false_via_mark_task(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1"])
    run(["init", "--loop-id", "loop-001", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")], tmp_path)
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    # Re-running mark-task with something non-real_impl should NOT reset it to false
    result = run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
                  "--verdict", "hacky", "--checker-rounds", "3"], tmp_path)
    assert result.returncode != 0


def test_reset_allows_false_rollback_batch(tmp_path: Path):
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1"])
    run(["init", "--loop-id", "loop-001", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")], tmp_path)
    run(["mark-task", "--loop-id", "loop-001", "--task-id", "t1",
         "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    run(["bump-round", "--loop-id", "loop-001"], tmp_path)
    result = run(["reset", "--loop-id", "loop-001"], tmp_path)
    assert result.returncode == 0, result.stderr
    s = read_status(exp)
    assert s["tasks"][0]["unit_test"] is False
    assert s["smoke_test"] is False
    assert s["overall_complete"] is False
    assert s["smoke_round"] == 1  # bumped before reset, NOT cleared by reset


def test_cannot_change_task_count(tmp_path: Path):
    """task list identity is fixed by tasks.json; must never drift."""
    exp = tmp_path / "experiments" / "loop-001"
    exp.mkdir(parents=True)
    make_tasks_json(exp / "tasks.json", ["t1", "t2"])
    run(["init", "--loop-id", "loop-001", "--controller-round", "1",
         "--tasks-json", str(exp / "tasks.json")], tmp_path)
    # Rewriting tasks.json with different ids must not cause status to drift
    # (status_update should read tasks.json fresh on each call and detect mismatch)
    make_tasks_json(exp / "tasks.json", ["t1", "t2", "t3"])  # Translator would not do this
    result = run(["mark-task", "--loop-id", "loop-001", "--task-id", "t3",
                  "--verdict", "real_impl", "--checker-rounds", "1"], tmp_path)
    # t3 wasn't in the original init; either reject, or init-time snapshot wins
    assert result.returncode != 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_status_update.py -v
```

Expected: all tests FAIL.

- [ ] **Step 3: Implement `scripts/status_update.py`**

```python
#!/usr/bin/env python
"""CLI enforcing status.json invariants (RecAgent_plan.md §3.4).

Orchestrator calls this instead of editing status.json directly. All mutations
are validated against the append-forward-only invariant. Failure exits non-zero
with reason on stderr; success writes the updated file.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def status_path(loop_id: str) -> Path:
    return Path("experiments") / loop_id / "status.json"


def tasks_path(loop_id: str) -> Path:
    return Path("experiments") / loop_id / "tasks.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_status(loop_id: str) -> dict:
    return json.loads(status_path(loop_id).read_text())


def save_status(loop_id: str, status: dict) -> None:
    status["updated_at"] = now()
    status_path(loop_id).write_text(json.dumps(status, indent=2))


def derive_aggregates(status: dict) -> None:
    status["all_units_pass"] = all(t["unit_test"] for t in status["tasks"])
    status["overall_complete"] = status["smoke_test"] and status["all_units_pass"]


def cmd_init(args: argparse.Namespace) -> int:
    tasks_doc = json.loads(Path(args.tasks_json).read_text())
    task_ids = [t["id"] for t in tasks_doc["tasks"]]
    status = {
        "loop_id": args.loop_id,
        "controller_round": args.controller_round,
        "smoke_round": 0,
        "tasks_total": len(task_ids),
        "tasks": [
            {"id": tid, "unit_test": False, "verdict": "pending", "checker_rounds": 0}
            for tid in task_ids
        ],
        "all_units_pass": False,
        "smoke_test": False,
        "overall_complete": False,
        "created_at": now(),
    }
    status_path(args.loop_id).parent.mkdir(parents=True, exist_ok=True)
    save_status(args.loop_id, status)
    return 0


def cmd_mark_task(args: argparse.Namespace) -> int:
    if args.verdict != "real_impl":
        print(f"ERROR: verdict '{args.verdict}' does not qualify to mark unit_test=true "
              f"(only 'real_impl' does)", file=sys.stderr)
        return 2
    status = load_status(args.loop_id)
    target = next((t for t in status["tasks"] if t["id"] == args.task_id), None)
    if target is None:
        print(f"ERROR: task id '{args.task_id}' not in status "
              f"(known: {[t['id'] for t in status['tasks']]})", file=sys.stderr)
        return 2
    if target["unit_test"] is True and target["verdict"] == "real_impl":
        # idempotent: already done; allow re-call (harmless)
        return 0
    target["unit_test"] = True
    target["verdict"] = "real_impl"
    target["checker_rounds"] = int(args.checker_rounds)
    derive_aggregates(status)
    save_status(args.loop_id, status)
    return 0


def cmd_mark_smoke(args: argparse.Namespace) -> int:
    status = load_status(args.loop_id)
    if not status["all_units_pass"]:
        print("ERROR: cannot mark smoke_test=true before all_units_pass=true",
              file=sys.stderr)
        return 2
    status["smoke_test"] = True
    derive_aggregates(status)
    save_status(args.loop_id, status)
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Batch reset of per-task state + smoke; smoke_round is preserved."""
    status = load_status(args.loop_id)
    for t in status["tasks"]:
        t["unit_test"] = False
        t["verdict"] = "pending"
        t["checker_rounds"] = 0
    status["smoke_test"] = False
    derive_aggregates(status)
    save_status(args.loop_id, status)
    return 0


def cmd_bump_round(args: argparse.Namespace) -> int:
    status = load_status(args.loop_id)
    status["smoke_round"] += 1
    save_status(args.loop_id, status)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    print(status_path(args.loop_id).read_text())
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="status.json CLI with invariant enforcement")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--loop-id", required=True)
    p_init.add_argument("--controller-round", type=int, required=True)
    p_init.add_argument("--tasks-json", required=True)
    p_init.set_defaults(func=cmd_init)

    p_mark = sub.add_parser("mark-task")
    p_mark.add_argument("--loop-id", required=True)
    p_mark.add_argument("--task-id", required=True)
    p_mark.add_argument("--verdict", required=True,
                        choices=["real_impl", "hacky", "doesnt_address", "pending"])
    p_mark.add_argument("--checker-rounds", type=int, required=True)
    p_mark.set_defaults(func=cmd_mark_task)

    p_smoke = sub.add_parser("mark-smoke")
    p_smoke.add_argument("--loop-id", required=True)
    p_smoke.set_defaults(func=cmd_mark_smoke)

    p_reset = sub.add_parser("reset")
    p_reset.add_argument("--loop-id", required=True)
    p_reset.set_defaults(func=cmd_reset)

    p_bump = sub.add_parser("bump-round")
    p_bump.add_argument("--loop-id", required=True)
    p_bump.set_defaults(func=cmd_bump_round)

    p_get = sub.add_parser("get")
    p_get.add_argument("--loop-id", required=True)
    p_get.set_defaults(func=cmd_get)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_status_update.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/status_update.py tests/test_status_update.py
git commit -m "feat: add status_update CLI enforcing append-forward-only invariants"
```

---

### Task 4: Register PreToolUse hook in `.claude/settings.json`

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: Read current settings**

```bash
cat .claude/settings.json
```

- [ ] **Step 2: Add hook configuration**

Update `.claude/settings.json` to include:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash $CLAUDE_PROJECT_DIR/tools/status_line.sh"
  },
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python $CLAUDE_PROJECT_DIR/scripts/bash_allowlist.py"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: Smoke-test the hook is wired**

Start a fresh Claude Code session in the repo. Try running `ls` via Bash — should succeed (not a Coder subagent, passes through). Then manually simulate a denied call by creating a test transcript-like path:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push"},"cwd":"/tmp","transcript_path":"/tmp/subagents/coder-abc.jsonl"}' | python scripts/bash_allowlist.py
```

Expected: exit code 2, stderr contains `DENY Bash [coder-orchestrator]`.

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: wire bash_allowlist.py as PreToolUse hook"
```

---

### Task 5: `.claude/agents/coder-checker.md` (skeptic subagent)

**Files:**
- Create: `.claude/agents/coder-checker.md`

- [ ] **Step 1: Write the checker subagent definition**

```markdown
---
name: coder-checker
description: Skeptic reviewer that judges whether a Coder-produced diff genuinely implements a task spec, or whether it is a fake/hacky workaround to make tests pass without real logic.
tools: Read
model: claude-opus-4-7
---

# Coder Checker — Skeptic Reviewer

You are the **skeptic** inside the Coder system. An executor just wrote code for a single task and its unit test passed. Your job is to decide whether the diff **actually implements** the task spec, or whether the unit test is a lie.

## Input (passed via the invoking prompt, as JSON)

```json
{
  "loop_id": "2026-04-17-loop-001",
  "task": { "id": "t1", "op": "create", "path": "models/LSTM4REC.py", "spec": "..." },
  "executor_output_path": "experiments/<loop_id>/round_<n>/task_t1_executor_a1.json",
  "attempt": 1
}
```

The executor's output file contains `{diff, unit_stdout, unit_exit_code, self_assessment}`. Read it. Then read the modified/created source file(s) in the worktree at `experiments/<loop_id>/code/<path>` for full context (Read tool only; you cannot edit or run anything).

## Your question is NOT "does it compile" — it is "is this real?"

For every task, work through this checklist explicitly in your reasoning:

1. **Intent alignment.** Does the diff solve the problem the spec describes? (Not a different problem that happens to pass a test.)
2. **Test is real.** Is the unit test actually validating behavior, or is it `assert True`, `assert 1 == 1`, `assert module is not None`, or equivalent?
3. **No exception swallowing.** Any new `try/except` that catches and silently ignores the failure? (`except Exception: pass` is a red flag.)
4. **No mocking the unit under test.** If the task is "implement LSTM4REC", the test must not mock LSTM4REC itself.
5. **No hardcoded return values to satisfy asserts.** `return 0.5` to make `assert score > 0.4` pass is a hack unless the spec literally asks for a constant.
6. **Identifier parity.** Class names, method names, argparse flags — do they match the spec? If spec says `--model`, is it really `--model`, not `--mdl`?
7. **Shape/type sanity.** Does the function actually produce what downstream callers (inferable from other files in the worktree) need?
8. **Scope discipline.** Are there unrelated edits to files the task didn't mention? (Sometimes OK for fixing imports, but always worth flagging.)

## Output

Write to `experiments/<loop_id>/round_<n>/task_<tid>_checker_a<k>.json`:

```json
{
  "task_id": "t1",
  "attempt": 1,
  "verdict": "real_impl" | "hacky" | "doesnt_address",
  "checked_at": "2026-04-17T...",
  "concerns": [
    { "severity": "error" | "warning", "checklist_item": 3, "quote": "...", "explanation": "..." }
  ],
  "suggest_fix": "..."    // null if verdict == real_impl
}
```

Then return a one-line summary text to your caller: `VERDICT <verdict>: <concerns count> concerns`.

## Verdicts

- `real_impl` — passes all checklist items; any concerns are style-level not correctness-level
- `hacky` — the diff technically runs/tests pass, but items 2/3/4/5 flagged; implementation is not trustworthy
- `doesnt_address` — even looking past hacks, the diff doesn't implement what the spec asked for (e.g., spec says "add LSTM" but diff only touches `argparse`)

## Hard rules

- Read-only. You have no Edit, Write, or Bash tools. If you feel the need to "run" something to check, write the concern as "I cannot verify X without running Z; flagging conservatively."
- Do not suggest fixes that broaden the scope of the task. Your fix suggestion should stay within `task.path`.
- Never output `real_impl` just because the test passed. Test passing is a prerequisite, not sufficient.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/agents/coder-checker.md
git commit -m "feat: add coder-checker subagent (skeptic reviewer)"
```

---

### Task 6: `.claude/agents/coder-executor.md` (task executor)

**Files:**
- Create: `.claude/agents/coder-executor.md`

- [ ] **Step 1: Write the executor subagent definition**

```markdown
---
name: coder-executor
description: Implements a single task from tasks.json — edits the specified file(s), runs that task's unit test, and reports the diff and test result. Does not interact with git, does not commit, does not modify tasks.json or status.json.
tools: Read, Edit, Write, Bash
model: claude-opus-4-7
---

# Coder Executor — Single Task Implementer

You implement **one** task from the translation. You do not plan, you do not pick which task, you do not commit, you do not touch git. You edit files, you run the unit test, you report.

## Input (via invoking prompt, as JSON)

```json
{
  "loop_id": "2026-04-17-loop-001",
  "smoke_round": 0,
  "attempt": 1,
  "task": { "id": "t1", "op": "create" | "modify", "path": "...", "spec": "..." },
  "tasks_json_readonly": "experiments/<loop_id>/tasks.json",
  "worktree_path": "experiments/<loop_id>/code",
  "prior_checker_concerns": [ ... ],     // empty on attempt=1
  "review_issues": [ ... ],              // populated if parent orchestrator is in Mode B
  "prior_smoke_log_tail": "..."          // populated from smoke_round > 0
}
```

## Your workflow

1. **Orient.** `cd` into `worktree_path`. Read `tasks.json` (read-only — do not edit). Understand the whole task list, not just your task; this prevents scope drift.

2. **Read surrounding code.** If your task is `modify`, read the target file and any files it imports. If `create`, read sibling files in the same directory to match conventions.

3. **Write code.** Edit or create the file per `task.spec`. Touch **only** the file at `task.path` unless a strictly necessary import fix in another file is required — flag any such secondary edit in your output's `unplanned_edits` field.

4. **Run the unit test for this task.** If the task doesn't spell out an explicit unit test command, infer the minimal one: `python -c "from <module> import <Class>; _ = <Class>(<reasonable args>)"` — verifies import + construction.

5. **If the test fails:** do NOT declare failure; try to fix the code (you have up to the orchestrator-level retry budget). If you genuinely cannot fix it after a reasonable effort, write your output file with `unit_exit_code != 0` and explain.

6. **Write your output file.** Path: `experiments/<loop_id>/round_<smoke_round>/task_<task_id>_executor_a<attempt>.json`:

```json
{
  "task_id": "t1",
  "attempt": 1,
  "op": "create",
  "path": "models/LSTM4REC.py",
  "diff": "...",                           // `git diff` output, but you can't run git — so include full file content under file_snapshot
  "file_snapshot": "<entire contents of task.path after edit>",
  "unplanned_edits": [],                   // list of other files you had to touch (with reason)
  "unit_test_cmd": "python -c '...'",
  "unit_stdout": "...",
  "unit_stderr": "...",
  "unit_exit_code": 0,
  "self_assessment": "I implemented LSTM4REC by mirroring GRU4REC.py line-by-line, swapping nn.GRU → nn.LSTM. The test imports and constructs an instance — passes."
}
```

7. **Return a one-line summary** to your caller (the orchestrator): `UNIT <pass|fail> t1 attempt=1 rc=0`.

## Hard rules

- **Never write to `tasks.json`.** The Bash/Write hook will block you even if you try.
- **Never run `git`.** The Bash hook will block. You are not responsible for commits.
- **Stay inside the worktree.** Don't read/write outside `experiments/<loop_id>/code/` for your edits. Reading `experiments/<loop_id>/tasks.json` is fine (that's your contract).
- **Honor `prior_checker_concerns` and `review_issues`.** If you're on attempt > 1, address the specific concerns enumerated there.
- **No mocking your own work.** Your test must exercise the real thing you wrote.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/agents/coder-executor.md
git commit -m "feat: add coder-executor subagent (single-task implementer)"
```

---

### Task 7: `.claude/agents/coder.md` (orchestrator)

**Files:**
- Create: `.claude/agents/coder.md`

- [ ] **Step 1: Write the orchestrator subagent definition**

```markdown
---
name: coder
description: Coder orchestrator. Drives the per-task executor+checker loop and the smoke-test loop. Commits on success, reports on failure. Does not itself write code — delegates to coder-executor and coder-checker subagents.
tools: Read, Write, Bash, Task
model: claude-opus-4-7
---

# Coder Orchestrator

You are the Coder. You receive a task list (from Translator, via Controller), you drive the implementation, you validate, you commit on success — or you report failure with enough detail for downstream diagnosis.

## Input (from Controller, via invoking prompt as JSON)

```json
{
  "mode": "implement" | "fixup",
  "loop_id": "2026-04-17-loop-001",
  "controller_round": 1,
  "base_commit": "a1b2c3d",
  "previous_commit": null,            // only Mode B: last Coder commit that Reviewer rejected
  "review_issues": [],                // only Mode B
  "tasks": [ ... ],                   // from tasks.json — DO NOT edit this file
  "success_criteria": { "smoke_cmd": "...", "asserts": [...] }
}
```

## Preconditions (guaranteed by Controller before you're invoked)

- `experiments/<loop_id>/` exists
- `experiments/<loop_id>/tasks.json` exists and matches the `tasks` field in your input
- `experiments/<loop_id>/code/` is a git worktree of branch `loop-<loop_id>` at `base_commit`
- You start with the above as your working directory context (though you must `cd` explicitly yourself)

## Your workflow

### Phase 0 — Setup

```
cd experiments/<loop_id>/code
# If Mode B: reset worktree and status before anything else
if mode == "fixup":
    git reset --hard <base_commit>
    python ../../../scripts/status_update.py reset --loop-id <loop_id>

# Init status.json if not yet present (Mode A, round 0)
if not exists experiments/<loop_id>/status.json:
    python ../../../scripts/status_update.py init \
        --loop-id <loop_id> --controller-round <controller_round> \
        --tasks-json ../tasks.json
```

### Phase 1 — Per-task loop

For each task `t` where `status.tasks[t].unit_test == false`:

```
attempt = 0
checker_concerns = []
while attempt < 3:
    attempt += 1
    # Invoke executor via Task tool
    executor_result = Task(
        subagent_type="coder-executor",
        prompt=<JSON input with task, prior_checker_concerns=checker_concerns, ...>
    )
    # executor wrote experiments/<loop_id>/round_<smoke_round>/task_<tid>_executor_a<attempt>.json
    exec_out = Read that file
    if exec_out.unit_exit_code != 0:
        # executor couldn't even get the unit test to pass — try again (same retry budget)
        continue

    # Invoke checker
    checker_result = Task(
        subagent_type="coder-checker",
        prompt=<JSON input pointing at the executor output file, task spec>
    )
    check_out = Read experiments/<loop_id>/round_<smoke_round>/task_<tid>_checker_a<attempt>.json
    if check_out.verdict == "real_impl":
        python scripts/status_update.py mark-task \
            --loop-id <loop_id> --task-id <tid> \
            --verdict real_impl --checker-rounds <attempt>
        break
    else:
        checker_concerns = check_out.concerns
        continue

if attempt == 3 and verdict != "real_impl":
    # Task failed all self-retries — escalate
    write experiments/<loop_id>/coder_failed_r<controller_round>.patch (git diff base..HEAD)
    write experiments/<loop_id>/coder_report_r<controller_round>.json:
        status = "failed_task_retries"
        failure.failed_task_id = <tid>
        failure.last_checker_concerns = checker_concerns
    exit with message "FAIL task t<tid> after 3 retries"
```

### Phase 2 — Smoke test

When all tasks have `unit_test == true`:

```
run success_criteria.smoke_cmd, capture stdout+stderr+exit_code to experiments/<loop_id>/round_<smoke_round>/smoke.log
if exit_code == 0 and all asserts hold:
    python scripts/status_update.py mark-smoke --loop-id <loop_id>
    git add -A
    git commit -m "[loop-<loop_id>][ctlr-r<controller_round>][coder] <goal summary>\n\ntasks: t1,t2,t3\nsmoke: pass (<duration>s)\nsmoke_rounds: <smoke_round>\nchecker_rejections: <sum of attempts-1 across tasks>\nbase: <base_commit short>"
    HEAD_COMMIT = git rev-parse HEAD
    write coder_report_r<controller_round>.json:
        status = "success"
        head_commit = HEAD_COMMIT
        smoke_rounds_used = smoke_round
        ... tasks[] with final_verdict, checker_rounds, executor_attempts
    exit with message "SUCCESS committed <HEAD_COMMIT>"
else:
    if smoke_round < 2:
        # dump the round for history, then reset and redo
        mkdir -p experiments/<loop_id>/round_<smoke_round>
        git diff <base_commit>..HEAD > experiments/<loop_id>/round_<smoke_round>/diff.patch
        git reset --hard <base_commit>
        python scripts/status_update.py bump-round --loop-id <loop_id>
        python scripts/status_update.py reset --loop-id <loop_id>
        # Re-enter Phase 1 with smoke_round+1; executor's prior_smoke_log_tail = last smoke.log
        goto Phase 1
    else:
        # Out of smoke retries
        write experiments/<loop_id>/coder_failed_r<controller_round>.patch
        write coder_report_r<controller_round>.json:
            status = "failed_smoke_retries"
            failure.smoke_round = smoke_round
            failure.last_smoke_log_tail = tail of last smoke.log
        exit with message "FAIL smoke after 3 total attempts"
```

## Hard rules

- **You do not write to `tasks.json`.** The hook will stop you; also, it's a correctness invariant.
- **You do not call `git push` or `git checkout <branch>`.** Only `git reset --hard <base_commit>`, `git add -A`, `git commit`, `git diff`, `git rev-parse`, `git status`, `git merge-base`.
- **You do not implement code directly.** Always delegate to `coder-executor` via the Task tool. Same for skepticism — always `coder-checker`.
- **Every status.json change goes through `scripts/status_update.py`.** Never hand-write or Edit that file.
- **On any failure path, always write `coder_report_r<controller_round>.json`.** Controller needs that file to decide next steps. `coder_failed_r<controller_round>.patch` accompanies all failure paths.
- **Single commit per successful invocation.** No intermediate commits, no amended commits.
- **Commit message first line must match** `[loop-<loop_id>][ctlr-r<n>][coder] ...` — Logger hook parses this.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/agents/coder.md
git commit -m "feat: add coder orchestrator subagent"
```

---

### Task 8: `scripts/init_loop.py` — dev harness / mock Controller

Stands in for Controller until that role is built. Creates a worktree, seeds a `tasks.json`, initializes `status.json`, invokes the `coder` subagent via `claude` CLI (or via manual Task invocation in an interactive session), and prints the final `coder_report`.

**Files:**
- Create: `scripts/init_loop.py`

- [ ] **Step 1: Write the harness**

```python
#!/usr/bin/env python
"""Dev harness: set up a Coder loop worktree and prepare invocation.

Does NOT invoke the coder subagent itself (that requires an interactive Claude
Code session). Instead, prepares everything and prints the exact `Task(...)` payload
to paste into a Claude Code conversation.

Usage:
    python scripts/init_loop.py \
        --loop-id 2026-04-17-smoke-test \
        --tasks-json tests/fixtures/loop-smoke/tasks.json \
        --base-branch main
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--loop-id", required=True)
    p.add_argument("--tasks-json", required=True, help="Source tasks.json to copy")
    p.add_argument("--base-branch", default="main")
    p.add_argument("--controller-round", type=int, default=1)
    args = p.parse_args()

    exp_dir = Path("experiments") / args.loop_id
    code_dir = exp_dir / "code"

    if exp_dir.exists():
        print(f"ERROR: {exp_dir} already exists. Remove it first or pick a new loop-id.",
              file=sys.stderr)
        return 2

    exp_dir.mkdir(parents=True)
    shutil.copy(args.tasks_json, exp_dir / "tasks.json")

    base_commit = run(["git", "rev-parse", args.base_branch]).stdout.strip()

    # Create worktree at experiments/<loop_id>/code on a new branch loop-<id>
    branch = f"loop-{args.loop_id}"
    run(["git", "worktree", "add", "-b", branch, str(code_dir), args.base_branch])

    # Initialize status.json
    run([sys.executable, "scripts/status_update.py", "init",
         "--loop-id", args.loop_id,
         "--controller-round", str(args.controller_round),
         "--tasks-json", str(exp_dir / "tasks.json")])

    # Compose and print the Task tool payload
    tasks_doc = json.loads(Path(args.tasks_json).read_text())
    payload = {
        "mode": "implement",
        "loop_id": args.loop_id,
        "controller_round": args.controller_round,
        "base_commit": base_commit,
        "previous_commit": None,
        "review_issues": [],
        "tasks": tasks_doc["tasks"],
        "success_criteria": tasks_doc["success_criteria"],
    }

    print("\n=== Worktree ready ===")
    print(f"Worktree: {code_dir.resolve()}")
    print(f"Branch:   {branch}")
    print(f"Base:     {base_commit}")
    print(f"Artifacts dir: {exp_dir.resolve()}")
    print("\n=== Invoke Coder ===")
    print("In an interactive Claude Code session at the repo root, run:")
    print("    Task(subagent_type='coder', prompt=<<JSON below>>)")
    print()
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke test the harness**

```bash
# Dry-run: needs a tasks.json fixture; we'll create one in Task 9
python scripts/init_loop.py --help
```

Expected: help text prints.

- [ ] **Step 3: Commit**

```bash
git add scripts/init_loop.py
git commit -m "feat: add init_loop.py dev harness"
```

---

### Task 9: End-to-end integration test

**Files:**
- Create: `tests/fixtures/loop-smoke/tasks.json`
- Create: `tests/integration_coder.md`

Uses the existing `quick-start-seq/` codebase as the thing-to-modify. A simple task: add a dropout parameter to `GRU4REC`.

- [ ] **Step 1: Write the fixture `tasks.json`**

Create `tests/fixtures/loop-smoke/tasks.json`:

```json
{
  "goal": "Add a configurable dropout to GRU4REC and plumb it through the training script",
  "tasks": [
    {
      "id": "t1",
      "op": "modify",
      "path": "quick-start-seq/models/GRU4REC.py",
      "spec": "Add a `dropout` kwarg to GRU4REC.__init__ (default 0.0). Pass it into nn.GRU via the `dropout=` parameter. Do not touch the output linear layer."
    },
    {
      "id": "t2",
      "op": "modify",
      "path": "quick-start-seq/train_model.py",
      "spec": "Add an argparse flag `--dropout` (type=float, default=0.0). Pass it into GRU4REC when instantiating the model. No other changes."
    }
  ],
  "success_criteria": {
    "smoke_cmd": "cd quick-start-seq && python data_process.py && python train_model.py --epochs 1 --batch_size 64 --dropout 0.1",
    "asserts": ["stdout contains 'hit@5'", "exit code == 0"]
  }
}
```

- [ ] **Step 2: Write the integration test procedure**

Create `tests/integration_coder.md`:

```markdown
# Coder End-to-End Integration Test

This is a manual test because Claude Code subagents require an interactive session.

## Prerequisites
- Fresh clone, or a clean tree on `main`.
- `pip install -r quick-start-seq/requirements.txt`
- `python quick-start-seq/data_process.py` run once (to generate the `tmp/` data).

## Steps

1. **Prepare the loop**

   ```bash
   python scripts/init_loop.py \
       --loop-id smoke-$(date +%Y%m%d-%H%M%S) \
       --tasks-json tests/fixtures/loop-smoke/tasks.json \
       --base-branch main
   ```

   Expected: script prints worktree path, branch name, and a JSON payload.

2. **Invoke the coder subagent**

   In Claude Code (interactive), issue:

   ```
   Task(subagent_type='coder', prompt=<paste the JSON from step 1>)
   ```

3. **Observe**

   - Coder should create `experiments/smoke-<ts>/round_0/task_*` files
   - On success: a commit appears on `loop-smoke-<ts>` branch in the worktree; `coder_report_r1.json` shows `status=success`
   - Smoke test output should mention `hit@5`

4. **Validate**

   ```bash
   cd experiments/smoke-<ts>/code
   git log --oneline                     # Should show one [loop-...][ctlr-r1][coder] commit
   cat ../coder_report_r1.json | python -m json.tool
   cat ../status.json | python -m json.tool
   ```

   `status.json` should show:
   - `all_units_pass: true`
   - `smoke_test: true`
   - `overall_complete: true`
   - Both tasks `verdict: real_impl`

5. **Cleanup**

   ```bash
   git worktree remove experiments/smoke-<ts>/code
   git branch -D loop-smoke-<ts>
   rm -rf experiments/smoke-<ts>
   ```

## Failure injection (optional)

To verify the checker catches hacks: temporarily edit `tests/fixtures/loop-smoke/tasks.json` and change `t1.spec` to something tautological like "add a dropout that doesn't do anything". Run the loop. Checker should reject with `verdict=doesnt_address`.

## What this test proves

- Worktree isolation works (main tree untouched)
- Orchestrator → executor → checker Task invocations chain correctly
- `bash_allowlist.py` doesn't block legitimate operations
- `status_update.py` invariants hold through a full lifecycle
- Commit message parses cleanly
- `coder_report_r<n>.json` matches schema
```

- [ ] **Step 3: Run the integration test manually**

Follow `tests/integration_coder.md` step-by-step. Record any deviations.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/loop-smoke/tasks.json tests/integration_coder.md
git commit -m "test: add end-to-end integration test for coder subagent"
```

---

### Task 10: Usage README

**Files:**
- Create: `docs/coder-system.md`

- [ ] **Step 1: Write the README**

Create `docs/coder-system.md`:

```markdown
# Coder Subagent System

Implements the Coder role from `RecAgent_plan.md §三`. Three subagents
(`coder`, `coder-executor`, `coder-checker`) plus a PreToolUse hook plus a
status.json CLI plus a dev harness.

## Quick invocation (dev)

```bash
python scripts/init_loop.py --loop-id smoke-1 --tasks-json tests/fixtures/loop-smoke/tasks.json
# Then in Claude Code:
Task(subagent_type="coder", prompt=<paste JSON>)
```

## Files

| File | Role |
|---|---|
| `.claude/agents/coder.md` | Orchestrator — entry point for Controller |
| `.claude/agents/coder-executor.md` | Implements one task |
| `.claude/agents/coder-checker.md` | Skeptic review of one task |
| `scripts/bash_allowlist.py` | PreToolUse hook, capability enforcement |
| `scripts/status_update.py` | CLI for status.json with invariant checks |
| `scripts/init_loop.py` | Dev harness (future: Controller will replace) |

## What's NOT in this deliverable

- **Translator** — tasks.json must be hand-authored for now
- **Reviewer** — `review_r<n>.json` is not produced/consumed yet
- **Controller** — `init_loop.py` stands in for it

These come in later deliverables.

## Troubleshooting

- **"DENY Bash [...]" in hook output:** the caller subagent isn't allowed to run that command. Check `scripts/bash_allowlist.py` `BASH_ALLOW` table.
- **`status_update.py` rejects a mark-task:** the verdict wasn't `real_impl`, or the task id wasn't in `tasks.json`. By design; don't work around it.
- **Executor writes to the wrong path:** path must be under `experiments/<loop_id>/code/`. Hook will block otherwise.
```

- [ ] **Step 2: Commit**

```bash
git add docs/coder-system.md
git commit -m "docs: add coder-system usage README"
```

---

## Self-review checklist (done before presenting this plan)

- **Spec coverage** (§3.1–3.8 of RecAgent_plan.md):
  - §3.1 3 subagents → Tasks 5, 6, 7 ✓
  - §3.2 lifecycle → encoded into Task 7's orchestrator prompt ✓
  - §3.3 input contract → fixture in Task 9, schemas in Tasks 5/6/7 prompts ✓
  - §3.4 status.json invariants → Task 3 `status_update.py` ✓
  - §3.5 permissions → Task 2 `bash_allowlist.py` + Task 4 settings registration ✓
  - §3.6 outputs — commit msg, reports, artifacts → encoded in Task 7 prompt ✓
  - §3.7 interfaces with other roles → Task 8 `init_loop.py` documents; README Task 10 notes what's deferred ✓
  - §3.8 defaults (3/M=2/N=3, opus-4-7) → Task 7 prompt + model frontmatter in 5/6/7 ✓

- **Placeholder scan:** None. Every step has concrete code or commands.

- **Type consistency:** `loop_id`, `controller_round`, `smoke_round`, `task_id` used consistently across status schema, report schema, executor/checker prompts, CLI args.

- **Known gaps / investigation steps:**
  - Task 2 Step 1 has a "verify hook event schema" investigation step. Finding could force a tweak to `detect_subagent` — acceptable, hooks are easy to amend.
  - `init_loop.py` only *prints* the Task payload; actual invocation is manual. A future Controller will automate this.
