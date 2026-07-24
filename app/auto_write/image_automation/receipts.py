"""외부/비원자 단계용 불변 receipt + 이벤트 JSONL."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from auto_write.image_automation.paths import sha256_bytes

EventKind = Literal["START", "END", "FAIL", "MANUAL_ACTION"]

_REDACT_KEYS = {
    "cookie",
    "cookies",
    "password",
    "token",
    "api_key",
    "authorization",
    "localstorage",
    "sessionstorage",
    "dom",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> str:
    """임시파일에 쓴 뒤 rename. 반환값은 내용 SHA-256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    digest = sha256_bytes(data)
    fd, tmp_name = tempfile.mkstemp(prefix=".receipt_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return digest


def write_receipt(
    receipts_dir: Path,
    stage: str,
    input_hash: str,
    config_hash: str,
    payload: dict[str, Any],
) -> Path:
    name = f"{stage}-{input_hash[:12]}-{config_hash[:12]}.json"
    path = receipts_dir / name
    body = {
        "schema_version": "1.0",
        "stage": stage,
        "input_hash": input_hash,
        "config_hash": config_hash,
        "written_at": _utc_now(),
        **payload,
    }
    atomic_write_json(path, body)
    return path


def append_event(
    events_path: Path,
    *,
    run_id: str,
    stage: str,
    attempt: int,
    event: EventKind,
    code: str = "",
    duration_ms: int | None = None,
    retry_count: int = 0,
    counters: dict[str, int] | None = None,
) -> None:
    """(run_id, stage, attempt) 당 START 1회 + terminal 1회 계약을 호출자가 지킨다."""
    events_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema_version": "1.0",
        "timestamp": _utc_now(),
        "run_id": run_id,
        "stage": stage,
        "attempt": attempt,
        "event": event,
        "code": code,
        "duration_ms": duration_ms,
        "retry_count": retry_count,
        "counters": counters or {},
    }
    _assert_no_secrets(row)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _assert_no_secrets(row: dict[str, Any]) -> None:
    blob = json.dumps(row, ensure_ascii=False).lower()
    for key in _REDACT_KEYS:
        # JSON key 또는 이스케이프된 문자열 내부 키 모두 차단
        if f'"{key}"' in blob or f'\\"{key}\\"' in blob or f"{key}=" in blob:
            raise ValueError(f"event contains forbidden key pattern: {key}")


def config_hash_of(mapping: dict[str, Any]) -> str:
    raw = json.dumps(mapping, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256_bytes(raw)


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)
