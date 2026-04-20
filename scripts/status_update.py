#!/usr/bin/env python3
"""CLI enforcing status.json invariants (RecAgent_plan.md §3.4.1).

Orchestrator calls this instead of editing status.json directly. All mutations
are validated against the append-forward-only invariant. Failure exits non-zero
with reason on stderr; success writes the updated file atomically.

Usage:
    python scripts/status_update.py init       --loop-id ID --controller-round N --tasks-json PATH
    python scripts/status_update.py mark-task  --loop-id ID --task-id TID --verdict VERDICT --checker-rounds K
    python scripts/status_update.py mark-smoke --loop-id ID
    python scripts/status_update.py set-phase  --loop-id ID --phase PHASE
    python scripts/status_update.py reset      --loop-id ID
    python scripts/status_update.py bump-round --loop-id ID
    python scripts/status_update.py get        --loop-id ID

Phases: init → tasks → checker → smoke → done | failed

Run from repo root. All paths are relative to cwd.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Path helpers ──────────────────────────────────────────────────────────────

def status_path(loop_id: str) -> Path:
    return Path("experiments") / loop_id / "status.json"


# ── Time ──────────────────────────────────────────────────────────────────────

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── I/O ───────────────────────────────────────────────────────────────────────

def load_status(loop_id: str) -> dict:
    p = status_path(loop_id)
    if not p.exists():
        _die(f"status.json not found: {p}")
    return json.loads(p.read_text())


def save_status(loop_id: str, status: dict) -> None:
    status["updated_at"] = now()
    p = status_path(loop_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=2))
    tmp.replace(p)


# ── Derived fields ────────────────────────────────────────────────────────────

def derive_aggregates(status: dict) -> None:
    status["all_units_pass"] = all(t["unit_test"] for t in status["tasks"])
    status["overall_complete"] = status["smoke_test"] and status["all_units_pass"]


VALID_PHASES = {"init", "tasks", "checker", "smoke", "done", "failed"}


# ── Error helper ──────────────────────────────────────────────────────────────

def _die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> None:
    tasks_file = Path(args.tasks_json)
    if not tasks_file.exists():
        _die(f"tasks.json not found: {tasks_file}")

    tasks_doc = json.loads(tasks_file.read_text())
    task_ids = [t["id"] for t in tasks_doc["tasks"]]

    status = {
        "loop_id": args.loop_id,
        "controller_round": args.controller_round,
        "phase": "tasks",
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


def cmd_mark_task(args: argparse.Namespace) -> None:
    if args.verdict != "real_impl":
        _die(
            f"verdict '{args.verdict}' does not qualify to set unit_test=true "
            f"(only 'real_impl' does)"
        )

    status = load_status(args.loop_id)
    known_ids = [t["id"] for t in status["tasks"]]
    target = next((t for t in status["tasks"] if t["id"] == args.task_id), None)

    if target is None:
        _die(f"task_id '{args.task_id}' not found in status (known: {known_ids})")

    if target["unit_test"] is True and target["verdict"] == "real_impl":
        return  # idempotent

    target["unit_test"] = True
    target["verdict"] = "real_impl"
    target["checker_rounds"] = int(args.checker_rounds)
    derive_aggregates(status)
    save_status(args.loop_id, status)


def cmd_set_phase(args: argparse.Namespace) -> None:
    if args.phase not in VALID_PHASES:
        _die(f"invalid phase '{args.phase}' (valid: {sorted(VALID_PHASES)})")
    status = load_status(args.loop_id)
    status["phase"] = args.phase
    save_status(args.loop_id, status)


def cmd_mark_smoke(args: argparse.Namespace) -> None:
    status = load_status(args.loop_id)

    if not status["all_units_pass"]:
        _die("cannot mark smoke_test=true before all_units_pass=true")

    status["smoke_test"] = True
    status["phase"] = "done"
    derive_aggregates(status)
    save_status(args.loop_id, status)


def cmd_reset(args: argparse.Namespace) -> None:
    """Batch rollback of per-task state + smoke. smoke_round is preserved."""
    status = load_status(args.loop_id)

    for t in status["tasks"]:
        t["unit_test"] = False
        t["verdict"] = "pending"
        t["checker_rounds"] = 0

    status["smoke_test"] = False
    status["phase"] = "tasks"
    derive_aggregates(status)
    save_status(args.loop_id, status)


def cmd_bump_round(args: argparse.Namespace) -> None:
    status = load_status(args.loop_id)
    status["smoke_round"] += 1
    save_status(args.loop_id, status)


def cmd_get(args: argparse.Namespace) -> None:
    print(status_path(args.loop_id).read_text())


# ── CLI wiring ────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="status.json CLI with append-forward-only invariant enforcement"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("--loop-id", required=True)
    pi.add_argument("--controller-round", type=int, required=True)
    pi.add_argument("--tasks-json", required=True)
    pi.set_defaults(func=cmd_init)

    pm = sub.add_parser("mark-task")
    pm.add_argument("--loop-id", required=True)
    pm.add_argument("--task-id", required=True)
    pm.add_argument("--verdict", required=True)
    pm.add_argument("--checker-rounds", type=int, required=True)
    pm.set_defaults(func=cmd_mark_task)

    ps = sub.add_parser("mark-smoke")
    ps.add_argument("--loop-id", required=True)
    ps.set_defaults(func=cmd_mark_smoke)

    psp = sub.add_parser("set-phase")
    psp.add_argument("--loop-id", required=True)
    psp.add_argument("--phase", required=True)
    psp.set_defaults(func=cmd_set_phase)

    pr = sub.add_parser("reset")
    pr.add_argument("--loop-id", required=True)
    pr.set_defaults(func=cmd_reset)

    pb = sub.add_parser("bump-round")
    pb.add_argument("--loop-id", required=True)
    pb.set_defaults(func=cmd_bump_round)

    pg = sub.add_parser("get")
    pg.add_argument("--loop-id", required=True)
    pg.set_defaults(func=cmd_get)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
