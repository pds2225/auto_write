"""F3 사업계획서 본문 자동 채움 — 입력 정규화 계층.

근본 원인(2026-10-08 재현): 마포 양식의 본문 7칸은 승인(grant)이 이미 나오지만,
사업계획서 DOCX 제목이 "1. 아이디어 제안배경"·"가. 핵심내용"처럼 번호가 붙으면
normalized_cell_label 이 숫자/글자 번호까지 남겨 칸 라벨과 정확 일치하지 않아
전부 NO_SOURCE 로 비었다. 또 회사 마스터 JSON 의 값은 {value, confidence...}
사전이라 문자열로 바꾸면 사전 원문이 칸에 들어갈 뻔했다.

여기서는 매칭 '키'만 정규화한다. 승인·보호영역 판정은 그대로 core 가 한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.docx.services.hwpx_protected_regions import normalized_cell_label

# 제목 앞 번호·기호만 벗긴다. 뒤 라벨은 그대로 두고 정확 일치만 허용한다.
_ENUM_PREFIX_RE = re.compile(
    r"^\s*(?:(?:"
    r"제\s*\d+\s*[장절]"            # 제1장
    r"|\d+(?:\.\d+)*(?:[.)]|\s)"     # 1. / 1) / 1.2 / "1 "
    r"|\(\d+\)|\d+\)"               # (1) 1)
    r"|[①-⑳]"
    r"|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\.?"
    r"|[IVX]+\."
    r"|[가-하][.)]|\([가-하]\)"      # 가. 가) (가)
    r"|[□■○●◦▪▶▷◆◇·•*\-–—]"
    r")\s*)+"
)


def heading_key(text: str) -> str:
    """제목/키 → 칸 라벨 비교용 키(앞 번호·기호 제거 후 normalized_cell_label)."""
    raw = str(text or "")
    stripped = _ENUM_PREFIX_RE.sub("", raw, count=1)
    return normalized_cell_label(stripped or raw)


def scalar_value(value: Any) -> str | None:
    """마스터 JSON 항목({value, confidence...})이나 스칼라 → 문자열.

    충돌(conflict) 항목은 임의로 고르지 않고 None(채우지 않음)을 돌려준다.
    """
    if isinstance(value, dict):
        if str(value.get("confidence", "")).lower() == "conflict":
            return None
        value = value.get("value")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return text or None
    return None


def load_json_reference(path: str | Path) -> dict[str, Any]:
    """참고자료 JSON 1개 → {identity, records, section_images}.

    지원 모양(섞어도 됨):
    - 회사 마스터: {"fields": {"대표자": {"value": "...", "confidence": "medium"}}}
    - 사업계획 데이터: {"business_plan": {"아이디어 제안배경": "..."}} 또는 최상위 문자열 키
    - 반복 표: {"hwpx_records": {"지식재산권": [{...}, ...]}}
    - 섹션 이미지: {"section_images": [{"anchor", "image", "caption"}]}
    읽지 못하면 빈 결과(추측 금지).
    """
    empty: dict[str, Any] = {"identity": {}, "records": {}, "section_images": []}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception:
        return empty
    if not isinstance(payload, dict):
        return empty
    identity: dict[str, str] = {}

    def take(mapping: Any) -> None:
        if not isinstance(mapping, dict):
            return
        for key, value in mapping.items():
            text = scalar_value(value)
            if text and str(key).strip():
                identity.setdefault(str(key).strip(), text)

    take(payload.get("fields"))
    for name in ("business_plan", "bizplan", "사업계획"):
        take(payload.get(name))
    take({k: v for k, v in payload.items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)})
    records = payload.get("hwpx_records")
    images = payload.get("section_images")
    return {
        "identity": identity,
        "records": records if isinstance(records, dict) else {},
        "section_images": [x for x in images if isinstance(x, dict)] if isinstance(images, list) else [],
    }


def _ref_path(ref: Any) -> Path:
    return Path(ref if isinstance(ref, (str, Path)) else getattr(ref, "saved_path", "") or "")


def json_reference_inputs(refs) -> dict[str, Any]:
    """참고자료 중 .json 파일들을 합친다(앞 파일 우선, 덮어쓰기 없음)."""
    merged: dict[str, Any] = {"identity": {}, "records": {}, "section_images": [], "base_dirs": []}
    for ref in refs or ():
        path = _ref_path(ref)
        if path.suffix.lower() != ".json" or not path.is_file():
            continue
        loaded = load_json_reference(path)
        for key, value in loaded["identity"].items():
            merged["identity"].setdefault(key, value)
        for key, value in loaded["records"].items():
            merged["records"].setdefault(key, value)
        # 업로드 JSON 의 이미지 경로는 파일명만 쓴다(참고자료 폴더 밖 파일 읽기 차단).
        for entry in loaded["section_images"]:
            merged["section_images"].append({**entry, "image": Path(str(entry.get("image") or "")).name})
        if path.parent not in merged["base_dirs"]:
            merged["base_dirs"].append(path.parent)
    for ref in refs or ():
        parent = _ref_path(ref).parent
        if str(parent) not in {"", "."} and parent not in merged["base_dirs"]:
            merged["base_dirs"].append(parent)
    return merged
