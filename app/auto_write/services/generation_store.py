"""generation_store.py — SFT 데이터 레이어 P0: AI 호출 trace 조립 계층.

run_evaluator 가 '실행 1건'을 학습 레코드로 조립하듯, 이 모듈은 'AI 호출 1건'
(system/user 프롬프트·원응답·provider·model·소요시간·purpose)을 trace 레코드로
조립해 learning_store.append_generation_trace 로 append 한다.

책임 분리(기존 아키텍처와 동일):
- learning_store  = 순수 JSONL I/O (append/load, 깨진줄 skip)
- generation_store = 레코드 조립 + 큰 본문(blob) 저장 (이 모듈)

용량·중복 방지(적대검증 HIGH 반영):
- system_prompt / user_prompt(질문+Context) / raw_response 는 그대로 JSONL 에 넣으면
  한 줄이 수십 KB가 되고 재시도·동일 Context 가 중복 저장된다. → 본문은 sha1 해시로
  ``workspace/learning/gen_blobs/<sha1>.txt`` 에 1회만 저장하고, trace 라인에는 해시와
  짧은 미리보기만 남긴다. 같은 Context 는 같은 해시 → 1개 파일로 dedup.

fail-safe(적대검증 HIGH 반영):
- 이 모듈은 호출 경계(openai_client._complete_text)에서 try/except 로 감싸 쓰인다.
  로깅 실패가 AI 호출·생성 파이프라인 실패로 승격되면 안 되므로, 호출부가 예외를
  흡수한다. 이 모듈 내부도 방어적으로 작성하되 예외를 삼키지는 않는다(호출부가 처리).

§9 M2 관례: KST 는 고정 오프셋(zoneinfo 금지 — Windows py-3.11 tzdata 부재).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import learning_store

_KST = timezone(timedelta(hours=9))
_BLOB_DIRNAME = "gen_blobs"
_PREVIEW_CHARS = 200


def _resolve_root(root: Path | None) -> Path:
    return Path(root) if root is not None else learning_store.LEARNING_ROOT


def _new_trace_id() -> str:
    return datetime.now(_KST).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]


def store_blob(text: str, root: Path | None = None) -> str:
    """본문을 gen_blobs/<sha1>.txt 에 1회만 저장하고 sha1(16자)을 반환한다.

    빈 문자열은 저장하지 않고 빈 해시("")를 반환한다(빈 프롬프트/빈 응답 구분용).
    """
    if not text:
        return ""
    digest = hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:16]
    blob_dir = _resolve_root(root) / _BLOB_DIRNAME
    blob_dir.mkdir(parents=True, exist_ok=True)
    path = blob_dir / f"{digest}.txt"
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return digest


def load_blob(digest: str, root: Path | None = None) -> str:
    """sha1 로 저장된 본문을 되읽는다(없으면 "" — P2 export 가 사용)."""
    if not digest:
        return ""
    path = _resolve_root(root) / _BLOB_DIRNAME / f"{digest}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def build_trace_record(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    raw_response: str,
    purpose: str = "",
    project_id: str = "",
    attempt: int = 1,
    duration_ms: int | None = None,
    trace_id: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """AI 호출 1건 → generation_traces.jsonl 1행 레코드. 본문은 blob 으로 분리 저장한다."""
    system_ref = store_blob(system_prompt, root)
    user_ref = store_blob(user_prompt, root)
    response_ref = store_blob(raw_response, root)
    return {
        "trace_id": trace_id or _new_trace_id(),
        "project_id": project_id,
        "purpose": purpose,
        "provider": provider,
        "model": model,
        "attempt": int(attempt),
        "empty": not bool(raw_response),
        "system_ref": system_ref,
        "user_ref": user_ref,
        "response_ref": response_ref,
        "user_preview": (user_prompt or "")[:_PREVIEW_CHARS],
        "response_preview": (raw_response or "")[:_PREVIEW_CHARS],
        "duration_ms": duration_ms,
        "created_at": datetime.now(_KST).isoformat(),
    }


def record_ai_call(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    raw_response: str,
    purpose: str = "",
    project_id: str = "",
    attempt: int = 1,
    duration_ms: int | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """trace 레코드를 만들어 generation_traces.jsonl 에 append 하고 레코드를 반환한다.

    호출부(openai_client)는 이 함수를 try/except 로 감싼다 — 여기서 예외가 나도
    (디스크 풀·권한 등) AI 호출 결과는 이미 확보돼 있으므로 상위는 정상 진행한다.
    """
    record = build_trace_record(
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_response=raw_response,
        purpose=purpose,
        project_id=project_id,
        attempt=attempt,
        duration_ms=duration_ms,
        root=root,
    )
    learning_store.append_generation_trace(record, root=root)
    return record


def resolve_trace_bodies(record: dict[str, Any], root: Path | None = None) -> dict[str, str]:
    """P2 export 용: trace 레코드의 blob 참조를 실제 본문으로 되돌린다."""
    return {
        "system_prompt": load_blob(str(record.get("system_ref", "")), root),
        "user_prompt": load_blob(str(record.get("user_ref", "")), root),
        "raw_response": load_blob(str(record.get("response_ref", "")), root),
    }
