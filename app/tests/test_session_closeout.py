"""Cross-location session closeout signal (scripts/session_closeout.py)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "session_closeout.py"


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _due(root: Path) -> dict:
    return json.loads((root / ".session" / "closeout_due.json").read_text(encoding="utf-8"))


def test_plant_status_ack_cancel(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    planted = _run(tmp_path, "plant", "--from", "cursor-cloud", "--note", "test")
    assert "due: True" in planted.stdout
    due = _due(tmp_path)
    assert due["due"] is True
    assert due["requested_from"] == "cursor-cloud"
    assert (tmp_path / ".claude" / ".closeout_due").is_file()

    status = _run(tmp_path, "status")
    assert "due: True" in status.stdout
    assert "local_claude_disk_flag: True" in status.stdout

    acked = _run(
        tmp_path,
        "ack",
        "--agent",
        "cursor",
        "--location",
        "cloud",
        "--extra",
        "RESUME.md",
    )
    assert "acks: 1" in acked.stdout
    assert not (tmp_path / ".claude" / ".closeout_due").exists()
    after_ack = _due(tmp_path)
    assert after_ack["due"] is True
    assert len(after_ack["acks"]) == 1

    cancelled = _run(tmp_path, "cancel")
    assert "due: False" in cancelled.stdout
    due2 = _due(tmp_path)
    assert due2["due"] is False


def test_ack_is_idempotent_per_agent_location_and_keeps_due(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    _run(tmp_path, "plant", "--from", "cursor-cloud")
    _run(tmp_path, "ack", "--agent", "cursor", "--location", "cloud")
    _run(tmp_path, "ack", "--agent", "cursor", "--location", "cloud")
    due = _due(tmp_path)
    assert due["due"] is True
    assert len(due["acks"]) == 1

    _run(tmp_path, "ack", "--agent", "claude", "--location", "local")
    due2 = _due(tmp_path)
    assert due2["due"] is True
    assert len(due2["acks"]) == 2
    pairs = {(a["agent"], a["location"]) for a in due2["acks"]}
    assert pairs == {("cursor", "cloud"), ("claude", "local")}


def test_sync_disk_after_other_location_acked(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    _run(tmp_path, "plant", "--from", "cursor-cloud")
    _run(tmp_path, "ack", "--agent", "cursor", "--location", "cloud")
    assert not (tmp_path / ".claude" / ".closeout_due").exists()

    _run(tmp_path, "sync-disk", "--agent", "claude", "--location", "local")
    assert (tmp_path / ".claude" / ".closeout_due").is_file()

    _run(tmp_path, "sync-disk", "--agent", "cursor", "--location", "cloud")
    assert not (tmp_path / ".claude" / ".closeout_due").exists()


def test_sync_disk_does_not_clear_local_only_flag_when_not_due(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    flag = claude / ".closeout_due"
    flag.write_text("local-only\n", encoding="utf-8")
    _run(tmp_path, "sync-disk", "--agent", "claude", "--location", "local")
    assert flag.is_file()
    assert flag.read_text(encoding="utf-8") == "local-only\n"


def test_plant_without_claude_dir_still_writes_github_flag(tmp_path: Path) -> None:
    _run(tmp_path, "plant", "--from", "codex-github")
    due = _due(tmp_path)
    assert due["due"] is True
    assert due["requested_from"] == "codex-github"
    assert not (tmp_path / ".claude" / ".closeout_due").exists()


def test_status_without_file_is_not_due(tmp_path: Path) -> None:
    out = _run(tmp_path, "status")
    assert "due: False" in out.stdout


def test_repo_default_flag_is_not_due() -> None:
    path = ROOT / ".session" / "closeout_due.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["due"] is False
