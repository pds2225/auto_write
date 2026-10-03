"""company_identity.py — 기업 프로필을 HWPX 직접채움 라벨로 옮긴다.

숫자 사실값(사업자등록번호·설립일·직원수·자본금)은 extract_source_fields 가
버리므로 여기 보존한다. 문서에 없는 값은 만들지 않는다.
기업명과 팀명은 같은 동의어 묶음이라, 팀명 라벨은 묶음으로 접기 전에 따로 둔다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# 한글 대표 라벨을 먼저 두고, 영문 별칭은 그 다음이다.
_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("기업명", ("기업명", "상호", "name", "organization_name", "company_name", "org_name")),
    ("대표자", ("대표자", "representative", "ceo", "owner")),
    ("팀명", ("팀명", "team", "team_name")),
    ("사업자등록번호", (
        "사업자등록번호", "사업자번호", "business_number", "biz_no", "registration_number",
    )),
    ("연락처", ("연락처", "전화", "전화번호", "phone", "tel", "mobile")),
    ("주소", ("주소", "address")),
    ("설립일", ("설립일", "founded", "founded_on", "established")),
    ("이메일", ("이메일", "email")),
    ("홈페이지", ("홈페이지", "homepage", "website")),
    ("업종", ("업종", "industry")),
    ("직원수", ("직원수", "employees", "employee_count")),
    ("자본금", ("자본금", "capital")),
    ("팩스", ("팩스", "fax")),
)

_ALIAS_TO_CANON: dict[str, str] = {}
for _canon, _aliases in _ALIASES:
    for _alias in _aliases:
        _ALIAS_TO_CANON[_alias.casefold()] = _canon


def company_profile_identity(profile: dict | None) -> dict[str, str]:
    """organization_profile 같은 자유 dict → 양식 라벨.

    대표 라벨(기업명)이 영문 별칭(name)보다 우선한다. 별칭이 아닌 비어 있지
    않은 키는 그대로 통과한다. 기업명을 팀명보다 앞에 둔다.
    """
    if not isinstance(profile, dict):
        return {}
    exact: dict[str, str] = {}
    alias: dict[str, str] = {}
    passthrough: dict[str, str] = {}
    for raw_key, raw_value in profile.items():
        value = "" if raw_value is None else str(raw_value).strip()
        if not value:
            continue
        key = str(raw_key).strip()
        canon = _ALIAS_TO_CANON.get(key.casefold())
        if canon is None:
            passthrough.setdefault(key, value)
            continue
        bucket = exact if key == canon else alias
        bucket.setdefault(canon, value)
    ordered: dict[str, str] = {}
    for canon, _aliases in _ALIASES:
        if canon in exact:
            ordered[canon] = exact[canon]
        elif canon in alias:
            ordered[canon] = alias[canon]
    for key, value in passthrough.items():
        ordered.setdefault(key, value)
    return ordered


def identity_from_label_text(text: str) -> dict[str, str]:
    """본문·표 텍스트의 라벨:값 → 양식 라벨. 숫자 사실값을 유지한다."""
    from auto_write.services.company_extract import _canon_field, _iter_label_value_pairs, _valid_value
    from auto_write.services.label_utils import key as label_key

    team_key = label_key("팀명")
    identity: dict[str, str] = {}
    for label, raw_value in _iter_label_value_pairs(text or ""):
        value = str(raw_value or "").strip()
        if not value:
            continue
        if label_key(label) == team_key:
            identity.setdefault("팀명", value)
            continue
        canon = _canon_field(label)
        if canon and _valid_value(canon, value):
            identity.setdefault(canon, value)
    return identity


def identity_from_reference_path(path: str | Path) -> dict[str, str]:
    """참고 DOCX 1개. 텍스트를 못 읽으면 빈 dict."""
    from auto_write.services.doc_text_extract import extract_text

    text, _notes = extract_text(path)
    if not text or "지원하지 않는" in text or "텍스트 추출" in text:
        return {}
    return identity_from_label_text(text)


def build_direct_fill_identity(project_input: Any) -> dict[str, str]:
    """직접 HWPX 채움 identity.

    ``project_meta['hwpx_identity']`` 가 같은 키를 이미 주면 그 값을 유지한다.
    """
    identity: dict[str, str] = {}
    meta = getattr(project_input, "project_meta", None) or {}
    raw_identity = meta.get("hwpx_identity") if isinstance(meta, dict) else None
    if isinstance(raw_identity, dict):
        identity.update({
            str(key): str(value)
            for key, value in raw_identity.items()
            if str(value or "").strip()
        })
    profile = getattr(project_input, "organization_profile", None) or {}
    for key, value in company_profile_identity(profile if isinstance(profile, dict) else {}).items():
        identity.setdefault(key, value)
    organization_name = ""
    if isinstance(profile, dict):
        organization_name = str(profile.get("name") or "").strip()
    if organization_name:
        identity.setdefault("기업명", organization_name)

    # 사용자 원문만 exact label 창업아이템 개요 후보로 넘긴다. 생성하거나 추론하지 않는다.
    answers = getattr(project_input, "answers", None) or {}
    if isinstance(answers, dict):
        overview = str(answers.get("user_brief") or answers.get("user_notes") or "").strip()
        if overview:
            identity.setdefault("창업아이템 개요", overview)
    return identity
