# -*- coding: utf-8 -*-
"""hwpx_form_diff — 원본 양식↔작성본 구조/문구 대조(L070).

값 채움은 허용하고, 양식 고유 문구 삭제·구조(표/체크) 변경은 결함으로 본다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
import copy
import re
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
    choice_marks: int = 0
    guidance_replacements: int = 0
    value_paragraphs: int = 0
    structure_deltas: dict[str, tuple[int, int]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def check_marks(self) -> int:
        """#218 호환 별칭: 체크박스 기호만 바뀐 정상 기입 수(= choice_marks)."""
        return self.choice_marks

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


# 선택 기호는 모두 □ 로 접어서 비교한다. □→■ 같은 체크 표시 변경은 양식 훼손이 아니라 정상 기입이다.
_CHECK_FOLD = str.maketrans({c: "□" for c in "■☑☒✔✓▣☐"})


def _check_marks_only(old: str, new: str) -> bool:
    """두 문구가 체크박스 기호만 다르면 True."""
    return old != new and old.translate(_CHECK_FOLD) == new.translate(_CHECK_FOLD)


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


def _choice_only(old, new):
    boxes = "□☐▢■☑✓▣"
    if _check_marks_only(old, new):  # #218: 체크 기호만 다른 경우(☒✔ 포함)도 정상 기입
        return True
    return old != new and len(old) == len(new) and any(c in boxes for c in old) and all(
        a == b or (a in boxes and b in boxes) for a,b in zip(old,new))


def _own_text(cell):
    return [t.text or "" for t in cell.iter(f"{{{_HP}}}t")
            if next(t.iterancestors(f"{{{_HP}}}tc"),None) is cell]


def _value_cell(cell):
    address=cell.find(f"{{{_HP}}}cellAddr")
    span=cell.find(f"{{{_HP}}}cellSpan")
    if address is None or span is None:
        return False
    row=cell.getparent()
    for sibling in row.iterchildren(f"{{{_HP}}}tc"):
        if sibling is cell:
            continue
        a=sibling.find(f"{{{_HP}}}cellAddr"); sp=sibling.find(f"{{{_HP}}}cellSpan")
        if a is None or sp is None:
            continue
        try:
            touches=int(a.get('colAddr'))+int(sp.get('colSpan'))==int(address.get('colAddr'))
            touches=touches and a.get('rowAddr')==address.get('rowAddr') and sp.get('rowSpan')==span.get('rowSpan')
        except (TypeError,ValueError):
            continue
        label=''.join(_own_text(sibling)).strip()
        if touches and label and len(label)<=40 and not re.search(r'[□■☑☐:：]',label):
            return True
    # Record values: exact header column above and a spanning row label.
    table=next(cell.iterancestors(f"{{{_HP}}}tbl"),None)
    if table is not None:
        try:
            r,c=int(address.get('rowAddr')),int(address.get('colAddr'))
            for tr in table.iterchildren(f'{{{_HP}}}tr'):
                for header in tr.iterchildren(f'{{{_HP}}}tc'):
                    a=header.find(f'{{{_HP}}}cellAddr');sp=header.find(f'{{{_HP}}}cellSpan')
                    if a is None or sp is None:continue
                    if int(a.get('rowAddr'))==r-1 and int(a.get('colAddr'))==c and sp.get('colSpan')==span.get('colSpan'):
                        text=''.join(_own_text(header)).strip()
                        labels=[tc for tc in tr.iterchildren(f'{{{_HP}}}tc') if tc.find(f'{{{_HP}}}cellSpan') is not None and int(tc.find(f'{{{_HP}}}cellSpan').get('rowSpan','1'))>1]
                        if text and len(text)<=40 and labels:return True
        except (TypeError,ValueError):
            pass
    return False


def _compare_roots(a,b):
    from core.docx.services.hwpx_protected_regions import is_value_cell_guidance
    rep=FormDiffReport()
    ca,cb=_counts(a),_counts(b)
    controls = {'checkBtn','radioBtn','edit','comboBox','listBox','button','ole','ctrl','secPr','header','footer','footNote','endNote'}
    old_controls=[etree.tostring(n,method='c14n') for n in a.iter() if etree.QName(n).localname in controls]
    new_controls=[etree.tostring(n,method='c14n') for n in b.iter() if etree.QName(n).localname in controls]
    if old_controls != new_controls:
        rep.structure_ok=False
        rep.notes.append('폼 객체/보호 영역 변경')
    masked_a,masked_b=copy.deepcopy(a),copy.deepcopy(b)
    old_cells=list(masked_a.iter(f'{{{_HP}}}tc'))
    new_cells=list(masked_b.iter(f'{{{_HP}}}tc'))
    if len(old_cells)==len(new_cells):
        for old,new in zip(old_cells,new_cells):
            # Cell addresses/spans are form geometry, not a value fill.
            for name in ('cellAddr','cellSpan'):
                oa,nb=old.find(f'{{{_HP}}}{name}'),new.find(f'{{{_HP}}}{name}')
                if (dict(oa.attrib) if oa is not None else None)!=(dict(nb.attrib) if nb is not None else None):
                    rep.structure_ok=False
                    rep.notes.append('셀 주소/병합 변경')
            ot,nt=_own_text(old),_own_text(new)
            value_cell=_value_cell(old)
            guidance=value_cell and is_value_cell_guidance("".join(ot))
            blank=value_cell and not any(t.strip() for t in ot)
            forbidden = {'tbl','ctrl','checkBtn','radioBtn','edit','comboBox','listBox','button','ole','secPr','header','footer','footNote','endNote'}
            has_form = any(etree.QName(n).localname in forbidden for cell in (old,new) for n in cell.iter() if n is not cell)
            if (guidance or blank) and not has_form and any(t.strip() for t in nt):
                op=[p for p in old.iter(f'{{{_HP}}}p') if next(p.iterancestors(f'{{{_HP}}}tc'),None) is old]
                np=[p for p in new.iter(f'{{{_HP}}}p') if next(p.iterancestors(f'{{{_HP}}}tc'),None) is new]
                if len(np)<len(op):
                    continue
                rep.value_paragraphs += len(np)-len(op)
                if guidance: rep.guidance_replacements+=1
                else: rep.value_fills+=1
                # Mask only paragraph text content, not geometry/form controls.
                for cell in (old,new):
                    for sub in cell.iterchildren(f'{{{_HP}}}subList'):
                        for p in list(sub.iterchildren(f'{{{_HP}}}p')):
                            sub.remove(p)
    for key in ca:
        allowed=(key=='문단' and cb[key]-ca[key]==rep.value_paragraphs)
        if ca[key]!=cb[key] and not allowed:
            rep.structure_ok=False
            rep.structure_deltas[key]=(ca[key],cb[key])
    ta,tb=_texts(masked_a),_texts(masked_b)
    for tag,i1,i2,j1,j2 in SequenceMatcher(None,ta,tb,autojunk=False).get_opcodes():
        if tag=='equal':continue
        old,new=ta[i1:i2],tb[j1:j2]
        for i in range(max(len(old),len(new))):
            o=old[i] if i<len(old) else ''; n=new[i] if i<len(new) else ''
            if _choice_only(o,n):rep.choice_marks+=1
            elif not o.strip() and n.strip():rep.value_fills+=1
            elif o.strip() and not n.strip():rep.form_phrase_drops+=1
            elif o.strip()!=n.strip():rep.form_phrase_edits+=1
    if rep.choice_marks:
        rep.notes.append(f"체크박스 기호 변경 {rep.choice_marks}건은 정상 기입으로 처리")
    if not rep.form_intact:
        rep.notes.append(f"양식 고유 변경: 수정 {rep.form_phrase_edits}·삭제 {rep.form_phrase_drops}·구조 {'OK' if rep.structure_ok else 'DIFF'}")
    return rep


def compare_hwpx_forms(src: str | Path, dst: str | Path) -> FormDiffReport:
    """Coordinate-scoped permitted value changes; all sections are checked."""
    rep=_compare_roots(_load_section(Path(src)),_load_section(Path(dst)))
    # Keep _load_section's long-standing test/consumer seam and as_dict keys.
    if Path(src).is_file() and Path(dst).is_file():
        with ZipFile(src) as a,ZipFile(dst) as b:
            members={n for n in a.namelist() if re.fullmatch(r'Contents/section\d+\.xml',n)}
            other={n for n in b.namelist() if re.fullmatch(r'Contents/section\d+\.xml',n)}
            if members!=other:
                rep.structure_ok=False;rep.notes.append('섹션 구성 변경')
            for member in sorted((members & other)-{'Contents/section0.xml'}):
                item=_compare_roots(etree.fromstring(a.read(member)),etree.fromstring(b.read(member)))
                rep.structure_ok &= item.structure_ok
                for counter in ('form_phrase_edits','form_phrase_drops','value_fills','choice_marks','guidance_replacements','value_paragraphs'):
                    setattr(rep,counter,getattr(rep,counter)+getattr(item,counter))
                rep.notes.extend(item.notes)
                rep.structure_deltas.update({member+':'+k:v for k,v in item.structure_deltas.items()})
    return rep
