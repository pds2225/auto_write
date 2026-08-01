"""hwpx_form_extract — 공고+서식 HWPX에서 서식만 분리(L037).

공고 본문(모집요강·수당·자격요건 표 등)을 제거하고 ``[서식 1]``(또는
동의어 마커)부터 끝까지 남긴 HWPX를 만든다. COM 없음(RHWP).
원본 미수정 · out==in 금지.
"""

from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from .hwpx_fill import _same_file

_STANDALONE_RE = re.compile(rb"standalone\s*=\s*['\"](yes|no)['\"]")
_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)

# 서식 시작 마커(앞에서부터 첫 일치)
_FORM_START_MARKERS = (
    "[서식 1]",
    "[서식1]",
    "서식 1.",
    "참여 신청서",
)


@dataclass
class FormExtractReport:
    input: str
    output: str = ""
    ok: bool = False
    start_index: int = -1
    marker: str = ""
    kids_before: int = 0
    kids_after: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "ok": self.ok,
            "start_index": self.start_index,
            "marker": self.marker,
            "kids_before": self.kids_before,
            "kids_after": self.kids_after,
            "notes": self.notes,
        }


def _detect_standalone(xml_bytes: bytes) -> Optional[bool]:
    m = _STANDALONE_RE.search(xml_bytes[:200])
    if not m:
        return None
    return m.group(1) == b"yes"


def find_form_start_index(root) -> tuple[int, str]:
    """섹션 루트 직계 자식 중 서식 시작 인덱스와 매칭 마커.

    ``[서식 1]`` 를 최우선으로 찾고, 없으면 ``서식 1.`` /
    제목형 ``참여 신청서``(접수목록·1부 안내 제외)로 폴백한다.
    """
    kids = list(root)
    # 1) 명시적 [서식 1]
    for i, kid in enumerate(kids):
        text = "".join(kid.itertext())
        if "[서식 1]" in text or "[서식1]" in text:
            return i, "[서식 1]"
    # 2) "서식 1." 목록 헤더(본문 직전)
    for i, kid in enumerate(kids):
        text = "".join(kid.itertext()).strip()
        if text.startswith("서식 1.") or text.startswith("서식1."):
            return i, "서식 1."
    # 3) 신청서 제목 표/단락 — 접수서류 목록('- … 1부') 제외
    for i, kid in enumerate(kids):
        text = "".join(kid.itertext())
        if "참여 신청서" not in text:
            continue
        if "1부" in text or "모집공고" in text or text.strip().startswith("-"):
            continue
        if "전문분야" in text or "성명" in text or text.strip().endswith("신청서"):
            return i, "참여 신청서"
    return -1, ""


def extract_forms_only(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    *,
    section_name: str = "Contents/section0.xml",
) -> FormExtractReport:
    """공고+서식 HWPX → 서식만 HWPX."""
    src, dst = Path(in_hwpx), Path(out_hwpx)
    rep = FormExtractReport(input=str(src), output=str(dst))
    if not src.is_file():
        rep.notes.append("입력 파일 없음")
        return rep
    if _same_file(src, dst):
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")

    dst.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(src, "r") as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}

    if section_name not in data:
        # 첫 section*.xml 사용
        secs = [n for n in names if _SECTION_RE.search(n)]
        if not secs:
            rep.notes.append("section*.xml 없음")
            return rep
        section_name = sorted(secs)[0]

    root = etree.fromstring(data[section_name])
    start, marker = find_form_start_index(root)
    kids = list(root)
    rep.kids_before = len(kids)
    if start < 0:
        rep.notes.append(
            "서식 시작 마커를 찾지 못했습니다 "
            f"({', '.join(_FORM_START_MARKERS)}). 원본을 복사만 합니다."
        )
        # 마커 없으면 복사(실패로 보고하되 파일은 생성)
        import shutil

        shutil.copyfile(src, dst)
        rep.ok = False
        return rep

    for kid in kids[:start]:
        root.remove(kid)
    rep.start_index = start
    rep.marker = marker
    rep.kids_after = len(list(root))

    standalone = _detect_standalone(data[section_name])
    data[section_name] = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=standalone
    )

    tmp = dst.with_suffix(dst.suffix + ".part")
    with zipfile.ZipFile(tmp, "w") as zout:
        # mimetype STORED first if present
        if "mimetype" in data:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, data["mimetype"])
        for name in names:
            if name == "mimetype":
                continue
            zout.writestr(name, data[name])
    os.replace(tmp, dst)
    rep.ok = True
    rep.notes.append(f"마커 '{marker}' @ index {start}: {rep.kids_before}→{rep.kids_after} nodes")
    return rep


def looks_like_notice_blob(text: str) -> bool:
    """채움 산출물에 공고 본문이 남아 있는지 휴리스틱."""
    keys = ("모집공고", "수당지급", "위촉기간", "접수기간", "모집인원")
    return sum(1 for k in keys if k in text) >= 2
