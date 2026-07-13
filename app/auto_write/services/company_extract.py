"""company_extract.py — P3(기업정보 자산화): 참고자료 여러 개 → company_master.json.

resume_extract(원본 이력서들 → profile.json)의 **파일별 추출 → 우선순위 병합 → 충돌
needs_confirm** 패턴을 기업 도메인으로 일반화한다. 라벨 정규화는 cross_form_autofill 의
동의어 클러스터(_cluster_rep/SYNONYMS)를 그대로 재사용한다.

핵심 차이(중요): cross_form_autofill.extract_source_fields 는 '순수 숫자/금액/날짜' 값을
폐기하는 가드가 있어(양식 전사 전용) 사업자등록번호·자본금·직원수 같은 **기업 사실칸이
통째로 유실**된다. 그래서 이 모듈은 라벨 정규화만 재사용하고 값 추출은 자체 구현해
**숫자 사실값을 보존**한다.

안전 불변(날조0):
- 문서에 실제로 있는 값만 추출한다. 없는 필드는 missing 으로 정직 표기(빈값).
- 파일 간 값이 다르면 임의로 하나 고르지 않고 conflict(needs_confirm)로 드러낸다.
- confirmed=false 로 저장 — 사람 검수 전에는 확정 아님(검수 루프는 후속 슬라이스).
- 항목마다 provenance(source_file, raw_label) 를 붙여 어디서 왔는지 추적 가능.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .cross_form_autofill import SYNONYMS, _cluster_rep, _key
from .doc_text_extract import extract_text

_KST = timezone(timedelta(hours=9))

# 기업 '정체성' 필드만 화이트리스트로 추출한다.
# (사업명/과제명=프로젝트, 직위=사람 역할 → 기업 마스터에서 제외)
_COMPANY_CANON = [
    "기업명", "대표자", "사업자등록번호", "설립일", "업종", "주소",
    "연락처", "이메일", "홈페이지", "직원수", "자본금", "팩스",
]
# _cluster_rep 가 돌려주는 정규화 대표키 → 사람이 읽는 대표 라벨
_REP_TO_CANON: dict[str, str] = {}
for _cluster in SYNONYMS:
    _canon = _cluster[0]
    if _canon in _COMPANY_CANON:
        _REP_TO_CANON[_key(_canon)] = _canon

# 대표자 값 오전사 가드(역할서술이 이름칸에 들어오는 것 차단 — cross_form 정책과 동일 취지)
_ROLE_WORDS = ("총괄", "담당", "수행", "자문", "대표이사", "및 ")
_LINE_FIELD_RE = re.compile(r"^\s*([^:：|]{1,40})\s*[:：]\s*(.+?)\s*$")


@dataclass
class FieldValue:
    value: str
    confidence: str          # high(≥2 파일 일치) | medium(1 파일) | conflict(불일치)
    confirmed: bool
    sources: list[dict[str, str]]  # [{file, raw_label}]


@dataclass
class Conflict:
    field: str
    candidates: list[dict[str, str]]  # [{value, source}]
    reason: str


@dataclass
class CompanyMaster:
    company_key: str
    fields: dict[str, Any]
    conflicts: list[dict[str, Any]]
    missing: list[str]
    sources: list[str]
    updated_at: str


def _canon_field(label: str) -> str | None:
    rep = _cluster_rep(_key(label))
    if rep is None:
        return None
    return _REP_TO_CANON.get(rep)


def _is_field_label(text: str) -> bool:
    """값이 그 자체로 기업 필드 라벨이면 True(라벨→라벨 오추출 차단)."""
    return _canon_field(text) is not None


def _valid_value(canon: str, value: str) -> bool:
    v = value.strip()
    if not v or len(v) > 200:
        return False
    if _is_field_label(v):          # 값이 라벨이면 폐기(예: '기업명' 셀이 값으로)
        return False
    if canon == "대표자":
        if len(v) > 20 or any(w in v for w in _ROLE_WORDS) or "," in v:
            return False            # 역할서술은 이름 아님
    return True


def _iter_label_value_pairs(text: str):
    """텍스트에서 (라벨, 값) 후보를 뽑는다.

    ① 표 행(doc_text_extract 가 ' | ' 로 결합) → 짝수 인덱스=라벨, 다음=값.
    ② 본문 '라벨: 값' 라인.
    """
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if " | " in line:
            cells = [c.strip() for c in line.split("|")]
            for i in range(0, len(cells) - 1, 2):
                label, value = cells[i], cells[i + 1]
                if label and value:
                    yield label, value
            continue
        m = _LINE_FIELD_RE.match(line)
        if m:
            yield m.group(1), m.group(2)


def parse_company_fields(text: str) -> dict[str, dict[str, str]]:
    """텍스트 1건 → {canon: {value, raw_label}} (canon 당 처음 유효값 1개)."""
    out: dict[str, dict[str, str]] = {}
    for label, value in _iter_label_value_pairs(text):
        canon = _canon_field(label)
        if canon is None or canon in out:
            continue
        if not _valid_value(canon, value):
            continue
        out[canon] = {"value": value.strip(), "raw_label": label.strip()}
    return out


def extract_company_from_file(path: str | Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """파일 1개 → (partial {canon:{value,raw_label}}, notes)."""
    text, notes = extract_text(path)
    if not text or "지원하지 않는" in text or "텍스트 추출" in text:
        return {}, notes + [f"[skip] 텍스트 추출 실패: {Path(path).name}"]
    return parse_company_fields(text), notes


def _norm_value(value: str) -> str:
    """값 비교용 정규화(공백·하이픈 제거 — 사업자번호 000-00-00000 == 0000000000)."""
    return re.sub(r"[\s\-·.]", "", value).lower()


def merge_company(
    partials: list[tuple[str, dict[str, dict[str, str]]]],
    company_key: str = "",
) -> CompanyMaster:
    """파일별 partial 목록(우선순위 순) → CompanyMaster(충돌 검출)."""
    # canon → [(value, raw_label, source), ...] 우선순위 순
    collected: dict[str, list[tuple[str, str, str]]] = {}
    sources: list[str] = []
    for source, partial in partials:
        sources.append(source)
        for canon, info in partial.items():
            collected.setdefault(canon, []).append((info["value"], info["raw_label"], source))

    fields: dict[str, Any] = {}
    conflicts: list[dict[str, Any]] = []
    for canon, entries in collected.items():
        norms = {_norm_value(v) for v, _, _ in entries}
        srcs = [{"file": s, "raw_label": rl} for v, rl, s in entries]
        if len(norms) == 1:
            confidence = "high" if len({s for _, _, s in entries}) >= 2 else "medium"
            fields[canon] = asdict(FieldValue(entries[0][0], confidence, False, srcs))
        else:
            # 불일치 → 우선순위 1위 값을 tentative 로, conflict 로 드러낸다.
            fields[canon] = asdict(FieldValue(entries[0][0], "conflict", False, srcs))
            cands = []
            seen: set[str] = set()
            for v, _rl, s in entries:
                nv = _norm_value(v)
                if nv in seen:
                    continue
                seen.add(nv)
                cands.append({"value": v, "source": s})
            conflicts.append(asdict(Conflict(canon, cands, "파일 간 값 불일치 — 사람 확인 필요")))

    key = company_key or str(fields.get("기업명", {}).get("value", "")).strip() or "unknown"
    missing = [c for c in _COMPANY_CANON if c not in fields]
    return CompanyMaster(
        company_key=key,
        fields=fields,
        conflicts=conflicts,
        missing=missing,
        sources=sources,
        updated_at=datetime.now(_KST).isoformat(),
    )


def build_company_master(
    files: list[str | Path],
    company_key: str = "",
) -> tuple[CompanyMaster, list[tuple[str, dict[str, dict[str, str]]]], list[str]]:
    """파일 목록(우선순위 순) → (CompanyMaster, partials, notes)."""
    partials: list[tuple[str, dict[str, dict[str, str]]]] = []
    notes: list[str] = []
    for f in files:
        partial, file_notes = extract_company_from_file(f)
        partials.append((Path(f).name, partial))
        notes.extend(file_notes)
    master = merge_company(partials, company_key=company_key)
    return master, partials, notes


def master_to_json(master: CompanyMaster, *, indent: int = 2) -> str:
    return json.dumps(asdict(master), ensure_ascii=False, indent=indent)


def format_korean(master: CompanyMaster) -> str:
    lines = [f"기업 마스터: {master.company_key} (파일 {len(master.sources)}개)"]
    for canon, fv in master.fields.items():
        mark = "⚠충돌" if fv["confidence"] == "conflict" else fv["confidence"]
        lines.append(f"  · {canon}: {fv['value']}  [{mark}]")
    if master.conflicts:
        lines.append(f"충돌 {len(master.conflicts)}건(사람 확인 필요):")
        for c in master.conflicts:
            vals = " / ".join(f"{x['value']}({x['source']})" for x in c["candidates"])
            lines.append(f"  · {c['field']}: {vals}")
    if master.missing:
        lines.append(f"미확보(빈칸): {', '.join(master.missing)}")
    return "\n".join(lines)
