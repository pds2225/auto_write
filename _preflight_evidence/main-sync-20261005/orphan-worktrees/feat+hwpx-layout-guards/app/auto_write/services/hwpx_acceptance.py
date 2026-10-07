# -*- coding: utf-8 -*-
"""hwpx_acceptance — HWPX 직접 산출물 수용검사 게이트(변환 없이 XML 단 직접 점검).

배경
----
현 수용검사(``usage_acceptance``)는 python-docx 기반 **DOCX 전용**이다. HWPX 산출물을
DOCX 로 변환한 뒤 검사하면, 변환 과정에서 유색 텍스트·양식 안내문구·줄위치 캐시
(``linesegarray``, 글씨 겹침 위험)가 소실돼 게이트가 결함을 못 잡는다.

이 모듈은 HWPX 가 본질적으로 ZIP(OWPML XML) 이라는 점을 이용해 **변환을 전혀 하지 않고**
압축만 풀어 ``Contents/header.xml``·``Contents/section*.xml`` 을 XML 단에서 직접 읽어
결함 **개수만 센다**. 원본은 읽기만 한다(수정·저장 없음).

점검(결정론·읽기전용, 개수만 카운트)
------------------------------------
1. ``colored``       — ``header.xml`` 의 ``charPr@textColor`` 가 흰(#FFFFFF)·검정(#000000)
                       외의 정규 6자리 hex 색(예: 회색 예시문구·파랑 안내). ``none``/``auto``/
                       미지정은 기본색이라 세지 않는다(오탐 0).
2. ``guides``        — ``section*.xml`` 에서 '작성방법/작성요령/기재요령'(핵심) + '삭제 후
                       제출/도식화/유의사항'(보조)을 **동시에** 담은 표·단락 개수(양식 안내문구).
3. ``linesegarray``  — ``section*.xml`` 의 ``hp:linesegarray`` 잔존 개수. 줄위치 캐시로,
                       .hwpx 를 직접 납품할 때 글씨 겹침/뭉침을 유발할 수 있어 결함으로 센다.

``ok`` = 위 세 fail 항목이 모두 0. CLI·게이트 배선은 하지 않는다(모듈+테스트만).

이식 참고: ``hwpx_submission_cleanup`` 의 제거 로직(force_black_text·remove_form_guides·
strip_linesegarray)을 '제거'가 아니라 '검출·카운트' 관점으로 옮긴 것. 네임스페이스·zip
읽기 패턴은 ``hwpx_fill`` 을 참고했다.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_HEADER_RE = re.compile(r"header\.xml$", re.IGNORECASE)
_HEX6_RE = re.compile(r"^[0-9A-F]{6}$")

# 양식 안내문구(작성요령/삭제 후 제출 지시) 시그니처 — 핵심 + 보조 동시 충족 시 카운트.
_GUIDE_CORE = ("작성방법", "작성요령", "기재요령", "작성 요령")
_GUIDE_AUX = ("삭제 후 제출", "삭제후 제출", "도식화", "항목 자율", "자율 변경", "유의사항")

_SAMPLE_LIMIT = 5


def _ln(el) -> str:
    """요소의 local-name(네임스페이스 접두어 제거). 주석/PI 등은 빈 문자열."""
    t = getattr(el, "tag", "")
    if isinstance(t, str) and "}" in t:
        return etree.QName(el).localname
    return t if isinstance(t, str) else ""


def _text_of(el) -> str:
    """el 하위 모든 hp:t 텍스트를 이어붙인 표시 문자열."""
    return "".join((t.text or "") for t in el.iter() if _ln(t) == "t")


def _cap(text: str, limit: int = 60) -> str:
    """샘플용 짧은 문자열(공백 정규화 + 길이 제한)."""
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= limit else t[:limit] + "…"


def count_colored_charpr(header_root) -> tuple[int, list[str]]:
    """header.xml charPr 중 흰·검정 외 유색(정규 hex) 개수와 색 샘플을 센다.

    textColor 가 정규 6자리 hex 이고 FFFFFF/000000 이 아닐 때만 유색으로 본다.
    none/auto/미지정/비정형 값은 기본색으로 취급해 세지 않는다(오탐 0).
    """
    n = 0
    samples: list[str] = []
    for cp in header_root.iter():
        if _ln(cp) != "charPr":
            continue
        tc = (cp.get("textColor") or "").upper().lstrip("#")
        if _HEX6_RE.match(tc) and tc not in ("FFFFFF", "000000"):
            n += 1
            if len(samples) < _SAMPLE_LIMIT:
                samples.append("#" + tc)
    return n, samples


def _is_guide_text(txt: str) -> bool:
    return any(c in txt for c in _GUIDE_CORE) and any(a in txt for a in _GUIDE_AUX)


def _within_any(el, ancestors: list) -> bool:
    """el 의 조상 중 ancestors(요소 identity) 에 포함된 것이 있으면 True."""
    cur = el.getparent()
    while cur is not None:
        for a in ancestors:
            if cur is a:
                return True
        cur = cur.getparent()
    return False


def count_form_guides(section_root) -> tuple[int, list[str]]:
    """섹션에서 양식 안내문구(핵심+보조 동시)를 담은 표·단락 개수와 샘플을 센다.

    안내 표 안의 단락은 표에서 이미 세었으므로 이중 카운트하지 않는다(조상 표 확인).
    핵심·보조가 표의 서로 다른 셀에 흩어진 경우엔 표 텍스트 결합으로 표 1건만 잡힌다.
    """
    n = 0
    samples: list[str] = []
    guide_tables: list = []  # identity 안정용으로 참조 유지
    for tbl in section_root.iter():
        if _ln(tbl) == "tbl" and _is_guide_text(_text_of(tbl)):
            guide_tables.append(tbl)
            n += 1
            if len(samples) < _SAMPLE_LIMIT:
                samples.append(_cap(_text_of(tbl)))
    for p in section_root.iter():
        if _ln(p) != "p" or not _is_guide_text(_text_of(p)):
            continue
        if _within_any(p, guide_tables):
            continue  # 안내 표 안 단락 — 표에서 이미 카운트
        n += 1
        if len(samples) < _SAMPLE_LIMIT:
            samples.append(_cap(_text_of(p)))
    return n, samples


def count_linesegarray(section_root) -> int:
    """섹션의 hp:linesegarray(줄위치 캐시) 잔존 개수 — 겹침 위험 지표."""
    return sum(1 for el in section_root.iter() if _ln(el) == "linesegarray")


@dataclass
class HwpxAcceptanceReport:
    """HWPX 직접 점검 결과 — 세 fail 항목의 개수와 제출가능 여부.

    colored/guides/linesegarray 는 결함 '개수'이고, ok 는 셋이 모두 0 일 때만 True.
    ok=False 는 '제출 전 후처리(유색→검정·안내문구 삭제·linesegarray 제거)가 필요함'을
    뜻한다(별도 후처리 모듈이 담당). 이 모듈은 판정·카운트만 한다.
    """
    source: str
    colored: int = 0
    guides: int = 0
    linesegarray: int = 0
    colored_samples: list[str] = field(default_factory=list)
    guides_samples: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def fail_defects(self) -> int:
        return self.colored + self.guides + self.linesegarray

    @property
    def ok(self) -> bool:
        return self.fail_defects == 0

    @property
    def verdict(self) -> str:
        return "제출가능" if self.ok else "제출불가(후처리 필요)"

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "ok": self.ok,
            "verdict": self.verdict,
            "fail_defects": self.fail_defects,
            "colored": self.colored,
            "guides": self.guides,
            "linesegarray": self.linesegarray,
            "colored_samples": list(self.colored_samples),
            "guides_samples": list(self.guides_samples),
            "notes": list(self.notes),
        }


def _extend_capped(dst: list, src: list, limit: int = _SAMPLE_LIMIT) -> None:
    for s in src:
        if len(dst) >= limit:
            break
        dst.append(s)


def run_hwpx_acceptance(path: str | Path) -> HwpxAcceptanceReport:
    """HWPX 산출물을 변환 없이 직접 열어 유색·안내문구·linesegarray 결함을 센다.

    Args:
        path: 점검할 .hwpx(ZIP/OWPML). 읽기만 하고 절대 수정하지 않는다.

    Returns:
        HwpxAcceptanceReport — colored/guides/linesegarray 개수 + ok(셋 다 0).

    Raises:
        FileNotFoundError: 파일이 없을 때.
        ValueError: 올바른 HWPX(ZIP) 가 아닐 때.
    """
    src = Path(path)
    report = HwpxAcceptanceReport(source=str(src))

    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    if not zipfile.is_zipfile(src):
        raise ValueError(f"올바른 HWPX(ZIP)가 아닙니다: {src.name}")

    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        for name in names:
            is_header = _HEADER_RE.search(name)
            is_section = _SECTION_RE.search(name)
            if not (is_header or is_section):
                continue
            try:
                root = etree.fromstring(z.read(name))
            except etree.XMLSyntaxError as exc:
                report.notes.append(f"{name} 파싱 실패(건너뜀): {exc}")
                continue
            if is_header:
                c, cs = count_colored_charpr(root)
                report.colored += c
                _extend_capped(report.colored_samples, cs)
            else:  # section
                g, gs = count_form_guides(root)
                report.guides += g
                _extend_capped(report.guides_samples, gs)
                report.linesegarray += count_linesegarray(root)

    if not any(_HEADER_RE.search(n) for n in names):
        report.notes.append("Contents/header.xml 을 찾지 못했습니다(유색 텍스트 점검 생략).")
    if not any(_SECTION_RE.search(n) for n in names):
        report.notes.append("Contents/section*.xml 을 찾지 못했습니다(안내문구·겹침 점검 생략).")
    return report
