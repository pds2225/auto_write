"""output_naming — 제출 파일명 규칙 (어디서든 동일).

기본: ``{양식접두}_{성명}.hwpx``
예: ``전문상담위원_참여신청서_박다솜.hwpx``
"""

from __future__ import annotations

import re
from pathlib import Path

from .submission_gates import WORK_SUFFIXES, work_suffix_hits  # noqa: F401  L059

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename_part(text: str, *, fallback: str = "미상") -> str:
    """파일명 한 토막을 안전하게 다듬는다.

    윈도우가 금지하는 글자(``< > : " / \\ | ? *``·제어문자)와 공백을 모두 없앤다.
    지우고 나서 남는 게 없으면 ``fallback`` 을 쓴다 — 이름이 ``_.hwpx`` 처럼
    깨지는 것을 막기 위해서다.
    """
    s = (text or "").strip()
    s = _INVALID.sub("", s)
    s = re.sub(r"\s+", "", s)
    return s or fallback


def submit_filename(
    *,
    form_prefix: str = "전문상담위원_참여신청서",
    name: str = "",
    ext: str = ".hwpx",
    version: str | None = None,
) -> str:
    """제출용 파일명. version 예: 'v1' → …_박다솜_v1.hwpx"""
    if not ext.startswith("."):
        ext = f".{ext}"
    prefix = sanitize_filename_part(form_prefix, fallback="신청서")
    person = sanitize_filename_part(name, fallback="미상")
    base = f"{prefix}_{person}"
    if version:
        ver = sanitize_filename_part(version, fallback="v1")
        base = f"{base}_{ver}"
    return f"{base}{ext}"


def resolve_submit_path(
    directory: str | Path,
    *,
    form_prefix: str = "전문상담위원_참여신청서",
    name: str = "",
    ext: str = ".hwpx",
    version: str | None = None,
) -> Path:
    """directory / 자동파일명. 디렉터리 없으면 생성하지 않음(호출측 책임)."""
    return Path(directory) / submit_filename(
        form_prefix=form_prefix, name=name, ext=ext, version=version
    )
