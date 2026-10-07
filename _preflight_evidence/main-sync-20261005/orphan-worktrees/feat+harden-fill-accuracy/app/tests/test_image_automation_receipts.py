"""M1 foundation: receipts / events / paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_write.image_automation.paths import anonymous_upload_name, ensure_run_dirs, sha256_bytes
from auto_write.image_automation.receipts import append_event, atomic_write_json, write_receipt


def test_anonymous_upload_name():
    assert anonymous_upload_name("auto_write", "abcdef0123456789") == "auto_write-abcdef01.pdf"


def test_atomic_write_and_receipt(tmp_path: Path):
    target = tmp_path / "r.json"
    digest = atomic_write_json(target, {"a": 1})
    assert target.is_file()
    assert digest == sha256_bytes(target.read_bytes())
    path = write_receipt(tmp_path / "receipts", "NOTEBOOKLM", "a" * 64, "b" * 64, {"ok": True})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["stage"] == "NOTEBOOKLM"
    assert data["ok"] is True


def test_events_attempt_contract(tmp_path: Path):
    events = tmp_path / "events.jsonl"
    append_event(events, run_id="r1", stage="NOTEBOOKLM", attempt=1, event="START")
    append_event(events, run_id="r1", stage="NOTEBOOKLM", attempt=1, event="MANUAL_ACTION", code="captcha")
    append_event(events, run_id="r1", stage="NOTEBOOKLM", attempt=2, event="START")
    append_event(events, run_id="r1", stage="NOTEBOOKLM", attempt=2, event="END", code="done")
    rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    assert [(r["attempt"], r["event"]) for r in rows] == [
        (1, "START"),
        (1, "MANUAL_ACTION"),
        (2, "START"),
        (2, "END"),
    ]


def test_event_redacts_forbidden_keys(tmp_path: Path):
    events = tmp_path / "events.jsonl"
    with pytest.raises(ValueError):
        append_event(
            events,
            run_id="r1",
            stage="NOTEBOOKLM",
            attempt=1,
            event="FAIL",
            code='{"cookie":"x"}',
        )


def test_ensure_run_dirs(tmp_path: Path):
    dirs = ensure_run_dirs("abc123", tmp_path)
    assert dirs["slides"].is_dir()
    assert dirs["receipts"].is_dir()
