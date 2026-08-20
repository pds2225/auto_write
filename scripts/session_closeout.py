#!/usr/bin/env python3
"""GitHub-shared session closeout signal (local / cloud / any AI).

One chat cannot save another chat. This file is only a *signal*:
the next session that opens this repo after `git pull` saves itself
into RESUME.md, then acks.

Usage:
  python scripts/session_closeout.py plant --from cursor-cloud
  python scripts/session_closeout.py status
  python scripts/session_closeout.py sync-disk --agent claude --location local
  python scripts/session_closeout.py ack --agent cursor --location cloud
  python scripts/session_closeout.py cancel

`due` stays true until cancel so every location/AI can still see the
flag. Each (agent, location) pair acks once. After git pull, run
sync-disk so the local Claude Code hook can fire.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
DUE_NAME = "closeout_due.json"
DISK_FLAG = Path(".claude") / ".closeout_due"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("SESSION_CLOSEOUT_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent


def due_path(root: Path) -> Path:
    return root / ".session" / DUE_NAME


def empty_state() -> dict:
    return {
        "schema": SCHEMA,
        "due": False,
        "id": "",
        "requested_at": "",
        "requested_from": "",
        "note": "",
        "acks": [],
    }


def load_state(root: Path) -> dict:
    path = due_path(root)
    if not path.is_file():
        return empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_state()
    if not isinstance(data, dict):
        return empty_state()
    state = empty_state()
    state.update({k: data.get(k, state[k]) for k in state})
    if not isinstance(state["acks"], list):
        state["acks"] = []
    state["due"] = bool(state["due"])
    return state


def save_state(root: Path, state: dict) -> Path:
    path = due_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def disk_flag_path(root: Path) -> Path:
    return root / DISK_FLAG


def plant_disk_flag(root: Path) -> Path | None:
    claude_dir = root / ".claude"
    if not claude_dir.is_dir():
        return None
    flag = disk_flag_path(root)
    flag.write_text(utc_now() + "\n", encoding="utf-8")
    return flag


def clear_disk_flag(root: Path) -> bool:
    flag = disk_flag_path(root)
    if flag.is_file():
        flag.unlink()
        return True
    return False


def cmd_plant(root: Path, requested_from: str, note: str) -> dict:
    stamp = utc_now()
    sid = stamp.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")
    state = {
        "schema": SCHEMA,
        "due": True,
        "id": sid,
        "requested_at": stamp,
        "requested_from": requested_from or "unknown",
        "note": note,
        "acks": [],
    }
    save_state(root, state)
    plant_disk_flag(root)
    return state


def cmd_cancel(root: Path) -> dict:
    state = load_state(root)
    state["due"] = False
    save_state(root, state)
    clear_disk_flag(root)
    return state


def has_ack(state: dict, agent: str, location: str) -> bool:
    for ack in state.get("acks") or []:
        if not isinstance(ack, dict):
            continue
        if ack.get("agent") == agent and ack.get("location") == location:
            return True
    return False


def cmd_ack(root: Path, agent: str, location: str, extra: str) -> dict:
    state = load_state(root)
    agent = agent or "unknown"
    location = location or "unknown"
    if not has_ack(state, agent, location):
        state.setdefault("acks", []).append(
            {
                "at": utc_now(),
                "agent": agent,
                "location": location,
                "extra": extra,
            }
        )
        save_state(root, state)
    # This machine's Claude hook is done. due stays True for other
    # location×AI pairs until cancel.
    clear_disk_flag(root)
    return state


def cmd_sync_disk(root: Path, agent: str, location: str) -> dict:
    """After git pull: align local Claude disk flag with the GitHub signal.

    If due and this pair has not acked → plant disk flag (Claude Code hook).
    If due and this pair already acked → clear disk flag (no save loop).
    If not due → leave a locally planted disk flag alone.
    """
    state = load_state(root)
    agent = agent or "claude"
    location = location or "local"
    if state.get("due") and not has_ack(state, agent, location):
        plant_disk_flag(root)
    elif state.get("due"):
        clear_disk_flag(root)
    return state


def format_status(root: Path, state: dict) -> str:
    disk = disk_flag_path(root).is_file()
    lines = [
        f"root: {root}",
        f"github_flag: {due_path(root)}",
        f"due: {state.get('due')}",
        f"id: {state.get('id') or '-'}",
        f"requested_at: {state.get('requested_at') or '-'}",
        f"requested_from: {state.get('requested_from') or '-'}",
        f"note: {state.get('note') or '-'}",
        f"local_claude_disk_flag: {disk} ({disk_flag_path(root)})",
        f"acks: {len(state.get('acks') or [])}",
    ]
    for i, ack in enumerate(state.get("acks") or [], 1):
        lines.append(
            f"  {i}. {ack.get('at')}  agent={ack.get('agent')}  "
            f"location={ack.get('location')}  extra={ack.get('extra') or '-'}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cross-location session closeout signal")
    p.add_argument("--root", default=None, help="Repo root (default: auto_write root)")
    sub = p.add_subparsers(dest="cmd", required=True)
    plant = sub.add_parser("plant", help="Broadcast closeout (git file + local Claude flag)")
    plant.add_argument("--from", dest="requested_from", default="unknown")
    plant.add_argument("--note", default="")
    ack = sub.add_parser("ack", help="This session saved RESUME.md")
    ack.add_argument("--agent", default="unknown", help="cursor|claude|codex|...")
    ack.add_argument("--location", default="unknown", help="local|cloud|github")
    ack.add_argument("--extra", default="")
    sync = sub.add_parser(
        "sync-disk",
        help="After git pull: plant .claude/.closeout_due if due and this pair not acked",
    )
    sync.add_argument("--agent", default="claude")
    sync.add_argument("--location", default="local")
    sub.add_parser("status", help="Show due flag and acks")
    sub.add_parser("cancel", help="Clear due (local disk flag too)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = repo_root(args.root)
    if args.cmd == "plant":
        state = cmd_plant(root, args.requested_from, args.note)
        print(format_status(root, state))
        print("next: git add .session/closeout_due.json && git commit && git push")
        print("other locations see this after git pull. They then update RESUME.md and ack.")
        return 0
    if args.cmd == "status":
        print(format_status(root, load_state(root)))
        return 0
    if args.cmd == "ack":
        state = cmd_ack(root, args.agent, args.location, args.extra)
        print(format_status(root, state))
        print("next: git add .session/closeout_due.json && git commit && git push")
        return 0
    if args.cmd == "cancel":
        state = cmd_cancel(root)
        print(format_status(root, state))
        print("next: git add .session/closeout_due.json && git commit && git push")
        return 0
    if args.cmd == "sync-disk":
        state = cmd_sync_disk(root, args.agent, args.location)
        print(format_status(root, state))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
