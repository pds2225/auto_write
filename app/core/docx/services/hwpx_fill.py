"""hwpx_fill.py — HWPX 원본 양식을 '변환 왕복 없이' 직접 채우는 결정론 엔진.

목적 / 배경
-----------
정부지원사업 양식은 대개 HWP/HWPX 다. 기존 경로(``hwp_fill``)는
HWPX→DOCX→채움→DOCX→HWP 로 **변환을 왕복**하기 때문에 표·서식·이미지가
미세하게 틀어질 수 있었다(변환 일치도 100% 미달 = 평생개발목표 진행 중).

이 모듈은 변환을 전혀 하지 않는다. HWPX 가 본질적으로 ZIP(OWPML XML) 이라는 점을
이용해, 압축을 풀고 ``Contents/section*.xml`` 의 **값 칸 텍스트(hp:t)만** 바꾼 뒤
다시 압축한다. 표 구조·셀 속성·테두리/채우기·이미지(BinData) 는
**한 바이트도 건드리지 않는다** → 원본 양식 100% 보존 + 값만 입력.
글꼴(header.xml)은 원칙적으로 불변이나, 채운 값이 유색 예시체를 승계하는 것을
막기 위해 **'검정 클론' charPr 추가만** 허용한다(기존 항목은 절대 수정하지 않음
— force_black 참조, 실측: 수원 멘토위원 신청서 파란 예시체 상속 결함).

OWPML 표 구조(실측)
-------------------
``hp:tbl > hp:tr > hp:tc``. 각 ``hp:tc`` 는 ``hp:cellAddr``(colAddr/rowAddr)·
``hp:cellSpan``(colSpan/rowSpan) + ``hp:subList > hp:p > hp:run > hp:t``(텍스트).
값 칸은 **라벨 칸의 colAddr+colSpan 위치**(논리 그리드 오른쪽 이웃)로 찾는다 —
병합셀(colSpan>1)·다열(라벨-값-라벨-값) 양식에서도 엉뚱한 칸을 안 채운다.

안전 원칙(불변)
---------------
- **원본 미수정**: out==in 이면 ValueError. ``os.path.samefile``(inode) 로 하드링크·
  심링크·대소문자·상대경로 우회까지 차단. 입력 ZIP 은 읽기만 한다.
- **원자적 쓰기**: 임시파일에 쓰고 성공 시 ``os.replace`` 로 교체 — 중간 실패가
  기존 출력 파일을 손상시키지 않는다.
- **양식 보존**: 값 칸의 ``hp:t`` 텍스트만 수정. 그 외 모든 ZIP 엔트리는 내용 동일.
  mimetype 은 ZIP 선두 + 무압축(STORED) 으로 유지(HWPX 유효성 요건).
- **날조 0**: 사용자가 준 identity/replacements 값만 입력한다. 없으면 안 채운다.
- **덮어쓰기 금지**: 비었거나 '명백한 예시 플레이스홀더'인 칸에만 입력한다.
  실제 값이 든 칸·라벨 칸은 절대 덮지 않는다(오매칭<빈칸<덮어쓰기).
  실값 때문에 건너뛴 identity 는 ``[existing] … EXISTING_VALUE`` 로 남긴다.
  replacements(직접 치환)도 채울 수 있는 칸 안에서만 적용한다(라벨/실값 보호).
- AI 호출 없음 — 동일 입력, 동일 결과(결정론).

매칭 지능은 ``cross_form_autofill`` 에서 그대로 가져온다(단일 출처):
``_key``·``_cluster_rep``·``_is_obvious_placeholder``·``_is_noise_label``.
"""

from __future__ import annotations

import copy
import hashlib
import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from .cross_form_autofill import (
    _ANY_BOX_RE,
    _CHECK_MARK,
    _EMPTY_BOX_RE,
    _cluster_rep,
    _is_fill_blank,
    _is_noise_label,
    _is_obvious_placeholder,
    _is_visible_blank,
    _iter_line_fields,
    _key,
    _normalize_choice,
    _option_text,
)

# OWPML 단락 네임스페이스(본문/표/텍스트 전부 hp:).
_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_STANDALONE_RE = re.compile(rb"standalone\s*=\s*['\"](yes|no)['\"]")


def _q(tag: str) -> str:
    return f"{{{_HP}}}{tag}"


def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _direct(el, name: str) -> list:
    """el 의 '직계' 자식 중 local-name 이 name 인 것."""
    return [c for c in el if _local(getattr(c, "tag", "")) == name]


def _cell_texts(tc) -> list:
    """이 셀 직속의 hp:t. 중첩 표 안 글자는 자식 칸의 것이다."""
    return [el for el in tc.iter(_q("t")) if _nearest_cell(el) is tc]


def _cell_has_nested_table(tc) -> bool:
    """이 칸이 자식 표를 품으면 True. 더 안쪽 칸의 표는 그 칸 것이다."""
    if tc is None:
        return False
    return any(_nearest_cell(tbl) is tc for tbl in tc.iter(_q("tbl")))


def _hold_exact_label(held: set | None, cell_key: str, want_key: str) -> None:
    """정확히 맞는 라벨 칸을 거절했을 때, 그 항목이 다른 라벨로 새지 않게 한다.

    같은 라벨의 다른 빈 칸(반복 행)은 그대로 둔다. 동의어 칸은 자기 항목으로만 채운다.
    """
    if held is not None and cell_key == want_key:
        held.add(want_key)


def _held_for_other_label(held: set | None, cell_key: str, want_key: str) -> bool:
    return bool(held) and want_key in held and cell_key != want_key


def _cell_text(tc) -> str:
    """셀의 표시 텍스트(hp:t 결합, 공백 정규화)."""
    parts = [str(el.text or "") for el in _cell_texts(tc)]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _split_value_spans(tc) -> bool:
    """값 글자가 둘 이상의 hp:t 에 나뉘어 있으면 True.

    ``_set_cell_text`` 는 첫 hp:t 에 값을 넣고 나머지 hp:t 를 비운다.
    공백이 아닌 글자가 뒤 span 에 있거나, 그 글자가 첫 span 이 아니면
    형제 run 을 지우거나 빈 span 으로 합친다. 그 칸은 기입하지 않는다.
    전부 비어 있는 추가 hp:t 는 기존 빈 칸 기입을 막지 않는다.
    """
    nodes = _cell_texts(tc)
    if len(nodes) <= 1:
        return False
    meaningful = [
        index for index, node in enumerate(nodes) if (node.text or "").strip()
    ]
    if len(meaningful) >= 2:
        return True
    return bool(meaningful) and meaningful[0] != 0


def _note_unfilled_span(bucket: list, label: str, tc=None) -> None:
    """run/span 경계 때문에 안 채운 칸을 residual 과 별도로 남긴다."""
    _note_region(bucket, "span", label, tc)


def _real_existing_text(text: str) -> bool:
    """Real prose or numbers. Empty scaffolds and fill-in placeholders are not.

    Obvious placeholders (``0000년 00월 00일``, ``000-00-00000``, ``000억원``),
    underscore blanks, date scaffolds, and choice marks stay on their own gates.
    HWPX example masks (``OOO``, ``000-0000-0000``, ``OO도 OO시·군``) are not real.
    """
    raw = str(text or "")
    if not raw.strip():
        return False
    if _is_obvious_placeholder(raw) or _is_fill_blank(raw) or _is_hwpx_example_scaffold(raw):
        return False
    from core.docx.services.hwpx_protected_regions import (
        _CHOICE_MARK_RE,
        _is_date_scaffold_paragraph,
    )
    if _is_date_scaffold_paragraph(raw) or _CHOICE_MARK_RE.search(raw):
        return False
    return True


def _note_existing_value(bucket: list, label: str, tc=None, labels: list | None = None) -> None:
    """Record a skipped write when the cell already holds a real value."""
    row = col = None
    if tc is not None:
        addr = next(iter(_direct(tc, "cellAddr")), None)
        if addr is not None:
            if addr.get("rowAddr") is not None:
                row = _int_attr(addr, "rowAddr", -1)
            if addr.get("colAddr") is not None:
                col = _int_attr(addr, "colAddr", -1)
    shown = str(label or "value")
    if row is not None and col is not None:
        note = f"[existing] {shown} row={row} col={col} EXISTING_VALUE"
    else:
        note = f"[existing] {shown} EXISTING_VALUE"
    if note not in bucket:
        bucket.append(note)
    if labels is not None and label and label not in labels:
        labels.append(label)


# 손글씨·도장 이미지. line/rect 는 빈칸 밑줄로 자주 쓰이므로 여기 넣지 않는다.
_HANDWRITTEN_OBJECT_TAGS = ("pic", "ole", "drawText", "textart")
_SEAL_PAREN_RE = re.compile(
    r"[\(（]\s*(?:서명|날인|직인|인감|인|印|署名|捺印|도장|sign|seal)\s*[\)）]",
    re.IGNORECASE,
)


def _note_region(bucket: list, kind: str, label: str, tc=None) -> None:
    """안 채운 칸의 이유를 ``[kind] … UNFILLED`` 로 남긴다."""
    row = col = None
    if tc is not None:
        addr = next(iter(_direct(tc, "cellAddr")), None)
        if addr is not None:
            if addr.get("rowAddr") is not None:
                row = _int_attr(addr, "rowAddr", -1)
            if addr.get("colAddr") is not None:
                col = _int_attr(addr, "colAddr", -1)
    if row is not None and col is not None:
        note = f"[{kind}] {label} row={row} col={col} UNFILLED"
    else:
        note = f"[{kind}] {label} UNFILLED"
    if note not in bucket:
        bucket.append(note)


def _nearest_cell(el):
    cur = el
    while cur is not None:
        if _local(getattr(cur, "tag", "")) == "tc":
            return cur
        cur = cur.getparent()
    return None


def _has_handwritten_object(tc) -> bool:
    """이 셀 자신의 그림·OLE·글상자가 있으면 True. 중첩 표 안 객체는 제외."""
    if tc is None:
        return False
    for name in _HANDWRITTEN_OBJECT_TAGS:
        for el in tc.iter(_q(name)):
            if _nearest_cell(el) is tc:
                return True
    return False


def _signature_seal_label(text: str) -> bool:
    """서명·날인·직인 칸. ``부서명``·``겸직인력``·``성명 (서명)`` 은 제외.

    괄호 안 도장 표시를 뺀 뒤에 남은 라벨만 본다. ``성명 (서명)`` 의 값칸은
    이름 칸이고, ``서명`` / ``서명 : ______`` 은 서명 칸이다.
    """
    stripped = _SEAL_PAREN_RE.sub("", str(text or ""))
    compact = re.sub(r"\s+", "", stripped).rstrip(":：_")
    if not compact:
        return bool(str(text or "").strip())
    without_department = compact.replace("부서명", "")
    if "서명" in without_department or "날인" in without_department:
        return True
    without_concurrent = compact.replace("겸직인", "")
    if "직인" in without_concurrent:
        return True
    if "인감" in compact and "인감증명" not in compact:
        return True
    return False


def _int_attr(el, name: str, default: int) -> int:
    if el is None:
        return default
    try:
        return int(str(el.get(name)))
    except (TypeError, ValueError):
        return default


# L097: 한 줄 칸 폭 추정. 1pt ≈ 100 HWPUNIT (7200/72). 한글 1em, ASCII 0.5em.
_HWPUNIT_PER_PT = 100
_DEFAULT_CELL_FONT_PT = 10
_ONE_LINE_HEIGHT_HWPUNIT = int(_DEFAULT_CELL_FONT_PT * _HWPUNIT_PER_PT * 1.6)


def estimate_text_width_hwpunit(text: str, font_pt: int = _DEFAULT_CELL_FONT_PT) -> int:
    """셀에 넣을 문자열의 대략 폭(HWPUNIT). 한글·전각=1em, ASCII=0.5em."""
    em = max(1, int(font_pt) * _HWPUNIT_PER_PT)
    width = 0
    for ch in str(text or "").replace("\n", ""):
        width += em if ord(ch) > 0x7F else em // 2
    return width


def cell_text_may_overflow(tc, value: str) -> bool:
    """한 줄로 잠긴 칸에 값이 폭을 넘치면 True. cellSz 없으면 측정 불가 → False.

    채움을 막지 않는다(데이터 손실 금지). 호출자가 overflow_cells 에 기록만 한다.
    """
    if not str(value or "").strip():
        return False
    sz = next(iter(_direct(tc, "cellSz")), None)
    if sz is None:
        return False
    width = _int_attr(sz, "width", 0)
    height = _int_attr(sz, "height", 0)
    if width <= 0:
        return False
    text_w = estimate_text_width_hwpunit(value)
    if text_w <= width:
        return False
    if 0 < height < _ONE_LINE_HEIGHT_HWPUNIT:
        return True
    return text_w > width * 3


def _note_overflow(bucket: Optional[list], label: str, tc, value: str) -> None:
    if bucket is None or not cell_text_may_overflow(tc, value):
        return
    shown = str(value).replace("\n", " ")[:24]
    bucket.append(f"{label}={shown}")


def _cell_addr(tc) -> Optional[int]:
    """셀의 논리 열 위치(colAddr). cellAddr 미지정이면 None."""
    ca = next(iter(_direct(tc, "cellAddr")), None)
    if ca is None:
        return None
    return _int_attr(ca, "colAddr", -1) if ca.get("colAddr") is not None else None


def _cell_colspan(tc) -> int:
    cs = next(iter(_direct(tc, "cellSpan")), None)
    return _int_attr(cs, "colSpan", 1)


def _row_of(tc):
    """tc 의 조상 hp:tr."""
    cur = tc.getparent()
    while cur is not None:
        if _local(getattr(cur, "tag", "")) == "tr":
            return cur
        cur = cur.getparent()
    return None


# 양식 폼 컨트롤 요소(OWPML) — 이 중 하나라도 든 칸은 텍스트 채움 대상이 아니다.
_FORM_CONTROL_TAGS = ("checkBtn", "radioBtn", "comboBox", "edit", "listBox", "btn")


def _has_form_control(tc) -> bool:
    """셀 안에 폼 컨트롤(체크박스·라디오·입력필드 등)이 있으면 True.

    컨트롤 칸은 텍스트가 비어 보여도 '빈칸'이 아니다 — 글자를 기입하면 컨트롤과
    겹쳐 이중 표시된다(실측: 수원 멘토위원 신청서 ☐ 옆 ■). 체크는 컨트롤의
    value 속성으로 해야 한다(check_options 참조).
    """
    for name in _FORM_CONTROL_TAGS:
        for _ in tc.iter(_q(name)):
            return True
    return False


def _direct_form_checkbtns(tc) -> list:
    """이 셀 '자신'에 속한 hp:checkBtn 목록(중첩 표 내부 것은 제외).

    가장 가까운 조상 hp:tc 가 tc 자신인 것만 취한다 — 셀 안 중첩 표의 컨트롤을
    바깥 셀 것으로 오인해 엉뚱한 체크박스를 켜는 것을 막는다.
    """
    out = []
    for btn in tc.iter(_q("checkBtn")):
        cur = btn.getparent()
        owner = None
        while cur is not None:
            if _local(getattr(cur, "tag", "")) == "tc":
                owner = cur
                break
            cur = cur.getparent()
        if owner is tc:
            out.append(btn)
    return out


def _opt_key_preserving(s: str) -> str:
    """폼컨트롤 체크 매칭용 '괄호 보존' 키 — 공백 제거 + 꼬리 구두점만 벗김.

    ``_opt_key``(→``_key``)는 괄호 내용을 통째로 지워 '동의(필수)'/'동의(선택)'을
    동일시하고, ``_normalize_choice`` 는 주식회사/유한회사를 전부 '법인'으로 환원해
    '유한회사' 요청이 '주식회사' 박스를 켜는 오체크를 만든다(적대검증 실측 재현).
    폼컨트롤 체크의 입력은 사용자가 양식에서 보고 지정한 '옵션 라벨'이므로
    환원 없이 괄호 보존 정확일치만 쓴다(오체크<미체크).
    """
    return re.sub(r"\s+", "", str(s or "")).rstrip(_OPT_TRAIL_PUNCT)


def _checkbtn_label(tc, cells) -> str:
    """checkBtn 컨트롤 셀의 옵션 라벨 — 같은 셀 캡션 1순위, 오른쪽 인접 셀 2순위.

    오른쪽 이웃 셀이 또 폼컨트롤 셀이면(컨트롤 연속 그리드·같은셀 캡션 배치)
    라벨로 인정하지 않는다 — '오른쪽 이웃=라벨' 단정이 한 칸 옆의 엉뚱한
    박스를 켜던 결함(적대검증 실측 재현) 차단. 라벨을 못 정하면 ""(후보 제외).
    """
    own = _cell_text(tc)
    if own:
        return own
    label_tc = _value_cell(tc, cells)
    if label_tc is None or label_tc is tc or _has_form_control(label_tc):
        return ""
    return _cell_text(label_tc)


def _is_black_color(color: Optional[str]) -> bool:
    """textColor 값이 '검정으로 렌더링되는' 값인가(미지정·auto 포함)."""
    c = (color or "").strip().upper().lstrip("#")
    return c in ("", "000000", "AUTO", "NONE")


def _charpr_is_italic(el) -> bool:
    """charPr 가 기울임이면 True. 속성 italic 과 hh:italic 자식을 함께 본다."""
    flag = (el.get("italic") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    for sub in el:
        if _local(getattr(sub, "tag", "")) != "italic":
            continue
        val = (sub.get("val") or sub.get("value") or "1").strip().lower()
        if val not in ("0", "false", "no"):
            return True
    return False


def _clear_italic(el) -> None:
    """클론에서 기울임을 끈다. 원본 charPr 는 호출 전에 복사돼 있어야 한다."""
    if el.get("italic") not in (None, "", "0", "false", "FALSE"):
        el.set("italic", "0")
    for sub in list(el):
        if _local(getattr(sub, "tag", "")) == "italic":
            el.remove(sub)


class _BlackCharPr:
    """헤더 charPr 색 지도 + '검정 클론' 관리 — 유색 예시체 상속 차단.

    양식의 예시 문구(파란 안내체 등)가 든 칸을 교체하거나 그 행의 서식을
    승계하면 채운 값이 유색으로 들어간다(실측: 수원 멘토위원 신청서 학력·경력
    값 전부 파랑 = 제출본 검정 원칙 위반). 유색 charPr 를 만나면 글꼴·크기는
    그대로 두고 textColor 만 #000000 인 클론을 헤더에 '추가'해 그 id 로
    갈아끼운다 — 기존 charPr·다른 유색 요소(제목 등)는 절대 수정하지 않는다.
    헤더가 없거나 charPr 색 정보가 없으면 완전 no-op(기존 동작 보존).
    """

    def __init__(self, header_root=None) -> None:
        self.root = header_root
        self.colors: dict[str, str] = {}
        self.changed = False
        self._byid: dict[str, Any] = {}
        self._clones: dict[str, str] = {}
        if header_root is None:
            return
        for el in header_root.iter():
            if _local(getattr(el, "tag", "")) == "charPr" and el.get("id"):
                self._byid[el.get("id")] = el
                self.colors[el.get("id")] = el.get("textColor") or ""

    def is_black(self, ref: Optional[str]) -> bool:
        if not self.colors:
            return True  # 색 정보 없음(헤더 부재/무색 헤더) → 관여하지 않음
        return _is_black_color(self.colors.get(ref or ""))

    def is_italic(self, ref: Optional[str]) -> bool:
        el = self._byid.get(ref or "")
        return el is not None and _charpr_is_italic(el)

    def needs_body(self, ref: Optional[str]) -> bool:
        """유색이거나 기울임이면 본문 스타일(검정·정자체)로 바꿔야 한다."""
        if not self._byid:
            return False
        return (not self.is_black(ref)) or self.is_italic(ref)

    def black_ref(self, ref: str) -> str:
        """ref 가 안내 스타일(유색·기울임)이면 본문 클론 id, 아니면 ref 그대로."""
        if not self.needs_body(ref):
            return ref
        if ref in self._clones:
            return self._clones[ref]
        orig = self._byid.get(ref)
        if orig is None:
            return ref
        numeric = [int(k) for k in self._byid if str(k).isdigit()]
        if not numeric:
            return ref  # 숫자 id 체계가 아니면 보수적으로 포기(무변경)
        new_id = str(max(numeric) + 1)
        clone = copy.deepcopy(orig)
        clone.set("id", new_id)
        clone.set("textColor", "#000000")
        _clear_italic(clone)
        # 하위 색 속성도 정규화(적대검증 D6): 유색 예시체는 밑줄·취소선·그림자
        # 색이 글자색과 동색(#0000FF 밑줄 실측 106건)이거나 형광 배경(shadeColor)을
        # 갖는 경우가 있어 textColor 만 바꾸면 '검정 글자+파란 밑줄/노란 배경'이 남는다.
        if clone.get("shadeColor") not in (None, "", "none", "NONE"):
            clone.set("shadeColor", "none")
        for sub in clone.iter():
            if _local(getattr(sub, "tag", "")) in ("underline", "strikeout", "shadow") \
                    and sub.get("color"):
                sub.set("color", "#000000")
        parent = orig.getparent()
        if parent is None:
            return ref
        parent.append(clone)
        cnt = parent.get("itemCnt")
        if cnt and str(cnt).isdigit():
            parent.set("itemCnt", str(int(cnt) + 1))
        self._byid[new_id] = clone
        self.colors[new_id] = "#000000"
        self._clones[ref] = new_id
        self.changed = True
        # L076: 클론은 반드시 append — 삽입 후 id/인덱스 불변 검증.
        from .hwpx_charpr_guard import assert_charpr_append_only
        assert_charpr_append_only(self.root)
        return new_id

    def fix_run(self, run) -> bool:
        """run 의 charPr 가 유색·기울임이면 본문 클론으로 교체. 바꿨으면 True."""
        ref = run.get("charPrIDRef")
        if ref is None or not self.needs_body(ref):
            return False
        new_ref = self.black_ref(ref)
        if new_ref == ref:
            return False
        run.set("charPrIDRef", new_ref)
        return True


def _inherit_charpr(tc, black: Optional[_BlackCharPr] = None) -> str:
    """빈 칸에 run 을 새로 만들 때 승계할 charPrIDRef.

    같은 행의 기존 run 글자속성을 재사용해 양식 폰트를 보존한다. 없으면 '0'.
    black 이 주어지면 행 안에서 '검정' run 을 우선 고른다 — 예시행처럼 유색
    run 뿐이면 첫 run 의 검정 클론을 쓴다(유색 상속 차단).
    """
    row = _row_of(tc)
    scope = row if row is not None else tc
    first = None
    for run in scope.iter(_q("run")):
        ref = run.get("charPrIDRef")
        if not ref:
            continue
        if first is None:
            first = ref
        if black is None or not black.needs_body(ref):
            return ref
    if first is not None:
        return first if black is None else black.black_ref(first)
    # 폴백 '0' 도 검정 검사를 거친다(적대검증 D8) — 실코퍼스에 id 0 이
    # #0000FF(013 딥테크)·#FFFFFF(012 K-Convergence, 흰 글자=비가시)인 양식 실재.
    return "0" if black is None else black.black_ref("0")


def _set_cell_text(tc, value: str, black: Optional[_BlackCharPr] = None, *, replace_scaffold: bool = False) -> bool:
    """셀의 텍스트를 value 로 설정한다(첫 hp:t 에 기입, 나머지 hp:t 는 비움).

    빈/플레이스홀더 칸에만 호출되므로 잔여 hp:t 를 비워도 실데이터 손실은 없다.
    다만 공백이 아닌 글자가 첫 hp:t 가 아닌 span 에 있거나 여러 span 에 나뉘면
    False 를 반환하고 아무 글자도 바꾸지 않는다(형제 run 보존).
    hp:t/hp:run 이 없으면 단락 서식(charPrIDRef 승계)을 유지하며 최소 생성한다.
    black 이 주어지면 값이 들어간 run 의 유색 charPr 를 검정 클론으로 바꾼다.

    L086: 폼 컨트롤(checkBtn 등)이 든 칸에는 텍스트를 절대 기입하지 않는다 —
    ``_cell_is_fillable`` 우회·resume 경로에서도 이중 표시를 막기 위한 최종 방어핀.
    그림·OLE·글상자(손글씨/도장)가 있는 칸도 같은 이유로 기입하지 않는다.

    L002/L145: 기입에 성공하면 그 칸의 ``hp:linesegarray`` 를 즉시 제거한다.
    호출자가 ``fill_hwpx`` 파이프라인·별도 strip 을 잊어도 옛 줄좌표에 새 글씨가
    겹치지 않는다. 형제 칸은 건드리지 않는다(L074).
    """
    if _has_form_control(tc) or _has_handwritten_object(tc) or _cell_has_nested_table(tc):
        return False
    if _split_value_spans(tc) and (
        not replace_scaffold or _date_placeholder_crosses_spans(tc)
    ):
        return False
    paras = list(tc.iter(_q("p")))
    if not paras:
        return False
    p = paras[0]
    ts = _cell_texts(tc)
    if ts:
        ts[0].text = value
        for extra in ts[1:]:
            extra.text = ""
        if black is not None:
            run = ts[0].getparent()
            if run is not None and _local(getattr(run, "tag", "")) == "run":
                black.fix_run(run)
        _invalidate_lineseg(tc)
        return True
    runs = list(p.iter(_q("run")))
    if runs:
        run = runs[0]
        if black is not None:
            black.fix_run(run)
    else:
        run = etree.SubElement(p, _q("run"))
        run.set("charPrIDRef", _inherit_charpr(tc, black))
    t = etree.SubElement(run, _q("t"))
    t.text = value
    _invalidate_lineseg(tc)
    return True


def _inline_texts(p) -> list:
    """hp:p 의 '직계 텍스트 흐름' hp:t 목록(문서순).

    p 의 직계 hp:run 들만 순회하고, run 이 중첩 표(hp:tbl)를 품으면 그 run 은
    통째로 건너뛴다 — 중첩 표/subList 텍스트를 인라인 흐름에 흡수하지 않는다(AC8).
    각 run 에서는 '직계' hp:t 만 취한다. flat 문자열 빌드와 offset→hp:t 매핑이
    반드시 이 함수의 동일 결과를 공유해야 offset 이 어긋나지 않는다(AC9).
    """
    texts: list = []
    for run in _direct(p, "run"):
        if _direct(run, "tbl"):
            continue
        texts.extend(_direct(run, "t"))
    return texts


def _locate_inline_span(p, fill_start: int, fill_end: int):
    """flat 구간이 걸친 (start hp:t, offset, end hp:t, offset). 못 찾으면 None."""
    ts = _inline_texts(p)
    pos = 0
    start_t = start_off = end_t = end_off = None
    for t in ts:
        s = t.text or ""
        if start_t is None and fill_start < pos + len(s):
            start_t, start_off = t, fill_start - pos
        if fill_end <= pos + len(s):
            end_t, end_off = t, fill_end - pos
            break
        pos += len(s)
    return start_t, start_off, end_t, end_off


def _span_crosses_text_nodes(p, fill_start: int, fill_end: int) -> bool:
    """채울 구간이 둘 이상의 hp:t(run 또는 같은 run 의 문자 span)에 걸치면 True."""
    start_t, _, end_t, _ = _locate_inline_span(p, fill_start, fill_end)
    return start_t is not None and end_t is not None and start_t is not end_t


def _splice_run_text(p, fill_start: int, fill_end: int, value: str) -> bool:
    """p 직계 텍스트 흐름의 flat 문자 구간 [fill_start, fill_end) 만 value 로 교체.

    형제 run/hp:t 의 텍스트·charPrIDRef 는 전부 보존한다(대상 hp:t 의 text 만 수정).
    flat 문자열은 _inline_texts(p) 의 text 를 공백 정규화 없이 그대로 이어붙인 것과
    동일해야 한다. 구간이 두 hp:t 에 걸치면(cross-run/span) 채우지 않고 False
    (오채움<빈칸 — 보수적 skip).
    """
    start_t, start_off, end_t, end_off = _locate_inline_span(p, fill_start, fill_end)
    if start_t is None or end_t is None:
        return False
    if start_t is not end_t:
        return False  # cross-run span: 보수적 skip(오채움<빈칸)
    cur = start_t.text or ""
    start_t.text = cur[:start_off] + value + cur[end_off:]
    _invalidate_lineseg(p)
    return True


def _fill_inline_fields_in_p(
    p, wants, used_keys: set, filled: dict, span_notes: Optional[list] = None,
    existing_labels: Optional[list] = None,
    exact_held: Optional[set] = None,
) -> bool:
    """hp:p 하나의 인라인 필드(`라벨 : ______`)를 채운다 — 1.5(셀)·1.8(본문) 공용 커널.

    '가시 빈칸'(밑줄/점/대시 채움선)만 채운다(_is_visible_blank) — '라벨 :'(콜론+공백만)
    은 옆 값칸·산문과 구별이 안 되므로 제외(_is_fill_blank 금지). flat 은 _inline_texts
    의 직계 hp:t 를 문서순 그대로 결합(공백 정규화 금지, AC9)하고, 역순 스플라이스로
    앞 필드 offset 을 보존한다. 형제 run 의 텍스트·charPrIDRef 보존은 _splice_run_text
    가 보장(대상 hp:t 부분 교체만). 구간이 둘 이상의 hp:t 에 걸치면 채우지 않고
    span_notes 에 ``[span] … UNFILLED`` 를 남긴다. 콜론 뒤가 실값이면 덮지 않고
    ``[existing] … EXISTING_VALUE`` 를 남긴다. used_keys 는 표(1)/인라인(1.5)/
    체크박스(1.7)/본문(1.8)이 공유한다(이중 기입 금지). 반환: 이 단락에서 하나라도
    채웠으면 True.
    """
    if span_notes is None:
        span_notes = []
    if existing_labels is None:
        existing_labels = []
    ts = _inline_texts(p)
    if not ts:
        return False
    flat = "".join(t.text or "" for t in ts)
    if ":" not in flat and "：" not in flat:
        return False
    changed = False

    # onlab 서약서처럼 정확히 '팀 명 :'만 있는 문단은 팀명에 한해 콜론 뒤에 쓴다.
    # 비고/주의 등 일반 콜론 문단은 기존대로 채우지 않는다.
    colon_only = re.fullmatch(r"\s*(.*?)\s*[:：]\s*", flat, re.DOTALL)
    if colon_only and _key(colon_only.group(1)) == _key("팀명"):
        for want_key, lbl, val in wants:
            if want_key in used_keys or want_key != _key("팀명"):
                continue
            last = ts[-1]
            last.text = (last.text or "") + " " + str(val)
            _invalidate_lineseg(p)
            filled[lbl] = str(val)
            used_keys.add(want_key)
            changed = True
            flat = "".join(t.text or "" for t in ts)
            break

    fields = list(_iter_line_fields(flat))
    # 역순 스플라이스: 뒤 구간부터 교체해야 앞 필드 offset 이 유효.
    for label_raw, value_raw, f_start, f_end in reversed(fields):
        visible = _is_visible_blank(value_raw)
        real_value = _real_existing_text(value_raw)
        if not visible and not real_value:
            continue
        field_key = _key(label_raw)
        if not field_key:
            continue
        for want_key, lbl, val in wants:
            if want_key in used_keys:
                continue
            if _exact_identity_blocks_synonym(field_key, want_key, wants, used_keys):
                continue
            if _held_for_other_label(exact_held, field_key, want_key):
                continue
            if not _label_matches(field_key, want_key):
                continue
            if _signature_seal_label(label_raw) or _signature_seal_label(lbl):
                _note_region(span_notes, "signature", lbl, _tc_of(p))
                _hold_exact_label(exact_held, field_key, want_key)
                break
            owner = _tc_of(p)
            if owner is not None and _has_handwritten_object(owner):
                _note_region(span_notes, "handwritten", lbl, owner)
                _hold_exact_label(exact_held, field_key, want_key)
                break
            if not visible:
                _note_existing_value(span_notes, lbl, owner, existing_labels)
                _hold_exact_label(exact_held, field_key, want_key)
                break
            if _span_crosses_text_nodes(p, f_start, f_end):
                _note_unfilled_span(span_notes, lbl, _tc_of(p))
                _hold_exact_label(exact_held, field_key, want_key)
                break
            if _splice_run_text(p, f_start, f_end, " " + str(val)):
                filled[lbl] = str(val)
                used_keys.add(want_key)
                changed = True
            break
    return changed


def _parse_checkbox_options(flat: str) -> tuple[str, list[tuple[int, str]]]:
    """flat 문자열에서 (인라인 라벨, [(box_pos, 옵션라벨), ...]) 을 파싱한다.

    옵션 = 빈 체크박스(□류, _EMPTY_BOX_RE) 1글자 + 그 뒤 텍스트(다음 빈 박스
    또는 끝까지)의 라벨. 인라인 라벨 = 첫 박스 '앞' 텍스트(없으면 "").
    이미 체크된 박스(■/☑ 등)는 옵션으로 세지 않는다 → 재실행이 안 건드림(멱등).
    box_pos 는 flat offset — _splice_run_text 와 동일한 _inline_texts 결합 기준.
    """
    boxes = list(_EMPTY_BOX_RE.finditer(flat))
    if not boxes:
        return "", []
    inline_label = flat[: boxes[0].start()].strip()
    options: list[tuple[int, str]] = []
    for i, m in enumerate(boxes):
        end = boxes[i + 1].start() if i + 1 < len(boxes) else len(flat)
        options.append((m.start(), _option_text(flat[m.end():end])))
    return inline_label, options


# 대괄호형 빈 체크박스 — 워크넷/고용노동부 별지서식 계열이 `[ ] 동의` 처럼 쓴다.
# □ 계열(_EMPTY_BOX_RE)과 달리 여러 글자라 (start, end) 구간 단위로 다룬다.
_BRACKET_BOX_RE = re.compile(r"\[[  　]{0,2}\]")
_BRACKET_CHECK_MARK = "[√]"


def _iter_empty_boxes(flat: str) -> list[tuple[int, int, str]]:
    """flat 에서 '빈 체크박스' 구간 목록 [(start, end, 체크기호), ...] (문서순).

    두 계열을 함께 본다 — □ 류 1글자(_EMPTY_BOX_RE → ■)와 대괄호형 `[ ]`(→ `[√]`).
    이미 체크된 박스(■/☑/[√] 등)는 포함하지 않는다(재실행 멱등).
    """
    spans: list[tuple[int, int, str]] = [
        (m.start(), m.end(), _CHECK_MARK) for m in _EMPTY_BOX_RE.finditer(flat)
    ]
    spans += [
        (m.start(), m.end(), _BRACKET_CHECK_MARK)
        for m in _BRACKET_BOX_RE.finditer(flat)
    ]
    spans.sort(key=lambda s: s[0])
    return spans


def _parse_line_options(flat: str) -> list[tuple[int, int, str, str]]:
    """flat 을 '빈 체크박스 + 뒤따르는 옵션 라벨' 목록으로 판다.

    반환: [(box_start, box_end, 체크기호, 옵션라벨), ...]. 옵션 라벨은 그 박스 뒤부터
    다음 박스 앞까지의 텍스트(``_option_text`` 로 정리). ``_parse_checkbox_options``
    의 대괄호 지원 확장판이며, 라벨 자동매칭 대신 **앵커 기반 지시**(line_edits)에서 쓴다.
    """
    boxes = _iter_empty_boxes(flat)
    out: list[tuple[int, int, str, str]] = []
    for i, (start, end, mark) in enumerate(boxes):
        stop = boxes[i + 1][0] if i + 1 < len(boxes) else len(flat)
        out.append((start, end, mark, _option_text(flat[end:stop])))
    return out


def _tc_of(el):
    """el 의 가장 가까운 조상 hp:tc(표 셀). 표 밖이면 None."""
    cur = el.getparent()
    while cur is not None:
        if _local(getattr(cur, "tag", "")) == "tc":
            return cur
        cur = cur.getparent()
    return None


def _apply_line_edits(
    root, line_edits: list[dict], edited: list,
    black: Optional[_BlackCharPr] = None,
) -> tuple[int, list[str]]:
    """'앵커 문단'에 한정해 텍스트 체크·직접 치환을 적용한다(사용자 명시 지시 전용).

    정부 서식에는 라벨-값 표가 아니라 **안내 문단 안에 선택지가 박힌** 칸이 많다
    (워크넷 별지 제2호 `1. 개인정보 수집ㆍ이용 동의 여부  [ ] 동의  [ ] 동의하지 않음`).
    이런 칸은 이미 글자가 있어 ``replacements`` 가 보호(_in_protected_cell)하고,
    라벨 자동매칭(1.7)도 그룹 라벨을 잡지 못한다. 그래서 **사람이 앵커 문구와
    선택지를 명시**했을 때만 동작하는 좁은 경로를 둔다(추측·자동확대 없음).

    line_edits 항목: ``{"anchor": str, "set": "문단 전체 새 글", "check": [옵션…],
    "replace": {옛:새}, "cells": {colAddr: 값}, "nth": 1, "all": False}``.
    ``set`` 은 앵커 문단의 텍스트를 통째로 갈아끼운다(같은 양식에 다른 아이템 내용을
    얹을 때). 첫 hp:t 에 넣고 나머지는 비워 **첫 run 의 서식을 그대로 승계**한다. ``nth``(1-based)·``all`` 은
    같은 문구가 여러 번 나오는 반복 행/반복 날짜를 지목할 때만 쓴다(미지정 시 유일할
    때만 적용). ``cells`` 는 **열머리글이 위에 있는 표**(라벨이 왼쪽이 아니라 위라
    라벨→값 매칭이 닿지 않는 구조)에서, 앵커가 든 셀과 **같은 행**의 빈 칸을
    colAddr 로 지목해 채운다(값이 이미 있으면 덮지 않는다).

    안전 규칙(오편집 < 미편집):
    - anchor 는 문서 안에서 **정확히 한 문단**에만 있어야 한다(0개·2개+ → 스킵·notes).
      단 ``nth``/``all`` 을 명시하면 그 지목대로 적용한다.
    - check 옵션은 그 문단의 빈 체크박스 옵션 라벨과 **정확일치 1개**여야 한다.
    - replace 의 옛 문자열은 그 문단에 **정확히 1회**만 나와야 한다.
    - 한 문단 안 여러 편집은 **뒤에서 앞으로** 적용해 offset 을 보존한다.
    """
    if not line_edits:
        return 0, []
    paras = [(p, "".join(t.text or "" for t in _inline_texts(p)))
             for p in root.iter(_q("p"))]
    applied = 0
    notes: list[str] = []
    for spec in line_edits:
        anchor = str((spec or {}).get("anchor") or "")
        if not anchor:
            continue
        hits = [p for p, flat in paras if anchor in flat]
        nth = spec.get("nth")
        if spec.get("all"):
            targets = hits
        elif nth:
            idx = int(nth)
            targets = [hits[idx - 1]] if 1 <= idx <= len(hits) else []
        else:
            targets = hits if len(hits) == 1 else []
        if not targets:
            notes.append(
                f"앵커 {'모호' if hits else '미발견'}({len(hits)}건): {anchor[:40]}"
            )
            continue
        for p in targets:
            # (0) 문단 통째 교체 — 같은 양식에 다른 아이템/내용을 얹을 때(내용 갈아끼우기).
            #     첫 hp:t 에 새 글을 넣고 나머지 hp:t 는 비운다(첫 run 의 서식을 따른다).
            new_text = spec.get("set")
            if new_text is not None and str(new_text).strip():
                ts = _inline_texts(p)
                if ts:
                    ts[0].text = str(new_text)
                    for t in ts[1:]:
                        t.text = ""
                    if black is not None:
                        run = ts[0].getparent()
                        if run is not None and _local(getattr(run, "tag", "")) == "run":
                            black.fix_run(run)
                    _invalidate_lineseg(p)
                    applied += 1
                    edited.append(p)
                else:
                    notes.append(f"교체 실패(텍스트 run 없음): {anchor[:24]}")

            # (a) 체크 — 뒤에서 앞으로 스플라이스(앞 옵션 offset 보존)
            wants = [str(o) for o in (spec.get("check") or []) if str(o or "").strip()]
            todo: list[tuple[int, int, str]] = []
            flat = "".join(t.text or "" for t in _inline_texts(p))
            options = _parse_line_options(flat)
            for want in wants:
                wkey = _opt_key(want)
                cand = [(s, e, mark) for s, e, mark, lbl in options
                        if _opt_key(lbl) and _opt_key(lbl) == wkey]
                if len(cand) != 1:
                    notes.append(
                        f"옵션 {'모호' if cand else '미발견'}: {want} @ {anchor[:24]}"
                    )
                    continue
                todo.append(cand[0])
            for start, end, mark in sorted(todo, key=lambda x: -x[0]):
                if _splice_run_text(p, start, end, mark):
                    applied += 1
                    edited.append(p)
                else:
                    notes.append(
                        f"체크 실패(run 경계 분할): {flat[start:end + 8]!r}"
                        f" @ {anchor[:24]}"
                    )
            # (b) 직접 치환 — 매번 flat 재계산(길이 변화 반영)
            for old, new in (spec.get("replace") or {}).items():
                old = str(old or "")
                if not old:
                    continue
                flat = "".join(t.text or "" for t in _inline_texts(p))
                if flat.count(old) != 1:
                    notes.append(
                        f"치환 {'모호' if flat.count(old) else '미발견'}: "
                        f"{old[:24]} @ {anchor[:24]}"
                    )
                    continue
                pos = flat.index(old)
                if _splice_run_text(p, pos, pos + len(old), str(new)):
                    applied += 1
                    edited.append(p)
                else:
                    notes.append(
                        f"치환 실패(run 경계 분할): {old[:24]!r} @ {anchor[:24]}"
                    )
            # (c) 같은 행의 빈 칸 채움 — 열머리글이 위에 있는 표(라벨이 왼쪽이 아님)용.
            #     앵커가 든 셀의 hp:tr 에서 colAddr 로 형제 칸을 지목한다.
            for col, val in (spec.get("cells") or {}).items():
                if not str(val or "").strip():
                    continue
                tc = _tc_of(p)
                tr = tc.getparent() if tc is not None else None
                if tr is None or _local(getattr(tr, "tag", "")) != "tr":
                    notes.append(f"행 찾기 실패(표 밖 문단): {anchor[:24]}")
                    continue
                hit = [c for c in _direct(tr, "tc") if _cell_addr(c) == int(col)]
                if len(hit) != 1:
                    notes.append(f"칸 지목 실패(colAddr={col}, {len(hit)}개): {anchor[:24]}")
                    continue
                if not _cell_is_fillable(hit[0]):
                    notes.append(f"칸에 이미 값 있음(덮어쓰기 금지, colAddr={col}): {anchor[:24]}")
                    continue
                if _split_value_spans(hit[0]):
                    notes.append(
                        f"칸 기입 보류(run 경계 분할, colAddr={col}): {anchor[:24]}"
                    )
                    continue
                if _set_cell_text(hit[0], str(val), black):
                    applied += 1
                    edited.append(hit[0])
    return applied, notes


_OPT_TRAIL_PUNCT = ",.;:·"


def _opt_key(s: str) -> str:
    """체크박스 옵션/값 비교용 키 — ``_key`` 후 꼬리 구두점 제거.

    실측(008 서식): 옵션 `자가(소유자   ),` 가 ``_key`` 정규화 후에도 `자가,`
    처럼 꼬리 콤마가 남아 값 `자가` 와 정확일치에 실패했다(보수 스킵 → 미채움).
    꼬리 구두점(콤마·마침표·세미콜론·콜론·가운뎃점)만 벗긴다 — 부분문자열
    매칭은 여전히 금지(`개인정보보호,` → `개인정보보호` ≠ `개인`).
    """
    return _key(s).rstrip(_OPT_TRAIL_PUNCT)


def _left_label_text(tc) -> str:
    """같은 행에서 tc 보다 colAddr 이 작은 셀 중 '가장 가까운' 라벨칸 텍스트.

    빈칸·체크박스 옵션칸(□ 포함)은 라벨로 보지 않고 건너뛴다. cellAddr 미지정
    양식은 행 내 위치 인덱스로 폴백한다. 라벨칸이 없으면 ""(그룹 스킵 신호).
    """
    row = _row_of(tc)
    if row is None:
        return ""
    cells = _direct(row, "tc")
    my_addr = _cell_addr(tc)
    if my_addr is not None:
        lefts = []
        for c in cells:
            addr = _cell_addr(c)
            if addr is not None and addr < my_addr:
                lefts.append((addr, c))
        lefts.sort(key=lambda pair: -pair[0])   # 가까운(큰 colAddr) 순
        candidates = [c for _, c in lefts]
    else:
        try:
            idx = cells.index(tc)
        except ValueError:
            return ""
        candidates = list(reversed(cells[:idx]))
    for c in candidates:
        txt = _cell_text(c)
        if not txt or _EMPTY_BOX_RE.search(txt):
            continue                             # 빈칸/옵션칸은 라벨이 아님
        return txt
    return ""


_EXAMPLE_OMASK_RE = re.compile(r"^[O○〇ㅇo]{3,}$")
_EXAMPLE_ZERO_RE = re.compile(r"^[0.\-\s]{6,}$")
_EXAMPLE_DATE_RE = re.compile(r"^0{4}\s*년\s*0{1,2}\s*월\s*0{1,2}\s*일$")
_EXAMPLE_GUIDED_OMASK_RE = re.compile(
    r"^[O○〇ㅇo]{3,}\s*[\(（].*(?:기입|작성|동일).*[\)）]\s*$"
)
_EXAMPLE_GUIDED_DATE_RE = re.compile(
    r"^0{4}\s*년\s*0{1,2}\s*월\s*0{1,2}\s*일\s*(.+)$"
)


def _date_placeholder_crosses_spans(tc) -> bool:
    """날짜 자체가 여러 span 에 나뉜 경우만 보존한다.

    완전한 날짜 예시 뒤의 별도 안내 run 은 교체할 수 있지만, 년/월/일이
    서로 다른 run 에 있으면 기존 날짜 서식과 span 경계를 합치지 않는다.
    """
    raw = _cell_text(tc)
    if not (_EXAMPLE_DATE_RE.fullmatch(raw) or _EXAMPLE_GUIDED_DATE_RE.fullmatch(raw)):
        return False
    texts = _cell_texts(tc)
    first = re.sub(r"\s+", " ", str(texts[0].text or "")).strip() if texts else ""
    return not (
        _EXAMPLE_DATE_RE.fullmatch(first) or _EXAMPLE_GUIDED_DATE_RE.fullmatch(first)
    )


_GUIDANCE_VALUE_RE = re.compile(
    r"^(?:예비창업|해당|예시|참고|입력|기재)[^\n]{0,70}(?:기재|작성)[^\n]{0,12}$"
)
_GUIDANCE_CONTACT_RE = re.compile(
    r"^[\(（]\s*(?:휴대폰|휴대전화|연락처)\s*[\)）]$",
    re.IGNORECASE,
)


def _is_hwpx_guidance_placeholder(text: str) -> bool:
    """값 칸 자체가 무엇을 쓰라는 짧은 안내뿐이면 빈칸으로 본다."""
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if re.fullmatch(r"ex\s*\)\s*\S.{0,230}", raw, re.IGNORECASE):
        return True
    if not raw or len(raw) > 90:
        return False
    return bool(
        _GUIDANCE_CONTACT_RE.fullmatch(raw)
        or _GUIDANCE_VALUE_RE.fullmatch(raw)
    )

_EXAMPLE_CHOICE_RE = re.compile(r"\s*/\s*")
_REGION_SCAFFOLD_CHARS_RE = re.compile(r"[O○〇ㅇ0\s·・.\-도특별시군구읍면동로길번지]")


def _is_hwpx_example_scaffold(text: str) -> bool:
    """칸 전체가 양식 예시(OOO·0마스크·지역 뼈대·선택 안내)면 True.

    cross-form ``_is_obvious_placeholder`` 는 단독 O마스크를 일부러 제외한다
    (GOOGLE/SOHO 오탐). 이 판정은 HWPX 값칸을 채울 때만 쓰고, 칸 문자열 전체에
    다른 글자가 없을 때만 예시로 본다.
    """
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if not raw or len(raw) > 240:
        return False
    if any(mark in raw for mark in ("□", "☐", "■", "☑")):
        return False
    compact = re.sub(r"\s+", "", raw)
    if _EXAMPLE_OMASK_RE.fullmatch(compact):
        return True
    if _EXAMPLE_GUIDED_OMASK_RE.fullmatch(raw):
        return True
    if _EXAMPLE_DATE_RE.fullmatch(raw):
        return True
    guided_date = _EXAMPLE_GUIDED_DATE_RE.fullmatch(raw)
    if guided_date and re.search(r"기입|작성|기재|기준|사업자등록|법인등기", guided_date.group(1)):
        return True
    if _EXAMPLE_ZERO_RE.fullmatch(compact) and "0" in compact and not re.search(r"[1-9]", compact):
        return True
    if re.search(r"[O○〇ㅇ]{2,}", raw) and re.search(r"[도시군구]", raw):
        if _REGION_SCAFFOLD_CHARS_RE.sub("", raw) == "":
            return True
    # '직위/직책' 처럼 슬래시만 붙은 복합 라벨은 예시가 아니다.
    # '개인사업자 / 법인사업자', '남 / 여' 처럼 슬래시 옆에 공백이 있을 때만 선택 안내로 본다.
    if re.search(r"\s/|/\s|／", raw):
        parts = [part.strip() for part in _EXAMPLE_CHOICE_RE.split(raw) if part.strip()]
        if 2 <= len(parts) <= 6 and all(
            1 <= len(part) <= 20 and not re.search(r"[.。!?]", part) for part in parts
        ):
            return True
    return False


def _cell_text_fillable(tc) -> bool:
    """텍스트 기준 채움 가능 판정 — 비었거나 예시 칸이면 True.

    이미 실제 값이 있으면 False(덮어쓰기 금지). 빈칸 외에는 명백한 플레이스홀더와
    HWPX 예시 칸(OOO, 000-0000-0000, OO도 OO시·군, '개인사업자 / 법인사업자')을
    채울 대상으로 본다. 문서 추출용 O마스크 금지는 ``_is_obvious_placeholder`` 에 남긴다.
    """
    txt = _cell_text(tc)
    if not txt:
        return True
    return (
        _is_obvious_placeholder(txt)
        or _is_hwpx_example_scaffold(txt)
        or _is_hwpx_guidance_placeholder(txt)
    )


def _cell_is_fillable(tc) -> bool:
    """그 칸에 '새 값을 기입'해도 되는가 — 텍스트 기준 + 폼 컨트롤 가드.

    폼 컨트롤(체크박스·입력필드 등)이 든 칸은 텍스트가 비어 보여도 채우지 않는다
    (컨트롤과 글자 이중 표시 방지 — 실측: 수원 멘토위원 신청서 ☐■ 이중).
    """
    if _has_form_control(tc) or _cell_has_nested_table(tc):
        return False
    return _cell_text_fillable(tc)



def _cell_has_blue_example_style(tc, black: Optional[_BlackCharPr]) -> bool:
    """값 칸 전체가 파란 예시체이면 현재 매칭된 프로필 값으로 교체 가능한가.

    텍스트 자체가 실값처럼 보여도 charPr가 양식 예시 파랑(#0000FF)인 경우에만 True.
    호출 위치가 이미 라벨↔identity 매칭 뒤이므로 해당 프로필 필드가 있을 때만 적용된다.
    """
    if black is None or _has_form_control(tc) or _cell_has_nested_table(tc):
        return False
    seen = False
    for t in _cell_texts(tc):
        if not str(t.text or "").strip():
            continue
        run = t.getparent()
        if run is None or _local(getattr(run, "tag", "")) != "run":
            return False
        ref = run.get("charPrIDRef") or ""
        color = re.sub(r"[^0-9A-Fa-f]", "", black.colors.get(ref, "") or "").upper()
        if color != "0000FF":
            return False
        seen = True
    return seen


_REGION_PROTECTED_LABEL_RE = re.compile(
    r"서명|날인|직인|인감|동의|서약|확약|체크|선택|확인자|심사|평가위원"
)


def region_cell_is_writable(tc, label: str = "") -> bool:
    """Exact-region v1 permits only empty, simple text cells, never controls.

    The analyzer may impose additional label/region-map restrictions. This guard
    independently checks the actual neighboring XML label, not caller metadata.
    Placeholder prose and existing values require a later revision contract.
    """
    if tc.tag != _q("tc") or _cell_text(tc) or _has_form_control(tc):
        return False
    if _REGION_PROTECTED_LABEL_RE.search(f"{_left_label_text(tc)} {label}"):
        return False
    sublists = _direct(tc, "subList")
    if len(sublists) != 1:
        return False
    # A containing cell must not absorb nested table/image/object content.
    allowed_cell = {_q(n) for n in ("subList", "cellAddr", "cellSpan", "cellSz", "cellMargin")}
    if any(child.tag not in allowed_cell for child in tc):
        return False
    sublist = sublists[0]
    if not len(sublist) or any(child.tag != _q("p") for child in sublist):
        return False
    for paragraph in sublist:
        if any(child.tag not in {_q("run"), _q("linesegarray")} for child in paragraph):
            return False
        for run in _direct(paragraph, "run"):
            if any(child.tag != _q("t") or len(child) for child in run):
                return False
    return True


def _is_label_like(tc) -> bool:
    """그 칸이 값칸이 아니라 '라벨/안내' 칸으로 보이면 True(값 기입 금지 대상).

    OOO·000-0000-0000 같은 예시 칸은 잡음 라벨로 보이지만 채울 값 칸이다.
    """
    txt = _cell_text(tc)
    if not txt:
        return False
    if (
        _is_obvious_placeholder(txt)
        or _is_hwpx_example_scaffold(txt)
        or _is_hwpx_guidance_placeholder(txt)
    ):
        return False
    norm = _key(txt)
    return _cluster_rep(norm) is not None or _is_noise_label(txt, norm)


def _cell_has_real_value(tc) -> bool:
    """값칸에 플레이스홀더가 아닌 사용자 글자가 있으면 True."""
    if tc is None or _is_label_like(tc):
        return False
    return _real_existing_text(_cell_text(tc))


def _in_protected_cell(t) -> bool:
    """hp:t 가 '채울 수 없는'(라벨·실값) 표 셀 안에 있으면 True(치환 보호 대상).

    가장 가까운 조상 hp:tc 를 찾아 **텍스트 기준**(_cell_text_fillable)으로
    판정한다 — 치환은 기존 텍스트 덮어쓰기라 폼 컨트롤 가드를 적용하지 않는다
    (컨트롤 옆 예시토큰 치환의 종전 recall 보존, 적대검증 D5). 표 밖(본문)
    텍스트는 보호하지 않는다. id() 대신 조상 순회라 lxml proxy 재사용 영향 없음.
    """
    cur = t.getparent()
    while cur is not None:
        if _local(getattr(cur, "tag", "")) == "tc":
            return not _cell_text_fillable(cur)
        cur = cur.getparent()
    return False


_PRIOR_SUPPORT_RE = re.compile(
    r"창업지원금|수혜\s*이력|지원\s*이력|기\s*지원|기지혜|과거\s*지원|참여\s*이력|"
    r"지원금\s*수혜|수혜\s*실적|기수혜|타\s*창업지원사업|"
    r"신청\s*[·ㆍ/]?\s*수행\s*여부|중복\s*지원|수행\s*실적"
)
_PRIOR_SUPPORT_PROJECT_KEYS = frozenset(
    _key(name) for name in ("사업명", "과제명") if _key(name)
)
_SUPPORT_AGENCY_HEADER_KEYS = frozenset(
    _key(name) for name in ("지원기관",) if _key(name)
)


def _table_first_row_text_by_col(tbl, tc) -> str:
    """표 첫 행에서 tc와 같은 colAddr의 머리글 텍스트를 반환."""
    col = _cell_addr(tc)
    rows = _direct(tbl, "tr")
    if col is None or not rows:
        return ""
    for header_tc in _direct(rows[0], "tc"):
        if _cell_addr(header_tc) == col:
            return _cell_text(header_tc)
    return ""


def _repeats_prior_support_header(tbl, tc) -> bool:
    """이력표 데이터 셀이 같은 열 머리글을 그대로 반복하면 라벨로 쓰지 않는다."""
    text = _cell_text(tc)
    header = _table_first_row_text_by_col(tbl, tc)
    return bool(text and header and _key(text) == _key(header))


def _prior_support_target_is_agency_column(tbl, target) -> bool:
    """이력표의 지원기관 열인지 머리글 기준으로 판정."""
    return _key(_table_first_row_text_by_col(tbl, target)) in _SUPPORT_AGENCY_HEADER_KEYS


_APPLICANT_IDENTITY_REPS = frozenset(
    rep for rep in (
        _cluster_rep(_key(name))
        for name in (
            "기업명", "대표자", "연락처", "주소", "이메일",
            "사업자등록번호", "설립일",
        )
    )
    if rep
)


def _is_applicant_identity(want_key: str) -> bool:
    """신청인 신원(기업·대표·연락)이면 True. 과제명 같은 서술 키는 아니다."""
    rep = _cluster_rep(want_key) or want_key
    return rep in _APPLICANT_IDENTITY_REPS


def _element_text(el) -> str:
    return "".join((node.text or "") for node in el.iter(_q("t")))


_SECTION_HEADING_RE = re.compile(
    r"^(?:\d+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+|[가-하])\s*[.．)]"
)


def _is_section_heading(text: str) -> bool:
    folded = re.sub(r"\s+", "", text or "")
    if not folded or len(folded) > 40:
        return False
    return _SECTION_HEADING_RE.match(re.sub(r"\s+", " ", text).strip()) is not None


def _text_outside_table(paragraph, tbl) -> str:
    """문단 글자 중 이 표 안은 뺀다. 같은 문단의 소제목을 보기 위함이다."""
    parts: list[str] = []
    for node in paragraph.iter(_q("t")):
        cur = node
        inside = False
        while cur is not None and cur is not paragraph:
            if cur is tbl:
                inside = True
                break
            cur = cur.getparent()
        if not inside:
            parts.append(node.text or "")
    return "".join(parts)


def _is_prior_support_table(tbl) -> bool:
    """바로 위 제목이나 표 머리글이 수혜·창업지원금 이력 표이면 True.

    신청인 정보 표는 제목이 달라도 채운다. 가장 가까운 번호 제목에서 걷기를
    멈춰, 앞 절의 '창업지원금' 이 신청인 표까지 물들이지 않게 한다.
    """
    chunks: list[str] = []
    for tr in _direct(tbl, "tr")[:2]:
        chunks.append(_element_text(tr))
    node = tbl
    while node is not None and _local(getattr(node, "tag", "")) != "p":
        node = node.getparent()
    if node is not None:
        same = _text_outside_table(node, tbl).strip()
        if same:
            chunks.append(same)
    prev = node.getprevious() if node is not None else None
    hops = 0
    while prev is not None and hops < 4:
        if _local(getattr(prev, "tag", "")) == "p":
            text = _element_text(prev).strip()
            if text:
                chunks.append(text)
                hops += 1
                if _is_section_heading(text):
                    break
        prev = prev.getprevious()
    return _PRIOR_SUPPORT_RE.search(" ".join(chunks)) is not None


def _label_matches(cell_key: str, want_key: str) -> bool:
    """정규화 라벨 cell_key 가 want_key 와 같은 항목인가(정확일치 또는 동의어 클러스터)."""
    if not cell_key or not want_key:
        return False
    if cell_key == want_key:
        return True
    rep_c = _cluster_rep(cell_key)
    rep_w = _cluster_rep(want_key)
    return rep_c is not None and rep_c == rep_w


def _exact_identity_blocks_synonym(cell_key: str, want_key: str, wants, used_keys) -> bool:
    """칸 라벨 자체가 아직 안 쓴 identity 키면 동의어 매칭을 막는다.

    기업명·팀명은 같은 동의어 묶음이다. identity 에 둘 다 있으면 팀명 칸이
    기업명 값을 먼저 가져가지 않게, 그 칸과 같은 키를 우선한다.
    """
    if not cell_key or cell_key == want_key:
        return False
    for other_key, _lbl, _val in wants:
        if other_key in used_keys:
            continue
        if other_key == cell_key:
            return True
    return False


def _value_cell(label_tc, cells: list):
    """라벨 칸의 값 칸을 찾는다 — cellAddr 우선(병합 안전), 없으면 위치 i+1 폴백.

    cellAddr 이 있으면 colAddr+colSpan 위치의 셀만 값칸으로 인정한다. 그 위치 셀이
    없으면(가로병합으로 사라졌거나 행 끝) None 을 돌려 '엉뚱한 칸 채움'을 차단한다.
    """
    addr = _cell_addr(label_tc)
    if addr is not None:
        want_col = addr + _cell_colspan(label_tc)
        for tc in cells:
            if _cell_addr(tc) == want_col:
                return tc
        return None  # 병합 등으로 값칸 위치가 비어있음 — 보수적으로 스킵
    # cellAddr 미지정 양식 — 위치 인덱스 폴백
    try:
        idx = cells.index(label_tc)
    except ValueError:
        return None
    return cells[idx + 1] if idx + 1 < len(cells) else None


_PERIOD_HEADER_RE = re.compile(r"^\(?(?:\d+년전|전년(?:도)?|당년(?:도)?|금년|현재|최근|20\d{2}년?)\)?$")


def _current_period_value_cell(tbl, label_tc, cells: list):
    """기간별 수치표는 현재 열만 선택한다. 열 주소가 모호하면 쓰지 않는다."""
    periods = []
    for row in _direct(tbl, "tr")[:3]:
        for cell in _direct(row, "tc"):
            text = re.sub(r"\s+", "", _cell_text(cell))
            if _PERIOD_HEADER_RE.fullmatch(text):
                periods.append((text.strip("()"), _cell_addr(cell)))
        if periods:
            break
    if not periods:
        return _value_cell(label_tc, cells)
    current = [col for text, col in periods if text in {"현재", "당년", "당년도", "금년", "최근"}]
    if len(current) > 1 or any(col is None for _, col in periods):
        return None
    col = current[0] if current else max(col for _, col in periods)
    candidates = [cell for cell in cells if _cell_addr(cell) == col and _cell_colspan(cell) == 1]
    return candidates[0] if len(candidates) == 1 and candidates[0] is not label_tc else None


def _cell_rowspan(tc) -> int:
    cs = next(iter(_direct(tc, "cellSpan")), None)
    return _int_attr(cs, "rowSpan", 1)


# 그리드 선택칸 마크 지시문 — 실측: "취득방법(해당란에 ‘○’표시)"(중기부 공통서식 053
# 취득방법·분류1~5·예비타당성 등 6곳+), "동의여부(해당란에 √표시)"(수출바우처 016/128).
# 괄호 안 '해당…에 <기호> 표(시)' 만 지시문으로 인정한다 — "확인 후 √ 표시" 같은
# 체크리스트 안내(행별 확인, 선택 아님)는 '해당'이 없어 매칭되지 않는다(오탐 차단).
_GRID_INSTR_RE = re.compile(
    r"[(（]\s*해당\s*(?:란|칸|항목|사항)?\s*(?:에|되는\s*곳에)?\s*"
    r"[‘'\"“]?\s*([○●VvＶ√✔✓])\s*[’'\"”]?\s*표\s*시?\s*[)）]"
)


def _grid_choice_groups(tbl) -> list:
    """표에서 '그리드 선택칸' 그룹을 찾는다 — □ 기호 없이 셀 자체가 선택지인 구조.

    실측 구조(053 공통서식 취득방법/분류1~5/예비타당성·서울AI허브 '신청 Track'):
      행 R  : [라벨셀(rowSpan≥2)] [옵션셀…(각각 비지 않은 짧은 텍스트)]
      행 R+1: [옵션과 같은 colAddr·colSpan 의 빈 마크셀…]  ← 여기에 ○/√ 기입
    한 행에 그룹이 여러 개면(053 #143: 예비타당성|사전기획|수요조사) rowSpan≥2 인
    다음 라벨셀에서 그룹을 끊는다. 보수 게이트(전부 만족해야 그룹 인정):
      cellAddr 필수 · 옵션 ≥2 · 옵션에 □/■류 기호 없음(체크박스는 1.7 담당) ·
      마크행 셀이 옵션과 정확 정렬(colAddr+colSpan 동일)·전부 빈칸·폼컨트롤 없음.
    마크행에 하나라도 값/마크가 있으면 그룹 전체 보류 — 멱등(재실행 무변경)·기존
    선택 보존. 반환: [(라벨키, 지시문 마크기호 or None, [(옵션텍스트, 마크셀), …])].
    """
    groups: list = []
    rows = _direct(tbl, "tr")
    for ri in range(len(rows) - 1):
        cells = _direct(rows[ri], "tc")
        below: dict[int, Any] = {}
        for mc in _direct(rows[ri + 1], "tc"):
            addr = _cell_addr(mc)
            if addr is not None:
                below[addr] = mc
        for idx, tc in enumerate(cells):
            if _cell_rowspan(tc) < 2:
                continue                       # 라벨은 마크행까지 세로 병합돼 있어야 함
            raw = _cell_text(tc)
            if not raw:
                continue
            instr = _GRID_INSTR_RE.search(raw)
            label_key = _key(_GRID_INSTR_RE.sub("", raw))
            if not label_key:
                continue
            opts: list = []
            valid = True
            for tc2 in cells[idx + 1:]:
                if _cell_rowspan(tc2) >= 2:
                    break                      # 다음 그룹 라벨 — 이 그룹 끝
                txt2 = _cell_text(tc2)
                addr2 = _cell_addr(tc2)
                if addr2 is None or not txt2 or _ANY_BOX_RE.search(txt2):
                    valid = False              # 주소 불명·빈 헤더·체크박스 혼입 → 구조 불명
                    break
                mc = below.get(addr2)
                if (mc is None or _cell_colspan(mc) != _cell_colspan(tc2)
                        or _has_form_control(mc) or _cell_text(mc)):
                    valid = False              # 마크행 미정렬·컨트롤·이미 값 → 그룹 보류
                    break
                opts.append((txt2, mc))
            if valid and len(opts) >= 2:
                mark = None
                if instr:
                    ch = instr.group(1)
                    mark = "V" if ch in "vＶ" else ch
                groups.append((label_key, mark, opts))
    return groups


@dataclass
class HwpxFillReport:
    input: str
    output: str = ""
    ok: bool = False
    filled: dict[str, str] = field(default_factory=dict)   # 채운 라벨→값
    filled_count: int = 0
    replaced: int = 0
    residual: list[str] = field(default_factory=list)      # 매칭 못 한 identity 라벨
    checked: list[str] = field(default_factory=list)       # 체크한 폼컨트롤 옵션
    check_residual: list[str] = field(default_factory=list)  # 못 체크한 옵션(모호/부재)
    # 그리드 선택칸(□ 없음) 후보 — 구조·값은 일치하나 마크 지시문이 없어 자동 기입을
    # 보류한 항목(needs_confirm, 오체크<미체크). 사람이 확인 후 직접 기입한다.
    grid_needs_confirm: list[str] = field(default_factory=list)
    line_edits_applied: int = 0   # 앵커 문단 편집(체크·치환) 성공 건수
    field_writes_written: dict[str, str] = field(default_factory=dict)
    field_write_skipped: dict[str, str] = field(default_factory=dict)
    field_write_style: dict[str, str] = field(default_factory=dict)
    template_status: str = ""
    sections_changed: int = 0
    overflow_cells: list[str] = field(default_factory=list)  # L097 한 줄 칸 넘침 가능
    pages_before: int = 0  # L095 XML 페이지 기준선 (한글 렌더 아님)
    pages_after: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "ok": self.ok,
            "filled": dict(self.filled),
            "filled_count": self.filled_count,
            "replaced": self.replaced,
            "residual": list(self.residual),
            "checked": list(self.checked),
            "check_residual": list(self.check_residual),
            "grid_needs_confirm": list(self.grid_needs_confirm),
            "line_edits_applied": self.line_edits_applied,
            "field_writes_written": dict(self.field_writes_written),
            "field_write_skipped": dict(self.field_write_skipped),
            "field_write_style": dict(self.field_write_style),
            "template_status": self.template_status,
            "sections_changed": self.sections_changed,
            "overflow_cells": list(self.overflow_cells),
            "pages_before": self.pages_before,
            "pages_after": self.pages_after,
            "notes": list(self.notes),
        }


def _layout_scope(el):
    """``hp:linesegarray`` 가 붙는 단위(문단 p, 없으면 셀 tc)로 올라간다.

    캐시는 run/t 가 아니라 그 조상 ``hp:p`` 의 자식(run 과 형제)이다. t 만
    넘기면 하위 iter 로는 안 잡히므로 조상으로 올린다.
    """
    cur = el
    while cur is not None:
        loc = _local(getattr(cur, "tag", ""))
        if loc in ("p", "tc"):
            return cur
        cur = cur.getparent()
    return el


def _owned_paragraph_text(paragraph) -> str:
    """이 문단 직계 run 의 글자. 중첩 표 안 문단은 그 문단 것이다."""
    parts: list[str] = []
    for child in paragraph:
        if _local(getattr(child, "tag", "")) != "run":
            continue
        for node in child:
            if _local(getattr(node, "tag", "")) == "t":
                parts.append(node.text or "")
    return "".join(parts)


def _drop_owned_lineseg(paragraph) -> int:
    """이 문단 소속 linesegarray 만 제거한다. 중첩 문단 캐시는 남긴다."""
    removed = 0

    def walk(el) -> None:
        nonlocal removed
        for child in list(el):
            if _local(getattr(child, "tag", "")) == "p":
                continue
            if _local(getattr(child, "tag", "")) == "linesegarray":
                el.remove(child)
                removed += 1
                continue
            walk(child)

    walk(paragraph)
    return removed


def _invalidate_lineseg(el) -> int:
    """텍스트를 바꾼 요소의 줄위치 캐시(hp:linesegarray)를 즉시 제거한다.

    L002 뿌리: 편집 직후 그 칸/문단만 무효화한다. ``fill_hwpx`` 파이프라인을
    거치지 않는 직접 호출(``_set_cell_text``, L145)에서도 글씨 겹침이 나지 않는다.
    L074: 형제 문단(안내박스) 캐시는 건드리지 않는다.
    """
    if el is None:
        return 0
    scope = _layout_scope(el)
    if scope is None:
        return 0
    return _strip_linesegarray(scope, only_under=[scope])


def _strip_linesegarray(root, *, only_under=None) -> int:
    """채운 섹션의 옛 줄위치 캐시(hp:linesegarray)를 제거한다.

    텍스트를 바꿔도 예시문구 기준의 linesegarray 가 남으면 한글이 새 글씨를 옛
    좌표에 겹쳐 그린다(사용자 실측: STAR·서울 AI 허브 신청서 글씨 겹침 재발). 제거하면
    문서를 열 때 줄위치를 새로 계산한다 — 레이아웃 캐시라 내용 무손실·멱등.
    원천 차단은 ``_set_cell_text`` / ``_splice_run_text`` 가 편집 직후
    ``_invalidate_lineseg`` 를 부르는 쪽이다. 이 함수는 그 구현 + 후처리 진입점.

    L074: ``only_under`` 가 주어지면 그 요소(들) 하위의 lineseg 만 제거한다.
    rhwp→PDF 경로에서 전역 strip 이 안내박스 다중문단을 깨뜨리는 것을 막기 위한
    편집-한정 API. ``only_under`` 미지정 시 종전처럼 root 전역(한글 직접 납품용).
    """
    removed = 0
    scopes = list(only_under) if only_under is not None else [root]
    seen_ids: set[int] = set()
    for scope in scopes:
        if scope is None:
            continue
        sid = id(scope)
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        for ls in list(scope.iter(_q("linesegarray"))):
            parent = ls.getparent()
            if parent is not None:
                parent.remove(ls)
                removed += 1
    return removed


def relax_t02_written_layout(hwpx_path: str | Path, specs: list[dict]) -> int:
    """T02 가 글을 넣은 문단의 lineseg 를 지우고, 빈 run 에 넣은 값은 본문 스타일로 바꾼다.

    exact writer 는 텍스트 노드만 바꾸고 lineseg·charPr 를 유지한다(범위 검사).
    제출 경로에서 그 다음에 이 함수를 불러 한글이 줄을 다시 잡게 한다.
    라벨과 값을 한 run 에 이어 쓴 경우(expected_raw_text 가 있음)는 라벨 서식을 유지한다.
    """
    path = Path(hwpx_path)
    if not specs or not path.is_file():
        return 0
    wanted: dict[str, list[dict]] = {}
    for spec in specs:
        member = str(spec.get("section_member") or "")
        if not member:
            continue
        wanted.setdefault(member, []).append(spec)
    if not wanted:
        return 0
    with zipfile.ZipFile(path) as zin:
        infos = zin.infolist()
        data = {info.filename: zin.read(info.filename) for info in infos}
    header_name = "Contents/header.xml"
    black: Optional[_BlackCharPr] = None
    if header_name in data:
        try:
            black = _BlackCharPr(etree.fromstring(data[header_name]))
        except etree.XMLSyntaxError:
            black = None
    changed_members: set[str] = set()
    touched = 0
    for member, items in wanted.items():
        raw = data.get(member)
        if raw is None:
            continue
        try:
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError:
            continue
        paragraphs = [el for el in root.iter(_q("p"))]
        member_changed = False
        for spec in items:
            index = spec.get("paragraph_index")
            if not isinstance(index, int) or index < 0 or index >= len(paragraphs):
                continue
            paragraph = paragraphs[index]
            if _drop_owned_lineseg(paragraph):
                member_changed = True
                touched += 1
            if spec.get("expected_raw_text"):
                continue
            run_index = spec.get("run_index")
            if not isinstance(run_index, int) or black is None:
                continue
            runs = [child for child in paragraph if _local(getattr(child, "tag", "")) == "run"]
            if run_index < 0 or run_index >= len(runs):
                continue
            if black.fix_run(runs[run_index]):
                member_changed = True
                touched += 1
        if member_changed:
            standalone = _detect_standalone(raw)
            data[member] = etree.tostring(
                root, xml_declaration=True, encoding="UTF-8", standalone=standalone,
            )
            changed_members.add(member)
    if black is not None and black.changed and header_name in data:
        standalone = _detect_standalone(data[header_name])
        data[header_name] = etree.tostring(
            black.root, xml_declaration=True, encoding="UTF-8", standalone=standalone,
        )
        changed_members.add(header_name)
    if not changed_members:
        return 0
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.lineseg.tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            if "mimetype" in data:
                info = zipfile.ZipInfo("mimetype")
                info.compress_type = zipfile.ZIP_STORED
                zout.writestr(info, data["mimetype"])
            for info in infos:
                if info.filename == "mimetype":
                    continue
                copied = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                copied.compress_type = info.compress_type
                copied.external_attr = info.external_attr
                copied.internal_attr = info.internal_attr
                copied.create_system = info.create_system
                zout.writestr(copied, data[info.filename])
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    return touched


def _fill_section_xml(
    xml_bytes: bytes,
    identity: dict[str, str],
    replacements: dict[str, str],
    black: Optional[_BlackCharPr] = None,
    grid_confirm: Optional[list] = None,
    line_edits: Optional[list[dict]] = None,
    line_report: Optional[dict] = None,
    overflow_cells: Optional[list] = None,
    field_writes: Optional[dict[str, str]] = None,
    f01_bucket: Optional[dict[str, dict]] = None,
    span_notes: Optional[list] = None,
    existing_labels: Optional[list] = None,
) -> tuple[bytes, dict[str, str], int, set[str]]:
    """한 섹션 XML 에서 표 라벨-값 칸(1) + 셀 인라인 빈칸(1.5) + 체크박스(1.7) +
    그리드 선택칸(1.75, □ 없음) + 표 밖 본문 단락 인라인 빈칸(1.8) 채움 +
    (보호된) 직접 치환(2). grid_confirm: 그리드 needs_confirm 수집 리스트(선택).

    black: 유색 예시체 상속 차단용 헤더 charPr 관리자 — 표 라벨→값 경로와
    '값 전용 run' 치환 경로에 적용. 인라인 스플라이스(1.5/1.8)·텍스트 체크(1.7)는
    라벨과 서식 run 을 공유하는 구조라 미적용(naive 적용 시 라벨까지 검정화 =
    양식 변조) — 유색 잔존 가능성은 fill_hwpx docstring 에 명시(차기: run 분할).
    폼컨트롤 체크박스(check_options)는 문서 전체 유일성 판정이 필요해
    fill_hwpx 레벨(2-패스)에서 처리한다.

    반환: (새 XML 바이트, 채운 라벨→값, 치환건수, 채운 identity 라벨키 집합).
    변경이 없으면 입력 바이트를 그대로 반환한다(불필요한 재직렬화·선언 변형 회피).
    """
    root = etree.fromstring(xml_bytes)
    # lxml element proxy의 id()는 순회 중 재사용될 수 있으므로 위치 순서로 기준선을 잡는다.
    # 텍스트 편집은 문단을 추가/삭제하지 않으므로 paragraph_index가 이 경로의 안정 키다.
    before_text = [
        _owned_paragraph_text(paragraph)
        for paragraph in root.iter(_q("p"))
    ]
    if span_notes is None:
        span_notes = []
    if existing_labels is None:
        existing_labels = []
    filled: dict[str, str] = {}
    used_keys: set[str] = set()
    exact_held: set[str] = set()
    replaced = 0
    changed = False
    edited: list = []  # L074: lineseg strip 대상(편집된 tc/p)
    table_used: dict[Any, set[str]] = {}

    wants = [
        (_key(lbl), lbl, val)
        for lbl, val in identity.items()
        if str(val or "").strip()
    ]

    # 1) 표 라벨→값 칸 채움 (cellAddr 기반 값칸 선택 + 라벨칸 보호)
    for tbl in root.iter(_q("tbl")):
        table_used[tbl] = set()
        prior_support = _is_prior_support_table(tbl)
        for tr in _direct(tbl, "tr"):
            cells = _direct(tr, "tc")
            for tc in cells:
                cell_key = _key(_cell_text(tc))
                if not cell_key:
                    continue
                for want_key, lbl, val in wants:
                    if want_key in used_keys:
                        continue
                    if prior_support and _is_applicant_identity(want_key):
                        continue
                    if prior_support and _repeats_prior_support_header(tbl, tc):
                        continue
                    if _exact_identity_blocks_synonym(cell_key, want_key, wants, used_keys):
                        continue
                    if _held_for_other_label(exact_held, cell_key, want_key):
                        continue
                    if not _label_matches(cell_key, want_key):
                        continue
                    target = _current_period_value_cell(tbl, tc, cells)
                    if target is None or target is tc:
                        continue
                    if (
                        prior_support
                        and want_key in _PRIOR_SUPPORT_PROJECT_KEYS
                        and _prior_support_target_is_agency_column(tbl, target)
                    ):
                        continue
                    blue_example = _cell_has_blue_example_style(target, black)
                    if _is_label_like(target) and not blue_example:
                        continue  # 값칸 후보가 또 라벨 → 기입 금지
                    if _cell_has_nested_table(target):
                        _note_region(span_notes, "nested", lbl, target)
                        _hold_exact_label(exact_held, cell_key, want_key)
                        break
                    if _signature_seal_label(_cell_text(tc)) or _signature_seal_label(lbl):
                        _note_region(span_notes, "signature", lbl, target)
                        _hold_exact_label(exact_held, cell_key, want_key)
                        break
                    if _has_handwritten_object(target):
                        _note_region(span_notes, "handwritten", lbl, target)
                        _hold_exact_label(exact_held, cell_key, want_key)
                        break
                    if not _cell_is_fillable(target) and not blue_example:
                        # 실값만 EXISTING_VALUE. ____·더미날짜·□ 는 각자 게이트에 남긴다.
                        if _cell_has_real_value(target):
                            table_used[tbl].add(want_key)
                            _note_existing_value(span_notes, lbl, target, existing_labels)
                            _hold_exact_label(exact_held, cell_key, want_key)
                        break
                    scaffold = (
                        _is_hwpx_example_scaffold(_cell_text(target))
                        or _is_hwpx_guidance_placeholder(_cell_text(target))
                        or blue_example
                    )
                    if _split_value_spans(target) and (
                        not scaffold or _date_placeholder_crosses_spans(target)
                    ):
                        _note_unfilled_span(span_notes, lbl, target)
                        _hold_exact_label(exact_held, cell_key, want_key)
                        break
                    if _set_cell_text(target, str(val), black, replace_scaffold=scaffold):
                        filled[lbl] = str(val)
                        used_keys.add(want_key)
                        table_used[tbl].add(want_key)
                        changed = True
                        edited.append(target)
                        _note_overflow(overflow_cells, lbl, target, str(val))
                    break

    # 1.5) 셀 '안' 인라인 빈칸(`라벨 : ______`) 채움 — 표 경로 '뒤'에 실행하며
    #      동일한 used_keys 를 공유한다(AC7: 표가 채운 라벨은 인라인이 재채움 금지).
    #      scope 는 각 hp:p 의 직계 텍스트 흐름만(_inline_texts, AC8 — 중첩 표 제외).
    #      '가시 빈칸'(밑줄/점/대시 채움선)만 채운다 — '라벨 :'(콜론+공백만)은
    #      옆 값칸을 가리키는 경우와 구별이 안 되므로 제외(_is_visible_blank).
    if wants:
        for tc in root.iter(_q("tc")):
            owner_table = next((a for a in tc.iterancestors() if a.tag == _q("tbl")), None)
            inline_used = table_used.get(owner_table, used_keys)
            for sub in _direct(tc, "subList"):
                for p in _direct(sub, "p"):
                    if _fill_inline_fields_in_p(
                        p, wants, inline_used, filled, span_notes, existing_labels,
                        exact_held,
                    ):
                        changed = True
                        edited.append(p)
                        used_keys.update(inline_used)

    # 1.7) 체크박스(□→■) 자동 체크 — 인라인/왼쪽셀 라벨 그룹을 보수적으로 마킹.
    #      표(1)·인라인(1.5)과 동일한 used_keys 를 공유한다(이중처리 금지).
    #      값↔옵션은 _opt_key(꼬리 구두점 제거)·_normalize_choice 환원 후
    #      **정확일치가 정확히 1개**일 때만 체크
    #      (부분문자열 금지 — '개인정보'가 '개인'을 체크하면 안 됨. 0개/2개+ = 모호 → 스킵).
    #      ■ 는 □ 와 같은 1글자라 splice 후에도 flat offset 이 불변이고, 한 그룹당
    #      최대 1개 박스만 마킹(break)하므로 역순 처리 없이도 offset 이 유효하다.
    if wants:
        for tc in root.iter(_q("tc")):
            for sub in _direct(tc, "subList"):
                for p in _direct(sub, "p"):
                    ts = _inline_texts(p)
                    if not ts:
                        continue
                    flat = "".join(t.text or "" for t in ts)
                    inline_label, options = _parse_checkbox_options(flat)
                    if not options:
                        continue
                    # 그룹 라벨: 첫 □ 앞 텍스트(인라인) 우선, 비면 왼쪽 이웃 셀.
                    group_key = _key(inline_label or _left_label_text(tc))
                    if not group_key:
                        continue
                    for want_key, lbl, val in wants:
                        if want_key in used_keys:
                            continue
                        if _exact_identity_blocks_synonym(group_key, want_key, wants, used_keys):
                            continue
                        if _held_for_other_label(exact_held, group_key, want_key):
                            continue
                        if not _label_matches(group_key, want_key):
                            continue
                        vnorm = _normalize_choice(_opt_key(str(val)))
                        hits = [
                            pos for pos, opt_label in options
                            if _opt_key(opt_label)
                            and _normalize_choice(_opt_key(opt_label)) == vnorm
                        ]
                        if len(hits) != 1:
                            break   # 0개/다수 매칭 → 모호, 아무 박스도 안 건드림
                        if _span_crosses_text_nodes(p, hits[0], hits[0] + 1):
                            _note_unfilled_span(span_notes, lbl, tc)
                            _hold_exact_label(exact_held, group_key, want_key)
                            break
                        if _splice_run_text(p, hits[0], hits[0] + 1, _CHECK_MARK):
                            filled[lbl] = str(val)
                            used_keys.add(want_key)
                            changed = True
                            edited.append(p)
                        break

    # 1.75) 그리드 선택칸(□ 기호 없음) — 표의 셀 자체가 선택지이고 아래 빈 셀에
    #      마크(○/√)를 기입하는 구조. 실측: 중기부 공통서식(053) '취득방법(해당란에
    #      ‘○’표시)'·분류1~5·예비타당성, 수출바우처(016/128) '동의여부(해당란에
    #      √표시)', 서울AI허브 '신청 Track'(사용자 실기입 ○). 1.7 과 동일한
    #      used_keys 공유(이중처리 금지). 보수 규칙(오체크<미체크·날조0):
    #        ① 라벨 정확일치/동의어(_label_matches)
    #        ② 값↔옵션 _opt_key·_normalize_choice 환원 후 **정확일치 1개**
    #           (0개/2개+ = 모호 → 아무 칸도 안 건드림, 부분문자열 금지)
    #        ③ 마크행 전부 빈칸이어야 그룹 인정(이미 마크·값 있으면 보류 = 멱등)
    #        ④ **라벨에 마크 지시문("해당란에 ○표시" 류)이 있을 때만 자동 기입**
    #           (기입 기호 = 지시문 기호 그대로). 지시문 없는 구조·값 일치는
    #           needs_confirm 강등(자동 기입 금지) — grid_confirm 에 보고만.
    if wants:
        for tbl in root.iter(_q("tbl")):
            for label_key, mark, opts in _grid_choice_groups(tbl):
                for want_key, lbl, val in wants:
                    if want_key in used_keys:
                        continue
                    if _exact_identity_blocks_synonym(label_key, want_key, wants, used_keys):
                        continue
                    if _held_for_other_label(exact_held, label_key, want_key):
                        continue
                    if not _label_matches(label_key, want_key):
                        continue
                    vnorm = _normalize_choice(_opt_key(str(val)))
                    hits = [
                        mc for opt_text, mc in opts
                        if _opt_key(opt_text)
                        and _normalize_choice(_opt_key(opt_text)) == vnorm
                    ]
                    if len(hits) != 1:
                        break   # 0개/다수 매칭 → 모호, 아무 칸도 안 건드림
                    if mark is None:
                        if grid_confirm is not None:
                            grid_confirm.append(
                                f"{lbl}={val} — 그리드 선택칸 후보(마크 지시문 없음, "
                                "직접 확인 후 기입 필요)")
                        break   # 오체크 위험 → needs_confirm 강등(자동 기입 금지)
                    if _set_cell_text(hits[0], mark, black):
                        filled[lbl] = str(val)
                        used_keys.add(want_key)
                        changed = True
                        edited.append(hits[0])
                        _note_overflow(overflow_cells, lbl, hits[0], mark)
                    break

    # 1.8) 표 '밖' 본문 단락 인라인 필드(`라벨 : ______`) — hs:sec 직계 hp:p 만 대상.
    #      표 셀 안 단락(hp:tc 하위)은 1.5 가 담당 — 직계 자식만 보므로 자동 배제
    #      (중복 처리 금지). 채움 규칙은 1.5 와 동일 커널(_fill_inline_fields_in_p)
    #      공유: 가시 빈칸만(산문 `주의 : ...`·콜론+공백만 `비고 : ` 는 절대 안 채움)·
    #      used_keys 공유(표/인라인/체크박스와 이중 기입 금지)·형제 run 보존.
    if wants:
        body_used = used_keys
        for p in _direct(root, "p"):
            text = "".join(t.text or "" for t in _inline_texts(p)).strip()
            if re.search(r"서약서|확약서", text) and ":" not in text and "：" not in text:
                body_used = set()
            if _fill_inline_fields_in_p(
                p, wants, body_used, filled, span_notes, existing_labels,
                exact_held,
            ):
                changed = True
                edited.append(p)
                used_keys.update(body_used)

    # 2) 직접 텍스트 치환 — 라벨/실값 칸은 보호(채울 수 있는 칸·본문에만 적용).
    #    lxml proxy id 재사용을 피하려 id() 집합 대신 조상(tc) 순회로 판별한다.
    #    치환값도 유색 예시체 상속을 차단한다(적대검증 D9) — 단, 같은 run 의 다른
    #    hp:t 에 비치환 텍스트(안내문 등)가 남아 있으면 run 전체 색 교체가 양식을
    #    변조하므로 '값 전용 run'일 때만 검정화(보수 규칙).
    if replacements:
        for t in root.iter(_q("t")):
            cur = str(t.text or "")
            if not cur:
                continue
            if _in_protected_cell(t):       # 라벨·실값 칸의 hp:t 보호
                cell = _nearest_cell(t)
                if cell is not None and _cell_has_real_value(cell) and any(
                    old and str(rep or "").strip() and old in cur
                    for old, rep in replacements.items()
                ):
                    _note_existing_value(span_notes, _left_label_text(cell) or "value", cell)
                continue
            new = cur
            for old, rep in replacements.items():
                if old and str(rep or "").strip() and old in new:
                    new = new.replace(old, str(rep))
            if new != cur:
                t.text = new
                replaced += 1
                changed = True
                _invalidate_lineseg(t)
                # L074: 치환된 run 의 조상 p/tc 를 strip 범위에 포함.
                anc = t.getparent()
                while anc is not None:
                    loc = _local(getattr(anc, "tag", ""))
                    if loc in ("p", "tc"):
                        edited.append(anc)
                        break
                    anc = anc.getparent()
                if black is not None:
                    run = t.getparent()
                    if run is not None and _local(getattr(run, "tag", "")) == "run":
                        others = [x for x in _direct(run, "t")
                                  if x is not t and str(x.text or "").strip()]
                        if not others:
                            black.fix_run(run)

    # 3) 앵커 문단 한정 편집(line_edits) — 사용자가 명시한 지시만 수행.
    if line_edits:
        applied, line_notes = _apply_line_edits(root, line_edits, edited, black=black)
        if line_report is not None:
            line_report["applied"] = line_report.get("applied", 0) + applied
            line_report.setdefault("notes", []).extend(line_notes)
        if applied:
            changed = True

    if field_writes:
        f01_changed, written, skipped, style = _apply_f01_on_root(root, field_writes, edited)
        if f01_bucket is not None:
            f01_bucket["written"].update(written)
            f01_bucket["skipped"].update(skipped)
            f01_bucket["style"].update(style)
        if f01_changed:
            changed = True

    if not changed:
        return xml_bytes, filled, replaced, used_keys

    # L074: 실제 텍스트가 바뀐 문단만 줄좌표 캐시를 제거한다.
    # id(element)는 lxml proxy 재사용으로 미편집 제목을 다른 문단으로 오인할 수 있으므로
    # 위에서 잡은 paragraph_index 기준선과 비교한다. edited tc 전체를 재귀 strip 하지 않는다.
    for paragraph_index, paragraph in enumerate(root.iter(_q("p"))):
        if paragraph_index >= len(before_text):
            continue
        if _owned_paragraph_text(paragraph) == before_text[paragraph_index]:
            continue
        _drop_owned_lineseg(paragraph)

    standalone = _detect_standalone(xml_bytes)
    out = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=standalone
    )
    return out, filled, replaced, used_keys


def _detect_standalone(xml_bytes: bytes) -> Optional[bool]:
    """원본 XML 선언의 standalone 값을 보존(yes→True/no→False/없음→None)."""
    m = _STANDALONE_RE.search(xml_bytes[:200])
    if not m:
        return None
    return m.group(1) == b"yes"


def _same_file(src: Path, dst: Path) -> bool:
    """src·dst 가 같은 실파일인가 — inode 비교(하드링크 포함)까지 잡는다."""
    try:
        if src.exists() and dst.exists() and os.path.samefile(src, dst):
            return True
    except OSError:
        pass
    return src.resolve() == dst.resolve()


def fill_hwpx(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    *,
    identity: Optional[dict[str, str]] = None,
    replacements: Optional[dict[str, str]] = None,
    check_options: Optional[list[str]] = None,
    line_edits: Optional[list[dict]] = None,
    force_black: bool = True,
    field_writes: Optional[dict[str, str]] = None,
    expected_sha256: str | None = None,
) -> HwpxFillReport:
    """HWPX 원본 양식의 빈 값 칸을 직접 채운다(변환 왕복 없음, 양식 100% 보존).

    Args:
        in_hwpx: 입력 HWPX(원본, 절대 미수정).
        out_hwpx: 출력 HWPX(.hwpx). out==in(하드링크 포함)이면 ValueError.
        identity: 라벨→값. 예: {"기업명": "도보네비게이션(주)", "대표자": "홍길동"}.
                  동의어(상호/회사명 …)·표 라벨 장식(○·1.)은 자동 정규화 매칭.
        replacements: 직접 치환 {예시토큰: 실제값}. 라벨/실값 칸은 보호된다(선택).
        check_options: hp:checkBtn 폼 컨트롤로 체크할 옵션 라벨 목록
                  (예: ["경영분야", "사업계획&BM"]). 라벨은 같은 셀 캡션 →
                  오른쪽 인접 셀 순으로 찾고 괄호 보존 정확일치만 인정하며,
                  일치 컨트롤이 '문서 전체'에서 1개(셀당 컨트롤 1개)일 때만
                  체크한다(모호하면 잔여 보고 — 오체크<미체크).
        line_edits: 앵커 문단 한정 편집 지시 목록(사람이 명시한 것만 수행).
                  ``[{"anchor": "1. 개인정보 수집ㆍ이용 동의 여부",
                      "check": ["동의"],
                      "replace": {"(     )시": "(서울특별)시"}}]``
                  안내 문단 안에 선택지가 박힌 칸(워크넷 별지서식 `[ ] 동의`)처럼
                  라벨-값 매칭도 replacements 도 닿지 않는 자리를 채운다.
                  앵커는 문서 내 유일해야 하고, 옵션·치환 문자열도 그 문단에서
                  정확히 1개여야 적용한다(모호하면 스킵 + notes — 오편집<미편집).
        force_black: 호출 호환용. 값을 쓴 run 이 유색이거나 기울임(예시 안내체)이면
                  False 여도 글꼴·크기는 유지하고 검정·정자체 클론으로 바꾼다.
                  원본 charPr 와 손대지 않은 양식 글자는 그대로다. 라벨과 값을
                  한 run 에 이어 쓴 인라인은 라벨 서식을 유지한다. 헤더에
                  charPr 가 없으면 no-op.

    Returns:
        HwpxFillReport — 채운 항목·치환수·잔여(미매칭 라벨)·체크 결과·변경 섹션수.
    """
    src = Path(in_hwpx)
    dst = Path(out_hwpx)
    report = HwpxFillReport(input=str(src), output=str(dst))

    identity = {
        key: value for key, value in dict(identity or {}).items()
        if key not in _F01_SPECS
    }
    requested_writes = {
        key: str(value) for key, value in dict(field_writes or {}).items()
        if key in _F01_SPECS and str(value or "").strip()
    }
    replacements = dict(replacements or {})
    check_options = [str(o) for o in (check_options or []) if str(o or "").strip()]
    line_edits = [e for e in (line_edits or []) if isinstance(e, dict)]

    # 1) 안전장치
    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    from .submission_gates import (
        assert_not_announcement_form,
        estimate_page_count,
        page_count_increased,
    )
    assert_not_announcement_form(src)
    if _same_file(src, dst):
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    if src.suffix.lower() != ".hwpx":
        raise ValueError(f"HWPX 입력만 지원합니다: {src.name}")
    if dst.suffix.lower() != ".hwpx":
        raise ValueError(f"출력은 .hwpx 만 지원합니다: {dst.name}")
    if not zipfile.is_zipfile(src):
        raise ValueError(f"올바른 HWPX(ZIP)가 아닙니다: {src.name}")
    report.pages_before = estimate_page_count(src)
    if requested_writes and expected_sha256 and _sha256_file(src).lower() != expected_sha256.lower():
        report.template_status = "TEMPLATE_MISMATCH"
        report.notes.append(
            "TEMPLATE_MISMATCH: canonical SHA256과 다른 양식에는 F01 field_writes를 적용하지 않음"
        )
        for key in requested_writes:
            report.field_write_skipped[key] = "TEMPLATE_MISMATCH"
        requested_writes = {}

    # 2) ZIP 전체를 읽어 들인다(엔트리 순서·압축방식·내용 보존용).
    with zipfile.ZipFile(src) as zin:
        infos = zin.infolist()
        data: dict[str, bytes] = {i.filename: zin.read(i.filename) for i in infos}

    section_names = [i.filename for i in infos if _SECTION_RE.search(i.filename)]
    if not section_names:
        report.notes.append("Contents/section*.xml 을 찾지 못했습니다(빈 양식?).")

    # 2.5) 안내 스타일(유색·기울임) 차단 — 헤더 charPr 지도.
    # preserve_template 는 force_black=False 지만, 값을 넣는 run 이 예시 파란색·
    # 기울임이면 본문 스타일 클론으로 바꾼다. 안 건드린 charPr 는 그대로다.
    header_name = "Contents/header.xml"
    black: Optional[_BlackCharPr] = None
    if header_name in data:
        try:
            black = _BlackCharPr(etree.fromstring(data[header_name]))
        except etree.XMLSyntaxError:
            black = None
    # force_black 은 호출 호환용이다. 값을 쓴 run 이 유색·기울임이면 본문 클론을 쓴다.
    _ = force_black

    # 3) 섹션 XML 만 채움/치환
    all_used: set[str] = set()
    changed_names: set[str] = set()
    grid_confirm: list[str] = []
    overflow_cells: list[str] = []
    line_report: dict[str, Any] = {"applied": 0, "notes": []}
    f01_bucket: dict[str, dict] = {"written": {}, "skipped": {}, "style": {}}
    span_notes: list[str] = []
    existing_labels: list[str] = []
    for name in section_names:
        try:
            new_bytes, filled, replaced, used = _fill_section_xml(
                data[name], identity, replacements, black=black,
                grid_confirm=grid_confirm,
                line_edits=line_edits, line_report=line_report,
                overflow_cells=overflow_cells,
                field_writes=requested_writes if name == "Contents/section0.xml" else None,
                f01_bucket=f01_bucket if name == "Contents/section0.xml" else None,
                span_notes=span_notes,
                existing_labels=existing_labels,
            )
        except etree.XMLSyntaxError as exc:
            report.notes.append(f"{name} 파싱 실패(건너뜀): {exc}")
            continue
        if new_bytes != data[name]:
            data[name] = new_bytes
            changed_names.add(name)
        report.filled.update(filled)
        report.replaced += replaced
        all_used |= used
    report.field_writes_written.update(f01_bucket["written"])
    report.field_write_skipped.update(f01_bucket["skipped"])
    report.field_write_style.update(f01_bucket["style"])
    for note in span_notes:
        if note not in report.notes:
            report.notes.append(note)

    # 3.3) 폼 컨트롤 체크박스(hp:checkBtn) 2-패스 — '문서 전체' 유일성 판정.
    #      (섹션 단위 판정은 다섹션 양식에서 전역 모호 라벨을 오체크 — 적대검증.)
    #      후보 규칙: 셀당 컨트롤 정확히 1개(예/아니오 스택 셀은 모호) ×
    #      라벨(_checkbtn_label: 같은셀 캡션 1순위·오른쪽 인접 2순위·컨트롤 셀
    #      불인정) 괄호 보존 정확일치(_opt_key_preserving). 문서 전체 후보가
    #      정확히 1개일 때만 value="CHECKED" — ■ 텍스트는 넣지 않는다.
    #      이미 CHECKED 면 변경·보고 없이 멱등 처리(불필요 재직렬화 회피).
    check_done: set[str] = set()
    if check_options:
        sec_roots: dict[str, Any] = {}
        for name in section_names:
            try:
                sec_roots[name] = etree.fromstring(data[name])
            except etree.XMLSyntaxError:
                continue
        dirty: set[str] = set()
        for opt in check_options:
            if opt in check_done:
                continue
            want = _opt_key_preserving(opt)
            if not want:
                continue
            cands: list = []                      # (섹션명, checkBtn)
            for name, sroot in sec_roots.items():
                for tbl in sroot.iter(_q("tbl")):
                    for tr in _direct(tbl, "tr"):
                        cells = _direct(tr, "tc")
                        for tc in cells:
                            btns = _direct_form_checkbtns(tc)
                            if len(btns) != 1:
                                continue
                            if _opt_key_preserving(
                                    _checkbtn_label(tc, cells)) == want:
                                cands.append((name, btns[0]))
            if len(cands) != 1:
                continue                          # 0/다수 = 모호 → 미체크(잔여 보고)
            name, btn = cands[0]
            if btn.get("value") == "CHECKED":
                check_done.add(opt)               # 멱등 — 변경·checked 보고 없음
                report.notes.append(f"'{opt}' 는 이미 체크되어 있어 변경하지 않았습니다.")
                continue
            btn.set("value", "CHECKED")
            check_done.add(opt)
            report.checked.append(str(opt))
            dirty.add(name)
        for name in dirty:
            standalone = _detect_standalone(data[name])
            data[name] = etree.tostring(
                sec_roots[name], xml_declaration=True, encoding="UTF-8",
                standalone=standalone,
            )
            changed_names.add(name)

    report.sections_changed = len(changed_names)

    # 3.5) 검정 클론이 생겼으면 헤더도 갱신(기존 항목 불변·클론 추가만).
    if black is not None and black.changed:
        standalone = _detect_standalone(data[header_name])
        data[header_name] = etree.tostring(
            black.root, xml_declaration=True, encoding="UTF-8",
            standalone=standalone,
        )

    # 3.6) fill 만 타고 submit 을 안 타도 과압축 자간을 완화한다(L 자간 하한).
    #      변경이 없으면 원본 헤더 바이트를 그대로 둔다(양식 보존 테스트).
    if header_name in data:
        try:
            from .hwpx_layout_fix import clamp_letter_spacing
            hroot = etree.fromstring(data[header_name])
            n_sp = clamp_letter_spacing(hroot)
            if n_sp:
                standalone = _detect_standalone(data[header_name])
                data[header_name] = etree.tostring(
                    hroot, xml_declaration=True, encoding="UTF-8",
                    standalone=standalone,
                )
                report.notes.append(f"자간 하한 clamp {n_sp}건")
        except etree.XMLSyntaxError:
            pass

    report.overflow_cells = list(dict.fromkeys(overflow_cells))
    if report.overflow_cells:
        report.notes.append(
            "한 줄 칸 넘침 가능(L097): " + "; ".join(report.overflow_cells))

    report.filled_count = len(report.filled)
    report.residual = [
        lbl
        for lbl, val in identity.items()
        if str(val or "").strip() and _key(lbl) not in all_used
    ]
    for label in existing_labels:
        if label not in report.residual:
            report.residual.append(label)
    report.check_residual = [o for o in check_options if o not in check_done]
    if report.check_residual:
        report.notes.append(
            "체크하지 못한 옵션(라벨 부재 또는 동일 라벨 다수=모호): "
            + ", ".join(report.check_residual))
    report.grid_needs_confirm = list(dict.fromkeys(grid_confirm))
    if report.grid_needs_confirm:
        report.notes.append(
            "그리드 선택칸 확인 필요(마크 지시문이 없어 자동 기입하지 않음): "
            + "; ".join(report.grid_needs_confirm))
    report.line_edits_applied = int(line_report.get("applied", 0))
    for note in dict.fromkeys(line_report.get("notes", [])):
        report.notes.append(f"[line_edits] {note}")

    # 4) 원자적 쓰기 — 임시파일에 다시 압축 후 os.replace.
    #    mimetype 선두 + STORED, 그 외 원본 압축방식·내용 유지.
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.stem}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            if "mimetype" in data:
                zi = zipfile.ZipInfo("mimetype")
                zi.compress_type = zipfile.ZIP_STORED
                zout.writestr(zi, data["mimetype"])
            for info in infos:
                name = info.filename
                if name == "mimetype":
                    continue
                zi = zipfile.ZipInfo(name, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zout.writestr(zi, data[name])
        os.replace(tmp, dst)
    except BaseException:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise

    report.pages_after = estimate_page_count(dst)
    if page_count_increased(report.pages_before, report.pages_after):
        report.notes.append(
            f"L095 페이지 증가 {report.pages_before}→{report.pages_after} "
            "(XML 추정, 한글 렌더 쪽수는 L005)"
        )

    report.ok = report.template_status != "TEMPLATE_MISMATCH"
    if not report.filled and not report.replaced and not report.checked and not report.field_writes_written and not report.template_status:
        report.notes.append(
            "채운 칸이 없습니다 — 라벨이 양식과 일치하지 않거나 칸에 이미 값이 "
            "있을 수 있습니다(덮어쓰기 금지). identity 라벨/값을 확인하세요.")
    # Reporting only: a repeated label used on the first row still leaves later
    # empty value cells. The write loop above is unchanged.
    if dst.is_file():
        from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
        from core.docx.services.hwpx_protected_regions import (
            document_duplicate_unfilled_cells,
            repeated_row_unfilled_labels,
        )

        filled_index = index_hwpx_structure(dst)
        for label in repeated_row_unfilled_labels(filled_index):
            if label not in report.residual:
                report.residual.append(label)
        for label, _section_index, _table_index, _row, _col in document_duplicate_unfilled_cells(filled_index):
            if label not in report.residual:
                report.residual.append(label)
    return report


# F-01 GovTech 아이디어 기획서. Astra write map (2026-09-26)의 7개 위치만 기입한다.
# 주제·문제해결·사업화의 새 문단은 원본에 빈 run이 없다.
# 본문 스타일은 같은 양식 header의 charPr 35다.
# 11pt(#000000), 굵게/기울임 없음, 자간 0. 안내문 49·67(회색 기울임)과
# 짧은 입력칸 65(굵게, 자간 -4)는 새 서술 문단에 쓰지 않는다.
# paraPr 1 / style 0 은 그 칸들의 바탕글이다.
# rhwp에서 char 35와 65의 쪽 넘침은 빈 양식과 같은 page2 para 35/36, 7.5px뿐이었다.
F01_CANONICAL_SHA256 = "e818bc0fa8a6ff9267b2379072e4e9e4f484f22ff7cac13b1619623e7508a187"
F01_NEW_BODY_CHARPR = "35"
_F01_NEW_PARA = {"paraPrIDRef": "1", "styleIDRef": "0", "pageBreak": "0", "columnBreak": "0", "merged": "0"}
_F01_NEW_CHAR = F01_NEW_BODY_CHARPR

# (table, row, col, colAddr, rowAddr, mode, fill_at or None)
# fill_at = (paragraph_index, run_index) when an existing empty run receives the first paragraph.
_F01_SPECS: dict[str, dict[str, Any]] = {
    "participant_name": {
        "table": 2, "row": 0, "col": 1, "col_addr": "1", "row_addr": "0",
        "mode": "RIGHT_VALUE_CELL", "fill_at": (0, 0), "new_style": False,
        "neighbor": (0, " 참가자(팀)명"),
        "own": [(("65", None),)],
    },
    "project_topic": {
        "table": 2, "row": 1, "col": 1, "col_addr": "1", "row_addr": "1",
        "mode": "INSERT_AFTER_GUIDANCE", "fill_at": None, "new_style": True,
        "neighbor": (0, " 참가작 주제"),
        "own": [(("67", "※ 참가작 주제는 한 문장으로 참가작 내용, 목적 등을 명확하게 파악할 수 있도록 기재하여야 함"),)],
    },
    "project_summary": {
        "table": 2, "row": 3, "col": 0, "col_addr": "0", "row_addr": "3",
        "mode": "APPEND_PARAGRAPH_IN_CELL", "fill_at": (0, 0), "new_style": False,
        "above": (2, 0, "참가작 주요내용 요약"),
        "own": [(("65", None),)],
    },
    "problem_validity": {
        "table": 5, "row": 1, "col": 0, "col_addr": "0", "row_addr": "1",
        "mode": "APPEND_PARAGRAPH_IN_CELL", "fill_at": None, "new_style": True,
        "titles": ((0, " 1. 문제 해결의 타당성"), (1, " ◈ 아이디어의 개발 동기, 배경 및 필요성")),
        "own": [
            (("35", " "), ("49", " 1-1. 아이디어에 대한 동기(내·외부적 동기 등) 및 배경 제시")),
            (("49", "  1-2. 아이디어의 필요성 및 사회적 이슈와의 관련성"),),
        ],
    },
    "commercialization": {
        "table": 6, "row": 1, "col": 0, "col_addr": "0", "row_addr": "1",
        "mode": "APPEND_PARAGRAPH_IN_CELL", "fill_at": None, "new_style": True,
        "titles": ((0, " 2. 사업화 가능성"), (1, " ◈ 실행계획, 실현가능성 및 차별성")),
        "own": [
            (("35", "  "), ("49", "2-1. 구체적 실행계획 및 기술적 실현 가능성 ")),
            (("49", "  2-2. 유사 아이디어 대비 차별성"),),
        ],
    },
    "sustainability": {
        "table": 7, "row": 1, "col": 0, "col_addr": "0", "row_addr": "1",
        "mode": "INSERT_AFTER_GUIDANCE", "fill_at": (2, 0), "new_style": False,
        "title_runs": (
            (0, ((None, " 3. 지속가능성과"), (None, "    사회적 기여"))),
        ),
        "title_cell": (1, " ◈ 기술의 적절성, 성장가능성 및 공공서비스 혁신성"),
        "own": [
            (("49", " 3-1. 기술 활용의 적절성, 발전 가능성"),),
            (("49", " 3-2. 기술 적용을 통한 국민 편익, 행정 효율 등 개선점 제시"),),
            (("49", None),),
        ],
    },
    "entrepreneurship": {
        "table": 8, "row": 1, "col": 0, "col_addr": "0", "row_addr": "1",
        "mode": "INSERT_AFTER_GUIDANCE", "fill_at": (2, 0), "new_style": False,
        "titles": ((0, " 4. 기업가 정신"), (1, " ◈ 주도성 및 실행 의지")),
        "own": [
            (("35", "  "), ("49", "4-1. 아이디어 구체화를 위해 진행한 사항")),
            (("49", "  ㅇ 현장 조사, 인터뷰, 기술 검토, 유사 사례 분석 등 사전 노력 기술"),),
            (("49", None),),
        ],
    },
}
F01_FIELD_KEYS = frozenset(_F01_SPECS)


@dataclass
class F01WriteReport:
    input: str
    output: str
    ok: bool = False
    written: dict[str, str] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    style_status: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_payload(run) -> tuple[str, str | None]:
    texts = _direct(run, "t")
    if not texts:
        return run.get("charPrIDRef") or "", None
    return run.get("charPrIDRef") or "", "".join(t.text or "" for t in texts)


def _cell_payload(tc) -> list[tuple[tuple[str, str | None], ...]]:
    subs = _direct(tc, "subList")
    if len(subs) != 1:
        return []
    rows = []
    for para in _direct(subs[0], "p"):
        rows.append(tuple(_run_payload(run) for run in _direct(para, "run")))
    return rows


def _cell_joined(tc) -> str:
    return "".join(t.text or "" for t in _direct_all_t(tc))


def _direct_all_t(tc) -> list:
    subs = _direct(tc, "subList")
    if len(subs) != 1:
        return []
    found = []
    for para in _direct(subs[0], "p"):
        for run in _direct(para, "run"):
            found.extend(_direct(run, "t"))
    return found


def _tc_at(root, table: int, row: int, col: int):
    tables = [el for el in root.iter(_q("tbl"))]
    if table >= len(tables):
        return None
    rows = _direct(tables[table], "tr")
    if row >= len(rows):
        return None
    cells = _direct(rows[row], "tc")
    if col >= len(cells):
        return None
    return cells[col]


def _addr_ok(tc, col_addr: str, row_addr: str) -> bool:
    addr = next(iter(_direct(tc, "cellAddr")), None)
    return addr is not None and addr.get("colAddr") == col_addr and addr.get("rowAddr") == row_addr


def _f01_anchor_error(root, spec: dict[str, Any]) -> str:
    tc = _tc_at(root, spec["table"], spec["row"], spec["col"])
    if tc is None or not _addr_ok(tc, spec["col_addr"], spec["row_addr"]):
        return "셀 주소 불일치"
    if _cell_payload(tc) != [tuple(para) for para in spec["own"]]:
        return "대상 셀 paragraph/run 불일치"
    if "neighbor" in spec:
        left = _tc_at(root, spec["table"], spec["row"], spec["neighbor"][0])
        if left is None or _cell_joined(left) != spec["neighbor"][1]:
            return "옆 라벨 불일치"
    if "above" in spec:
        above = _tc_at(root, spec["table"], spec["above"][0], spec["above"][1])
        if above is None or _cell_joined(above) != spec["above"][2]:
            return "위 제목 불일치"
    title_row = _direct([el for el in root.iter(_q("tbl"))][spec["table"]], "tr")[0]
    title_cells = _direct(title_row, "tc")
    if "titles" in spec:
        for index, text in spec["titles"]:
            if index >= len(title_cells) or _cell_joined(title_cells[index]) != text:
                return "제목 행 불일치"
    if "title_cell" in spec:
        index, text = spec["title_cell"]
        if index >= len(title_cells) or _cell_joined(title_cells[index]) != text:
            return "제목 행 불일치"
    if "title_runs" in spec:
        for index, expected in spec["title_runs"]:
            if index >= len(title_cells):
                return "제목 행 불일치"
            paras = _cell_payload(title_cells[index])
            flat_text = tuple("".join("" if text is None else text for _, text in para) for para in paras)
            want = tuple(piece[1] for piece in expected)
            if flat_text != want:
                return "제목 행 문단 불일치"
    return ""


def _append_body_paragraph(sublist, text: str, *, para_attrs: dict[str, str], char_pr: str):
    para = etree.Element(_q("p"))
    para.set("id", "2147483648")
    for key, value in para_attrs.items():
        para.set(key, value)
    run = etree.SubElement(para, _q("run"))
    run.set("charPrIDRef", char_pr)
    node = etree.SubElement(run, _q("t"))
    node.text = text
    sublist.append(para)
    return para


def _put_run_text(run, text: str) -> None:
    node = etree.SubElement(run, _q("t"))
    node.text = text
    _invalidate_lineseg(run)


def _paragraphs_of(value: str) -> list[str]:
    return [line for line in str(value).splitlines() if line.strip()]


def _apply_f01_on_root(root, values: dict[str, str], edited: list) -> tuple[bool, dict[str, str], dict[str, str], dict[str, str]]:
    """section XML 루트에 F-01 7개 write target만 반영한다. ZIP 쓰기는 하지 않는다."""
    written: dict[str, str] = {}
    skipped: dict[str, str] = {}
    style: dict[str, str] = {}
    changed = False
    for key, spec in _F01_SPECS.items():
        raw = values.get(key)
        if raw is None or not str(raw).strip():
            continue
        reason = _f01_anchor_error(root, spec)
        if reason:
            skipped[key] = f"REVIEW_REQUIRED: {reason}"
            continue
        paragraphs = _paragraphs_of(str(raw))
        if not paragraphs:
            continue
        tc = _tc_at(root, spec["table"], spec["row"], spec["col"])
        sublist = _direct(tc, "subList")[0]
        paras = _direct(sublist, "p")
        fill_at = spec["fill_at"]
        body = paragraphs
        if fill_at is not None:
            para = paras[fill_at[0]]
            run = _direct(para, "run")[fill_at[1]]
            _put_run_text(run, body[0])
            edited.append(para)
            extra_attrs = {
                "paraPrIDRef": para.get("paraPrIDRef") or "1",
                "styleIDRef": para.get("styleIDRef") or "0",
                "pageBreak": para.get("pageBreak") or "0",
                "columnBreak": para.get("columnBreak") or "0",
                "merged": para.get("merged") or "0",
            }
            extra_char = run.get("charPrIDRef") or _F01_NEW_CHAR
            body = body[1:]
        else:
            extra_attrs = dict(_F01_NEW_PARA)
            extra_char = _F01_NEW_CHAR
        for text in body:
            created = _append_body_paragraph(sublist, text, para_attrs=extra_attrs, char_pr=extra_char)
            edited.append(created)
        written[key] = spec["mode"]
        if spec["new_style"]:
            style[key] = "CONFIRMED_CHARPR_35"
        changed = True
    return changed, written, skipped, style


def apply_f01_field_writes(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    values: dict[str, str],
    *,
    expected_sha256: str | None = None,
) -> F01WriteReport:
    """F-01 7개 값을 ``fill_hwpx`` 한 경로로 기록한다."""
    filled = fill_hwpx(
        in_hwpx,
        out_hwpx,
        field_writes=values,
        force_black=False,
        expected_sha256=expected_sha256,
    )
    report = F01WriteReport(
        input=filled.input,
        output=filled.output,
        written=dict(filled.field_writes_written),
        skipped=dict(filled.field_write_skipped),
        style_status=dict(filled.field_write_style),
        notes=list(filled.notes),
    )
    report.ok = not report.skipped and bool(
        report.written or not any(str(value or "").strip() for value in values.values())
    )
    return report


@dataclass(frozen=True)
class ExactTextTarget:
    """One hp:t. The writer may replace that node's text and nothing else."""

    section_member: str
    paragraph_index: int
    run_index: int
    text_node_index: int | None
    expected_raw_text: str
    value: str
    table_index: int | None = None
    row: int | None = None
    col: int | None = None
    preserve_prefix: bool = False
    choice_flip: bool = False


@dataclass
class ExactWriteReport:
    input: str
    output: str
    ok: bool = False
    cancelled: bool = True
    reason: str = ""
    written_count: int = 0
    reasons: list[str] = field(default_factory=list)


def _raw_text_node(node) -> str:
    parts = [node.text or ""]
    for child in list(node):
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _section_text_nodes(root) -> dict[tuple[int, int, int], Any]:
    """Map indexer-order (paragraph, run, text) to the hp:t element."""
    found: dict[tuple[int, int, int], Any] = {}
    paragraph_index = 0
    for paragraph in root.iter(_q("p")):
        run_index = 0
        for child in list(paragraph):
            if _local(child.tag) != "run":
                continue
            text_index = 0
            for sub in list(child):
                if _local(sub.tag) != "t":
                    continue
                found[(paragraph_index, run_index, text_index)] = sub
                text_index += 1
            run_index += 1
        paragraph_index += 1
    return found


def _snapshot_text(root) -> dict[tuple[int, int, int], str]:
    return {key: _raw_text_node(node) for key, node in _section_text_nodes(root).items()}


def _section_runs(root) -> dict[tuple[int, int], Any]:
    found: dict[tuple[int, int], Any] = {}
    paragraph_index = 0
    for paragraph in root.iter(_q("p")):
        run_index = 0
        for child in list(paragraph):
            if _local(child.tag) != "run":
                continue
            found[(paragraph_index, run_index)] = child
            run_index += 1
        paragraph_index += 1
    return found


def _is_exact_choice_flip(before: str, after: str) -> bool:
    """True when the only change is the leading empty box becoming a checked box."""
    if not before or not after or before[0] not in "□☐" or after[0] != "■":
        return False
    return before[1:] == after[1:]


def _protected_existing_text(text: str) -> bool:
    """Refuse to replace guidance, a seal line, a date scaffold, or a choice mark."""
    if not (text or "").strip():
        return False
    from core.docx.services.hwpx_protected_regions import (
        _CHOICE_MARK_RE,
        _SIGNATURE_RE,
        _is_date_scaffold_paragraph,
        guidance_status,
    )
    if guidance_status(text) == "guidance":
        return True
    if _SIGNATURE_RE.search(text) or _is_date_scaffold_paragraph(text):
        return True
    return _CHOICE_MARK_RE.search(text) is not None


def _coordinates_match(src: Path, targets: list[ExactTextTarget]) -> str:
    """Return a reason when a supplied table cell does not contain the run."""
    if not any(target.table_index is not None for target in targets):
        return ""
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
    index = index_hwpx_structure(src)
    if index.analysis_status != "COMPLETE":
        return "INDEX_INCOMPLETE"
    for target in targets:
        if target.table_index is None:
            continue
        section = next((item for item in index.sections if item.section_member == target.section_member), None)
        if section is None or target.paragraph_index >= len(section.paragraphs):
            return "COORDINATE_MISMATCH"
        paragraph = section.paragraphs[target.paragraph_index]
        if paragraph.table_index != target.table_index or target.table_index >= len(index.tables):
            return "COORDINATE_MISMATCH"
        table = index.tables[target.table_index]
        owner = next((cell for cell in table.cells if target.paragraph_index in cell.paragraph_indexes), None)
        if owner is None or owner.row != target.row or owner.col != target.col:
            return "COORDINATE_MISMATCH"
        if target.run_index >= len(paragraph.runs):
            return "COORDINATE_MISMATCH"
    return ""


def commit_exact_text_writes(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    targets: list[ExactTextTarget],
    *,
    source_sha256: str,
) -> ExactWriteReport:
    """Write exact hp:t nodes, or write nothing.

    Legacy ``fill_hwpx`` is unchanged. This path refuses partial writes, header
    edits, substring search, and any change outside the approved text nodes.
    """
    src = Path(in_hwpx)
    dst = Path(out_hwpx)
    report = ExactWriteReport(input=str(src), output=str(dst))
    if not src.exists():
        raise FileNotFoundError(src)
    if _same_file(src, dst):
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    before_src = src.read_bytes()
    actual_sha = hashlib.sha256(before_src).hexdigest()
    if actual_sha.lower() != str(source_sha256 or "").lower():
        report.reason = "SHA_MISMATCH"
        report.reasons.append("SHA_MISMATCH")
        return report
    if not targets:
        report.reason = "EMPTY_PLAN"
        report.reasons.append("EMPTY_PLAN")
        return report
    seen: set[tuple[str, int, int, int]] = set()
    for target in targets:
        key = (target.section_member, target.paragraph_index, target.run_index, target.text_node_index)
        if key in seen:
            report.reason = "DUPLICATE_TARGET"
            report.reasons.append("DUPLICATE_TARGET")
            return report
        seen.add(key)

    with zipfile.ZipFile(src) as zin:
        infos = zin.infolist()
        data = {info.filename: zin.read(info.filename) for info in infos}
    original = dict(data)
    roots: dict[str, Any] = {}
    located: dict[tuple[str, int, int, int], Any] = {}
    for target in targets:
        if target.section_member not in data:
            report.reasons.append(f"SECTION_MISSING:{target.section_member}")
            continue
        if target.section_member not in roots:
            try:
                roots[target.section_member] = etree.fromstring(data[target.section_member])
            except etree.XMLSyntaxError:
                report.reasons.append(f"SECTION_XML:{target.section_member}")
                continue
        if target.text_node_index is None:
            run = _section_runs(roots[target.section_member]).get((target.paragraph_index, target.run_index))
            direct_children = list(run) if run is not None else []
            has_text = any(_local(child.tag) == "t" for child in direct_children)
            has_table = any(_local(child.tag) == "tbl" for child in direct_children)
            if run is None or has_text or has_table or target.expected_raw_text != "":
                report.reasons.append(
                    f"EMPTY_RUN_MISMATCH:{target.paragraph_index}:{target.run_index}"
                )
                continue
            if _protected_existing_text("".join(_raw_text_node(child) for child in direct_children)):
                report.reasons.append(
                    f"PROTECTED_TEXT:{target.paragraph_index}:{target.run_index}"
                )
                continue
            located[(target.section_member, target.paragraph_index, target.run_index, None)] = run
            continue
        nodes = _section_text_nodes(roots[target.section_member])
        node = nodes.get((target.paragraph_index, target.run_index, target.text_node_index))
        if node is None:
            report.reasons.append(
                f"TARGET_MISSING:{target.paragraph_index}:{target.run_index}:{target.text_node_index}"
            )
            continue
        if list(node):
            report.reasons.append(
                f"SPAN_NOT_PLAIN:{target.paragraph_index}:{target.run_index}:{target.text_node_index}"
            )
            continue
        current = _raw_text_node(node)
        if current != target.expected_raw_text:
            report.reasons.append(
                f"EXPECTED_TEXT_MISMATCH:{target.paragraph_index}:{target.run_index}:{target.text_node_index}"
            )
            continue
        choice_ok = (
            target.choice_flip
            and current == target.expected_raw_text
            and _is_exact_choice_flip(current, target.value)
        )
        if current.strip() and not target.preserve_prefix and not choice_ok:
            report.reasons.append(
                f"EXISTING_VALUE:{target.paragraph_index}:{target.run_index}:{target.text_node_index}"
            )
            continue
        if _protected_existing_text(current) and not choice_ok:
            report.reasons.append(
                f"PROTECTED_TEXT:{target.paragraph_index}:{target.run_index}:{target.text_node_index}"
            )
            continue
        if current.strip() and target.preserve_prefix:
            prefix_ok = (
                current == target.expected_raw_text
                and target.value.startswith(current)
                and target.value[len(current):].strip() != ""
            )
            if not prefix_ok:
                report.reasons.append(
                    f"EXISTING_VALUE:{target.paragraph_index}:{target.run_index}:{target.text_node_index}"
                )
                continue
        located[(target.section_member, target.paragraph_index, target.run_index, target.text_node_index)] = node
    if report.reasons or len(located) != len(targets):
        report.reason = report.reasons[0] if report.reasons else "PLAN_REJECTED"
        report.cancelled = True
        report.ok = False
        return report
    coordinate_reason = _coordinates_match(src, targets)
    if coordinate_reason:
        report.reason = coordinate_reason
        report.reasons.append(coordinate_reason)
        report.cancelled = True
        report.ok = False
        return report

    snapshots = {name: _snapshot_text(root) for name, root in roots.items()}
    for target in targets:
        node = located[(target.section_member, target.paragraph_index, target.run_index, target.text_node_index)]
        if target.text_node_index is None:
            created = etree.SubElement(node, _q("t"))
            created.text = target.value
        else:
            node.text = target.value
    for name, root in roots.items():
        after = _snapshot_text(root)
        before = snapshots[name]
        approved = {
            (target.paragraph_index, target.run_index, 0 if target.text_node_index is None else target.text_node_index): target.value
            for target in targets if target.section_member == name
        }
        expected_keys = set(before)
        expected_keys.update(approved)
        if set(after) != expected_keys:
            report.reason = "STRUCTURE_CHANGED"
            report.reasons.append("STRUCTURE_CHANGED")
            return report
        for key, raw in after.items():
            if key in approved:
                if raw != approved[key]:
                    report.reason = "WRITE_SPAN_MISMATCH"
                    report.reasons.append("WRITE_SPAN_MISMATCH")
                    return report
            elif raw != before[key]:
                report.reason = "OUT_OF_SCOPE_TEXT"
                report.reasons.append("OUT_OF_SCOPE_TEXT")
                return report
        standalone = _detect_standalone(original[name])
        data[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=standalone)

    for name, payload in data.items():
        if name not in roots and payload != original[name]:
            report.reason = "OUT_OF_SCOPE_XML"
            report.reasons.append("OUT_OF_SCOPE_XML")
            return report

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f"{dst.stem}.{os.getpid()}.exact.tmp")
    replaced = False

    def _drop_output() -> None:
        nonlocal replaced
        if tmp.exists():
            tmp.unlink()
        if replaced and dst.exists():
            dst.unlink()
            replaced = False

    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            if "mimetype" in data:
                info = zipfile.ZipInfo("mimetype")
                info.compress_type = zipfile.ZIP_STORED
                zout.writestr(info, data["mimetype"])
            for info in infos:
                if info.filename == "mimetype":
                    continue
                copied = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                copied.compress_type = info.compress_type
                copied.external_attr = info.external_attr
                copied.internal_attr = info.internal_attr
                copied.create_system = info.create_system
                zout.writestr(copied, data[info.filename])
        if src.read_bytes() != before_src:
            report.reason = "SOURCE_MUTATED"
            report.reasons.append("SOURCE_MUTATED")
            report.ok = False
            report.cancelled = True
            return report
        from core.docx.services.hwpx_xml_scope_diff import XmlScopeTarget, compare_hwpx_xml_scope
        try:
            diff = compare_hwpx_xml_scope(
                src, tmp,
                [XmlScopeTarget(item.section_member, item.paragraph_index, item.run_index, item.text_node_index) for item in targets],
                expected_sha256=actual_sha,
            )
        except Exception as exc:
            report.reason = "XML_SCOPE_ERROR"
            report.reasons.append(f"XML_SCOPE_ERROR:{exc.__class__.__name__}")
            report.ok = False
            report.cancelled = True
            return report
        if src.read_bytes() != before_src:
            report.reason = "SOURCE_MUTATED"
            report.reasons.append("SOURCE_MUTATED")
            report.ok = False
            report.cancelled = True
            return report
        if not diff.ok or diff.unexpected_count or not diff.sha_ok:
            report.reason = "OUT_OF_SCOPE_XML_CHANGE"
            report.reasons.append("OUT_OF_SCOPE_XML_CHANGE")
            report.ok = False
            report.cancelled = True
            return report
        os.replace(tmp, dst)
        replaced = True
        if src.read_bytes() != before_src:
            report.reason = "SOURCE_MUTATED"
            report.reasons.append("SOURCE_MUTATED")
            report.ok = False
            report.cancelled = True
            _drop_output()
            return report
    except BaseException:
        _drop_output()
        raise
    finally:
        if tmp.exists():
            tmp.unlink()
    report.ok = True
    report.cancelled = False
    report.reason = "WRITTEN"
    report.written_count = len(targets)
    return report


def _labels_holding_real_values(index) -> set[str]:
    """T02 labels whose value cell already holds prose or a number."""
    from core.docx.services.hwpx_protected_regions import _cell_joined, _label_value_pairs

    sections = {section.section_index: section for section in index.sections}
    found: set[str] = set()
    for section_index, _table_index, label, value, empty in _label_value_pairs(index):
        if empty or not label:
            continue
        section = sections.get(section_index)
        if section is None:
            continue
        if _real_existing_text(_cell_joined(section, value)):
            found.add(label)
    return found


def commit_t02_label_writes(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    values: dict[str, str],
) -> ExactWriteReport:
    """Refuse analyzer writes until an internal authorization recheck passes.

    A T02 candidate is not a write. ``auto_write_allowed`` on a caller-built
    record is ignored. A horizontal merged value grant uses the same exact
    writer and the same all-or-nothing refusal. Legacy ``commit_exact_text_writes``
    stays a separate coordinate contract.
    """
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure

    src = Path(in_hwpx)
    dst = Path(out_hwpx)
    report = ExactWriteReport(input=str(src), output=str(dst))
    index = index_hwpx_structure(src)
    if index.analysis_status != "COMPLETE":
        report.reason = "INDEX_INCOMPLETE"
        report.reasons.append("INDEX_INCOMPLETE")
        return report
    wanted = {re.sub(r"\s+", "", key).rstrip(":："): str(value) for key, value in values.items() if str(value or "").strip()}
    if not wanted:
        report.reason = "EMPTY_PLAN"
        report.reasons.append("EMPTY_PLAN")
        return report
    from core.docx.services.hwpx_protected_regions import (
        authorization_is_current,
        authorize_merged_value_writes,
        authorize_nested_leaf_writes,
        authorize_checkbox_writes,
        authorize_guidance_narrative_writes,
        authorize_inline_field_writes,
        authorize_repeated_row_writes,
        authorize_t02_writes,
        checkbox_authorization_is_current,
        checkbox_replacement,
        guidance_authorization_is_current,
        inline_authorization_is_current,
        merged_authorization_is_current,
        nested_authorization_is_current,
        repeated_authorization_is_current,
    )
    real_labels = _labels_holding_real_values(index)
    grants = {
        grant.field_label: grant
        for grant in authorize_t02_writes(index)
        if authorization_is_current(index, grant)
    }
    for grant in authorize_merged_value_writes(index):
        if grant.field_label in grants:
            continue
        if merged_authorization_is_current(index, grant):
            grants[grant.field_label] = grant
    for grant in authorize_nested_leaf_writes(index):
        if grant.field_label in grants:
            continue
        if nested_authorization_is_current(index, grant):
            grants[grant.field_label] = grant
    for grant in authorize_repeated_row_writes(index):
        if grant.field_label in grants:
            continue
        if repeated_authorization_is_current(index, grant):
            grants[grant.field_label] = grant
    for grant in authorize_guidance_narrative_writes(index):
        if grant.field_label in grants:
            continue
        if guidance_authorization_is_current(index, grant):
            grants[grant.field_label] = grant
    for grant in authorize_inline_field_writes(index):
        if grant.field_label in grants:
            continue
        if inline_authorization_is_current(index, grant):
            grants[grant.field_label] = grant
    for grant in authorize_checkbox_writes(index):
        if grant.field_label in grants:
            continue
        if checkbox_authorization_is_current(index, grant):
            grants[grant.field_label] = grant
    exact: list[ExactTextTarget] = []
    for key, value in wanted.items():
        grant = grants.get(key)
        if grant is None or grant.source_sha256 != index.source_sha256:
            report.reasons.append(f"NOT_AUTHORIZED:{key}")
            if key in real_labels:
                report.reasons.append(f"EXISTING_VALUE:{key}")
            continue
        written = value
        preserve = False
        choice = False
        mark = grant.expected_raw_text[:1]
        flipped = checkbox_replacement(grant.expected_raw_text, value) if mark and mark in "□☐" else None
        if mark and mark in "□☐":
            if flipped is None:
                report.reasons.append(f"NOT_AUTHORIZED:{key}")
                continue
            written = flipped
            choice = True
        elif grant.expected_raw_text:
            prefix = grant.expected_raw_text
            written = prefix + value if prefix[-1].isspace() else prefix + " " + value
            preserve = True
        exact.append(ExactTextTarget(
            grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index,
            grant.expected_raw_text, written,
            table_index=None if grant.table_index < 0 else grant.table_index,
            row=None if grant.row < 0 else grant.row,
            col=None if grant.col < 0 else grant.col,
            preserve_prefix=preserve,
            choice_flip=choice,
        ))
    if report.reasons or len(exact) != len(wanted):
        report.reason = report.reasons[0] if report.reasons else "NOT_AUTHORIZED"
        report.cancelled = True
        report.ok = False
        return report
    return commit_exact_text_writes(src, dst, exact, source_sha256=index.source_sha256)
