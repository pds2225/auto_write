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
2. ``guides``        — ``section*.xml`` 의 양식 안내문구 표·단락 개수.
                       (가) '작성방법/작성요령/기재요령'(핵심) + '삭제 후 제출/도식화/유의사항'(보조)
                       동시, (나) 보조 없이 핵심 표제만 있는 지시문
                       (예: '작성방법: 예시를 참고하십시오').
                       핵심어가 본문에 섞인 문장('작성요령을 잘 따르십시오')은 세지 않는다.
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
from typing import Any, Sequence

from lxml import etree

_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_HEADER_RE = re.compile(r"header\.xml$", re.IGNORECASE)
_HEX6_RE = re.compile(r"^[0-9A-F]{6}$")

# 양식 안내문구. 핵심+보조를 함께 담거나, 보조 없이 핵심 표제(`작성방법:`)만 있는 지시문.
_GUIDE_CORE = ("작성방법", "작성요령", "기재요령", "작성 요령")
_GUIDE_AUX = ("삭제 후 제출", "삭제후 제출", "도식화", "항목 자율", "자율 변경", "유의사항")
# 핵심 토큰 직후의 콜론만 표제로 본다. '작성요령을 …' 같은 본문 언급은 제외.
_CORE_HEADING_RE = re.compile(r"(?:작성방법|기재요령|작성\s*요령)\s*[:：]")

_SAMPLE_LIMIT = 5

# D6: 정부양식 예시 이름. identity 로 채운 실값이면 허용(오탐 방지).
TEMPLATE_DUMMY_NAMES = ("홍길동", "아무개")


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
    """양식 안내문구. 핵심+보조, 또는 보조 없는 핵심 표제 지시문."""
    if not any(token in txt for token in _GUIDE_CORE):
        return False
    if any(token in txt for token in _GUIDE_AUX):
        return True
    return _CORE_HEADING_RE.search(txt) is not None


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
    """섹션에서 양식 안내문구(핵심+보조, 또는 핵심 표제)를 담은 표·단락 개수와 샘플을 센다.

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


def count_template_dummy_names(
    section_root,
    *,
    allowed: Sequence[str] = (),
) -> tuple[int, list[str]]:
    """양식 예시 이름(홍길동 등) 잔존 — D6.

    ``allowed`` 에 그 문자열이 들어 있으면(채운 신원값) 세지 않는다.
    반환: (더미 이름 종류 수, 샘플).
    """
    blob = "".join(section_root.itertext())
    allow_blob = " ".join(str(a) for a in allowed if a)
    n = 0
    samples: list[str] = []
    for name in TEMPLATE_DUMMY_NAMES:
        if name in allow_blob:
            continue
        if name in blob:
            n += 1
            if len(samples) < _SAMPLE_LIMIT:
                samples.append(name)
    return n, samples


@dataclass
class HwpxAcceptanceReport:
    """HWPX 직접 점검 결과 — 세 fail 항목의 개수와 제출가능 여부.

    colored/guides/linesegarray/dummy_names 는 결함 '개수'이고, ok 는 모두 0 일 때만 True.
    ok=False 는 '제출 전 후처리(유색→검정·안내문구 삭제·linesegarray 제거·예시이름 치환)가 필요함'을
    뜻한다(별도 후처리 모듈이 담당). 이 모듈은 판정·카운트만 한다.
    """
    source: str
    colored: int = 0
    guides: int = 0
    linesegarray: int = 0
    dummy_names: int = 0
    colored_samples: list[str] = field(default_factory=list)
    guides_samples: list[str] = field(default_factory=list)
    dummy_name_samples: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def fail_defects(self) -> int:
        return self.colored + self.guides + self.linesegarray + self.dummy_names

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
            "dummy_names": self.dummy_names,
            "colored_samples": list(self.colored_samples),
            "guides_samples": list(self.guides_samples),
            "dummy_name_samples": list(self.dummy_name_samples),
            "notes": list(self.notes),
        }


def _extend_capped(dst: list, src: list, limit: int = _SAMPLE_LIMIT) -> None:
    for s in src:
        if len(dst) >= limit:
            break
        dst.append(s)


def _is_colored_hex(tc: str) -> bool:
    return bool(_HEX6_RE.match(tc) and tc not in ("FFFFFF", "000000"))


def _charpr_colors(header_root) -> dict[str, str]:
    """charPr id → textColor(대문자, # 없음). id 없는 정의는 빈 키로 모은다."""
    colors: dict[str, str] = {}
    anon = 0
    for cp in header_root.iter():
        if _ln(cp) != "charPr":
            continue
        tc = (cp.get("textColor") or "").upper().lstrip("#")
        cid = cp.get("id")
        if cid is None:
            colors[f"__anon_{anon}"] = tc
            anon += 1
        else:
            colors[cid] = tc
    return colors


def _paragraphs(root) -> list:
    return [el for el in root.iter() if _ln(el) == "p"]


def _direct_run_text(run) -> str:
    return "".join((node.text or "") for node in run if _ln(node) == "t")


def _owned_text(paragraph) -> str:
    """이 문단 직계 run 의 글자. 중첩 표 안 문단 글자는 그 문단 것이다."""
    parts: list[str] = []
    for child in paragraph:
        if _ln(child) != "run":
            continue
        parts.append(_direct_run_text(child))
    return "".join(parts)


def _owned_lineseg(paragraph) -> int:
    """이 문단 소속 linesegarray. 중첩 문단 것은 세지 않는다."""
    count = 0

    def walk(el) -> None:
        nonlocal count
        for child in el:
            if _ln(child) == "p":
                continue
            if _ln(child) == "linesegarray":
                count += 1
            walk(child)

    walk(paragraph)
    return count


def _run_colors(paragraph, colors: dict[str, str]) -> list[str]:
    out: list[str] = []
    for child in paragraph:
        if _ln(child) != "run":
            continue
        cid = child.get("charPrIDRef") or ""
        out.append(colors.get(cid, ""))
    return out


def _guide_texts(section_root) -> list[str]:
    texts: list[str] = []
    guide_tables: list = []
    for tbl in section_root.iter():
        if _ln(tbl) == "tbl" and _is_guide_text(_text_of(tbl)):
            guide_tables.append(tbl)
            texts.append(_text_of(tbl))
    for paragraph in section_root.iter():
        if _ln(paragraph) != "p" or not _is_guide_text(_text_of(paragraph)):
            continue
        if _within_any(paragraph, guide_tables):
            continue
        texts.append(_text_of(paragraph))
    return texts


def _zip_members(names: list[str]) -> tuple[list[str], list[str]]:
    headers = [name for name in names if _HEADER_RE.search(name)]
    sections = [name for name in names if _SECTION_RE.search(name)]
    return headers, sections


def _parse_member(z: zipfile.ZipFile, name: str, report: HwpxAcceptanceReport):
    try:
        return etree.fromstring(z.read(name))
    except etree.XMLSyntaxError as exc:
        report.notes.append(f"{name} 파싱 실패(건너뜀): {exc}")
        return None


def _section_key(name: str) -> str:
    match = _SECTION_RE.search(name.replace("\\", "/"))
    return match.group(0).lower() if match else name.lower()


def _accumulate_absolute(report: HwpxAcceptanceReport, z: zipfile.ZipFile, names: list[str], allowed_names) -> None:
    for name in names:
        is_header = _HEADER_RE.search(name)
        is_section = _SECTION_RE.search(name)
        if not (is_header or is_section):
            continue
        root = _parse_member(z, name, report)
        if root is None:
            continue
        if is_header:
            colored, samples = count_colored_charpr(root)
            report.colored += colored
            _extend_capped(report.colored_samples, samples)
        else:
            guides, samples = count_form_guides(root)
            report.guides += guides
            _extend_capped(report.guides_samples, samples)
            report.linesegarray += count_linesegarray(root)
            dummy, dummy_samples = count_template_dummy_names(root, allowed=allowed_names)
            report.dummy_names += dummy
            _extend_capped(report.dummy_name_samples, dummy_samples)


def _new_charpr_colors(out_colors: dict[str, str], base_colors: dict[str, str]) -> list[str]:
    """양식에 같은 id·같은 색으로 있던 charPr 는 제외한다."""
    fresh: list[str] = []
    for cid, color in out_colors.items():
        if not _is_colored_hex(color):
            continue
        if base_colors.get(cid) == color:
            continue
        fresh.append("#" + color)
    return fresh


def _new_colored_runs(out_p, base_p, out_colors: dict[str, str], base_colors: dict[str, str]) -> list[str]:
    """채운 문단에서 양식 run 과 다른 유색만 센다.

    같은 위치 run 의 색이 양식과 같으면 글자가 바뀌어도 양식 색이다.
    새 run 이거나 검정/미지정이 유색으로 바뀐 경우만 결함이다.
    """
    out_colors_seq = _run_colors(out_p, out_colors)
    base_colors_seq = _run_colors(base_p, base_colors) if base_p is not None else []
    fresh: list[str] = []
    for index, color in enumerate(out_colors_seq):
        if not _is_colored_hex(color):
            continue
        if index < len(base_colors_seq) and base_colors_seq[index] == color:
            continue
        fresh.append("#" + color)
    return fresh


def _accumulate_against_baseline(
    report: HwpxAcceptanceReport,
    out_zip: zipfile.ZipFile,
    base_zip: zipfile.ZipFile,
    allowed_names,
) -> None:
    """양식에 있던 유색·안내·lineseg 는 결함이 아니다. 채운 문단의 잔존만 센다."""
    out_names = out_zip.namelist()
    base_names = base_zip.namelist()
    out_headers, out_sections = _zip_members(out_names)
    _base_headers, base_sections = _zip_members(base_names)
    base_sections_by_key = {_section_key(name): name for name in base_sections}

    out_colors: dict[str, str] = {}
    base_colors: dict[str, str] = {}
    for name in out_headers:
        root = _parse_member(out_zip, name, report)
        if root is not None:
            out_colors.update(_charpr_colors(root))
    for name in _base_headers:
        try:
            root = etree.fromstring(base_zip.read(name))
        except etree.XMLSyntaxError:
            continue
        base_colors.update(_charpr_colors(root))

    fresh_defs = _new_charpr_colors(out_colors, base_colors)
    report.colored += len(fresh_defs)
    _extend_capped(report.colored_samples, fresh_defs)

    for name in out_sections:
        out_root = _parse_member(out_zip, name, report)
        if out_root is None:
            continue
        base_name = base_sections_by_key.get(_section_key(name))
        base_root = None
        if base_name is not None:
            try:
                base_root = etree.fromstring(base_zip.read(base_name))
            except etree.XMLSyntaxError as exc:
                report.notes.append(f"baseline {base_name} 파싱 실패: {exc}")
        out_ps = _paragraphs(out_root)
        base_ps = _paragraphs(base_root) if base_root is not None else []
        for index, paragraph in enumerate(out_ps):
            base_p = base_ps[index] if index < len(base_ps) else None
            edited = base_p is None or _owned_text(paragraph) != _owned_text(base_p)
            if edited:
                leftover = _owned_lineseg(paragraph)
                report.linesegarray += leftover
                run_colors = _new_colored_runs(paragraph, base_p, out_colors, base_colors)
                report.colored += len(run_colors)
                _extend_capped(report.colored_samples, run_colors)
        if base_root is None:
            guides, samples = count_form_guides(out_root)
            report.guides += guides
            _extend_capped(report.guides_samples, samples)
        else:
            base_guides = _guide_texts(base_root)
            out_guides = _guide_texts(out_root)
            used = {text: base_guides.count(text) for text in set(base_guides)}
            for text in out_guides:
                if used.get(text, 0) > 0:
                    used[text] -= 1
                    continue
                report.guides += 1
                _extend_capped(report.guides_samples, [_cap(text)])
        dummy, dummy_samples = count_template_dummy_names(out_root, allowed=allowed_names)
        report.dummy_names += dummy
        _extend_capped(report.dummy_name_samples, dummy_samples)

    report.notes.append(
        "baseline: 양식에 있던 유색·안내문구·linesegarray 는 제외하고 편집 문단만 집계"
    )


def run_hwpx_acceptance(
    path: str | Path,
    *,
    allowed_names: Sequence[str] = (),
    baseline: str | Path | None = None,
) -> HwpxAcceptanceReport:
    """HWPX 산출물을 변환 없이 직접 열어 유색·안내문구·linesegarray·예시이름을 센다.

    Args:
        path: 점검할 .hwpx(ZIP/OWPML). 읽기만 하고 절대 수정하지 않는다.
        allowed_names: 채운 신원값. 이 안에 있는 더미 이름(홍길동 등)은 세지 않는다.
        baseline: 원본 양식. 주면 양식에 있던 유색 charPr·안내문구·미편집 문단의
            linesegarray 는 결함으로 세지 않는다. 편집 문단에 남은 linesegarray,
            양식에 없던 유색 run/charPr, 잔존 예시 이름은 그대로 실패다.
            생략하면 산출물 절대 개수(기존 계약).

    Returns:
        HwpxAcceptanceReport — colored/guides/linesegarray/dummy_names 개수 + ok(모두 0).

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

    base_path = Path(baseline) if baseline else None
    if base_path is not None:
        if not base_path.exists():
            raise FileNotFoundError(f"기준 양식이 없습니다: {base_path}")
        if not zipfile.is_zipfile(base_path):
            raise ValueError(f"기준 양식이 올바른 HWPX(ZIP)가 아닙니다: {base_path.name}")

    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        if base_path is None:
            _accumulate_absolute(report, z, names, allowed_names)
        else:
            with zipfile.ZipFile(base_path) as base_zip:
                _accumulate_against_baseline(report, z, base_zip, allowed_names)

    if not any(_HEADER_RE.search(n) for n in names):
        report.notes.append("Contents/header.xml 을 찾지 못했습니다(유색 텍스트 점검 생략).")
    if not any(_SECTION_RE.search(n) for n in names):
        report.notes.append("Contents/section*.xml 을 찾지 못했습니다(안내문구·겹침 점검 생략).")
    return report
