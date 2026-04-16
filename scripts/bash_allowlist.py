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
