# -*- coding: utf-8 -*-
"""hwpx_submission_cleanup — 채워진 HWPX 제출본 공통 후처리(전체 양식 공통 적용).

2026-06-29 사용자 지시("지금까지 말한 수정사항을 공통 수정방법으로 전체 양식에 적용")로 도출한
제출본 공통 원칙을 어떤 HWPX 양식에도 적용하는 결정론적 후처리. 본문 내용은 만들지 않는다(날조 0).

적용 원칙(모두 멱등):
1. strip_linesegarray   — 줄위치 캐시 제거 → 한글이 열 때 재계산(.hwpx 직접 납품 시 글씨 겹침/뭉침 방지).
2. force_black_text      — charPr 글자색 흰색(#FFFFFF)만 보존, 나머지(예시 회색/파랑/빨강) → 검정.
3. remove_form_guides    — '작성방법/작성요령/※삭제 후 제출/도식화 자료 삽입' 등 양식 안내 표·단락 제거.

표 헤더/내용행 서식 구분, ■ 제목 서식, ※ 본문 메타 제거, 쉬운 표현은 '생성 시점'(채움 코드) 책임이라
여기서는 다루지 않는다(별도 헬퍼: reformat_bullet_heading, strip_meta_notes 참고).

사용:
    from auto_write.services.hwpx_submission_cleanup import finalize_submission_hwpx
    finalize_submission_hwpx("filled.hwpx", "submit.hwpx")   # out==in 이면 ValueError
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_HEADER_RE = re.compile(r"header\.xml$", re.IGNORECASE)

# 양식 안내문구(작성요령/삭제 후 제출 지시) 시그니처 — 핵심 키워드 + 보조 키워드 동시 충족 시 제거.
_GUIDE_CORE = ("작성방법", "작성요령", "기재요령", "작성 요령")
_GUIDE_AUX = ("삭제 후 제출", "삭제후 제출", "도식화", "항목 자율", "자율 변경", "유의사항")

# 본문 작성-메타(내가 봐야 할 설명) 괄호절 — 작성태도 주석. _MetaParen.sub 으로 제거.
_META_PAREN = re.compile(
    r"\s*\([^()]*(?:단정하|단정 없|날조|과장하|과장 없|과장 차단|기정사실|두지 않|"
    r"완성이 아니라|완성 단정|채용 전제|보정 엔진 보유|미확정)[^()]*\)")


def _ln(el) -> str:
    t = getattr(el, "tag", "")
    return etree.QName(el).localname if isinstance(t, str) and "}" in t else (t or "")


def _text_of(el) -> str:
    return "".join((t.text or "") for t in el.iter() if _ln(t) == "t")


def strip_linesegarray(root, *, only_under=None) -> int:
    """줄위치 캐시(hp:linesegarray) 제거 → 한글이 열 때 줄위치를 새로 계산.

    L074: ``only_under`` 가 주어지면 그 하위만 제거(rhwp PDF 안내박스 보호).
    ``None`` 이면 종전처럼 root 전역(한글 직접 납품 최종 cleanup 용).
    """
    # hwpx_fill 과 동일 의미 — 중복 방지로 위임.
    from .hwpx_fill import _strip_linesegarray
    return _strip_linesegarray(root, only_under=only_under)


def force_black_text(header_root) -> int:
    """header.xml charPr 글자색: 흰색(#FFFFFF, 어두운 칸용)만 보존, 나머지 → 검정(#000000)."""
    n = 0
    for cp in header_root.iter():
        if _ln(cp) == "charPr":
            tc = (cp.get("textColor") or "").upper().lstrip("#")
            if tc and tc not in ("FFFFFF", "000000"):
                cp.set("textColor", "#000000")
                n += 1
    return n


def remove_form_guides(root) -> int:
    """'작성방법 ※삭제 후 제출 …' 등 양식 안내 표/단락 제거(양식이 '삭제 후 제출' 명시)."""
    def is_guide(txt: str) -> bool:
        return any(c in txt for c in _GUIDE_CORE) and any(a in txt for a in _GUIDE_AUX)

    n = 0
    for tbl in list(root.iter()):
        if _ln(tbl) == "tbl" and is_guide(_text_of(tbl)):
            par = tbl.getparent()
            if par is not None:
                par.remove(tbl)
                n += 1
    for p in list(root.iter()):
        if _ln(p) == "p" and is_guide(_text_of(p)):
            par = p.getparent()
            if par is not None:
                par.remove(p)
                n += 1
    return n


def strip_meta_notes(text: str) -> str:
    """본문 문자열에서 작성-메타 제거(생성 시점용 헬퍼): ① ※ 안내줄 ② 작성태도 괄호절."""
    text = "\n".join(ln for ln in text.split("\n") if not ln.lstrip().startswith("※"))
    return _META_PAREN.sub("", text)


def reformat_bullet_heading(line: str) -> str:
    """■ 제목 서식 통일(생성 시점용 헬퍼): '■ 라벨 — 설명'/'■ 라벨(부제)' → '■ (라벨)'."""
    s = line.strip()
    if not s.startswith("■"):
        return line
    body = s[1:].strip()
    for dash in (" — ", " — ", " – ", " - "):
        if dash in body:
            body = body.split(dash, 1)[0].strip()
            break
    if "(" in body:
        body = body.split("(", 1)[0].strip()
    return "■ (%s)" % body.strip("()").strip()


def finalize_submission_hwpx(in_path, out_path, *, force_black=True,
                             remove_guides=True, strip_lineseg=True) -> dict:
    """채워진 HWPX 제출본에 공통 후처리를 적용해 out_path 로 저장. 원본 보존(out==in 금지)."""
    in_path, out_path = Path(in_path), Path(out_path)
    if in_path.resolve() == out_path.resolve():
        raise ValueError("원본 덮어쓰기 금지: 출력 경로가 입력과 같습니다.")

    with zipfile.ZipFile(in_path) as zin:
        infos = zin.infolist()
        store = {i.filename: zin.read(i.filename) for i in infos}

    stats = {"linesegarray_removed": 0, "guides_removed": 0, "charpr_blacked": 0}
    for name, data in list(store.items()):
        if _SECTION_RE.search(name):
            root = etree.fromstring(data)
            if remove_guides:
                stats["guides_removed"] += remove_form_guides(root)
            if strip_lineseg:
                stats["linesegarray_removed"] += strip_linesegarray(root)
            store[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        elif _HEADER_RE.search(name) and force_black:
            hroot = etree.fromstring(data)
            stats["charpr_blacked"] += force_black_text(hroot)
            store[name] = etree.tostring(hroot, xml_declaration=True, encoding="UTF-8", standalone=True)

    with zipfile.ZipFile(out_path, "w") as zout:
        if "mimetype" in store:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, store["mimetype"])
        for info in infos:
            if info.filename == "mimetype":
                continue
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zout.writestr(zi, store[info.filename])
    return stats
