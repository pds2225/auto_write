# -*- coding: utf-8 -*-
"""hwpx_form_diff — 원본 양식↔작성본 구조/문구 대조(L070).

값 채움은 허용하고, 양식 고유 문구 삭제·구조(표/체크) 변경은 결함으로 본다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from lxml import etree

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_NS = {"hp": _HP}


@dataclass
class FormDiffReport:
    """원본 양식↔작성본 대조 결과.

    ``value_fills`` 는 빈칸이 값으로 찬 정상 변화, ``form_phrase_edits/drops`` 는
    양식 고유 문구를 고치거나 지운 결함이다.
    """

    structure_ok: bool = True
    form_phrase_edits: int = 0
    form_phrase_drops: int = 0
    value_fills: int = 0
    structure_deltas: dict[str, tuple[int, int]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def form_intact(self) -> bool:
        """양식 고유 영역 변경 0 + 구조 동일."""
        return self.structure_ok and self.form_phrase_edits == 0 and self.form_phrase_drops == 0

    def as_dict(self) -> dict[str, Any]:
        """JSON 리포트용 요약(구조 델타 튜플은 리스트로 변환)."""
        return {
            "structure_ok": self.structure_ok,
            "form_intact": self.form_intact,
            "form_phrase_edits": self.form_phrase_edits,
            "form_phrase_drops": self.form_phrase_drops,
            "value_fills": self.value_fills,
            "structure_deltas": {k: list(v) for k, v in self.structure_deltas.items()},
            "notes": list(self.notes),
        }


def _load_section(path: Path):
    with ZipFile(path) as z:
        return etree.fromstring(z.read("Contents/section0.xml"))


def _texts(sec) -> list[str]:
    return [(t.text or "") for t in sec.findall(".//hp:t", _NS)]


def _counts(sec) -> dict[str, int]:
    return {
        "표": len(sec.findall(".//hp:tbl", _NS)),
        "행": len(sec.findall(".//hp:tr", _NS)),
        "칸": len(sec.findall(".//hp:tc", _NS)),
        "문단": len(sec.findall(".//hp:p", _NS)),
        "체크박스": len(sec.findall(".//hp:checkBtn", _NS)),
    }


def compare_hwpx_forms(src: str | Path, dst: str | Path) -> FormDiffReport:
    """원본↔작성본 대조. form_intact=True 이면 양식 고유 영역 변경 0."""
    a = _load_section(Path(src))
    b = _load_section(Path(dst))
    rep = FormDiffReport()
    ca, cb = _counts(a), _counts(b)
    for k in ca:
        if ca[k] != cb[k]:
            rep.structure_ok = False
            rep.structure_deltas[k] = (ca[k], cb[k])
    ta, tb = _texts(a), _texts(b)
    sm = SequenceMatcher(None, ta, tb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old = ta[i1:i2]
        new = tb[j1:j2]
        for k in range(max(len(old), len(new))):
            o = old[k] if k < len(old) else ""
            n = new[k] if k < len(new) else ""
            if not o.strip() and n.strip():
                rep.value_fills += 1
            elif o.strip() and not n.strip():
                rep.form_phrase_drops += 1
            elif o.strip() and n.strip() and o.strip() != n.strip():
                rep.form_phrase_edits += 1
    if not rep.form_intact:
        rep.notes.append(
            f"양식 고유 변경: 수정 {rep.form_phrase_edits}·삭제 {rep.form_phrase_drops}"
            f"·구조 {'OK' if rep.structure_ok else 'DIFF'}"
        )
    return rep
