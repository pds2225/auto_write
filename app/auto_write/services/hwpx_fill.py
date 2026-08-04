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
  replacements(직접 치환)도 채울 수 있는 칸 안에서만 적용한다(라벨/실값 보호).
- AI 호출 없음 — 동일 입력, 동일 결과(결정론).

매칭 지능은 ``cross_form_autofill`` 에서 그대로 가져온다(단일 출처):
``_key``·``_cluster_rep``·``_is_obvious_placeholder``·``_is_noise_label``.
"""

from __future__ import annotations

import copy
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
    """셀 안의 모든 hp:t 요소(순서대로)."""
    return [el for el in tc.iter(_q("t"))]


def _cell_text(tc) -> str:
    """셀의 표시 텍스트(hp:t 결합, 공백 정규화)."""
    parts = [str(el.text or "") for el in _cell_texts(tc)]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _int_attr(el, name: str, default: int) -> int:
    if el is None:
        return default
    try:
        return int(str(el.get(name)))
    except (TypeError, ValueError):
        return default


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

    def black_ref(self, ref: str) -> str:
        """ref 가 유색이면 검정 클론의 id, 아니면 ref 그대로."""
        if self.is_black(ref):
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
        """run 의 charPr 가 유색이면 검정 클론으로 교체. 바꿨으면 True."""
        ref = run.get("charPrIDRef")
        if ref is None or self.is_black(ref):
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
        if black is None or black.is_black(ref):
            return ref
    if first is not None:
        return first if black is None else black.black_ref(first)
    # 폴백 '0' 도 검정 검사를 거친다(적대검증 D8) — 실코퍼스에 id 0 이
    # #0000FF(013 딥테크)·#FFFFFF(012 K-Convergence, 흰 글자=비가시)인 양식 실재.
    return "0" if black is None else black.black_ref("0")


def _set_cell_text(tc, value: str, black: Optional[_BlackCharPr] = None) -> bool:
    """셀의 텍스트를 value 로 설정한다(첫 hp:t 에 기입, 나머지 hp:t 는 비움).

    빈/플레이스홀더 칸에만 호출되므로 잔여 hp:t 를 비워도 실데이터 손실은 없다.
    hp:t/hp:run 이 없으면 단락 서식(charPrIDRef 승계)을 유지하며 최소 생성한다.
    black 이 주어지면 값이 들어간 run 의 유색 charPr 를 검정 클론으로 바꾼다.

    L086: 폼 컨트롤(checkBtn 등)이 든 칸에는 텍스트를 절대 기입하지 않는다 —
    ``_cell_is_fillable`` 우회·resume 경로에서도 이중 표시를 막기 위한 최종 방어핀.
    """
    if _has_form_control(tc):
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


def _splice_run_text(p, fill_start: int, fill_end: int, value: str) -> bool:
    """p 직계 텍스트 흐름의 flat 문자 구간 [fill_start, fill_end) 만 value 로 교체.

    형제 run/hp:t 의 텍스트·charPrIDRef 는 전부 보존한다(대상 hp:t 의 text 만 수정).
    flat 문자열은 _inline_texts(p) 의 text 를 공백 정규화 없이 그대로 이어붙인 것과
    동일해야 한다. 구간이 두 hp:t 에 걸치면(cross-run span) 채우지 않고 False
    (오채움<빈칸 — 보수적 skip).
    """
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
    if start_t is None or end_t is None:
        return False
    if start_t is not end_t:
        return False  # cross-run span: 보수적 skip(오채움<빈칸)
    cur = start_t.text or ""
    start_t.text = cur[:start_off] + value + cur[end_off:]
    return True


def _fill_inline_fields_in_p(p, wants, used_keys: set, filled: dict) -> bool:
    """hp:p 하나의 인라인 필드(`라벨 : ______`)를 채운다 — 1.5(셀)·1.8(본문) 공용 커널.

    '가시 빈칸'(밑줄/점/대시 채움선)만 채운다(_is_visible_blank) — '라벨 :'(콜론+공백만)
    은 옆 값칸·산문과 구별이 안 되므로 제외(_is_fill_blank 금지). flat 은 _inline_texts
    의 직계 hp:t 를 문서순 그대로 결합(공백 정규화 금지, AC9)하고, 역순 스플라이스로
    앞 필드 offset 을 보존한다. 형제 run 의 텍스트·charPrIDRef 보존은 _splice_run_text
    가 보장(대상 hp:t 부분 교체만). used_keys 는 표(1)/인라인(1.5)/체크박스(1.7)/
    본문(1.8)이 공유한다(이중 기입 금지). 반환: 이 단락에서 하나라도 채웠으면 True.
    """
    ts = _inline_texts(p)
    if not ts:
        return False
    flat = "".join(t.text or "" for t in ts)
    if ":" not in flat and "：" not in flat:
        return False
    changed = False
    fields = list(_iter_line_fields(flat))
    # 역순 스플라이스: 뒤 구간부터 교체해야 앞 필드 offset 이 유효.
    for label_raw, value_raw, f_start, f_end in reversed(fields):
        if not _is_visible_blank(value_raw):
            continue
        field_key = _key(label_raw)
        if not field_key:
            continue
        for want_key, lbl, val in wants:
            if want_key in used_keys:
                continue
            if not _label_matches(field_key, want_key):
                continue
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

    line_edits 항목: ``{"anchor": str, "check": [옵션…], "replace": {옛:새},
    "cells": {colAddr: 값}, "nth": 1, "all": False}``. ``nth``(1-based)·``all`` 은
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


def _cell_text_fillable(tc) -> bool:
    """텍스트 기준 채움 가능 판정 — 비었거나 '명백한 예시 플레이스홀더'면 True.

    이미 실제 값이 있으면 False(덮어쓰기 금지). 빈칸 외에는 _is_obvious_placeholder
    (불가능 날짜·전부-0 수량·더미 등록번호)만 채울 대상으로 본다(O마스크 제외).
    치환(replacements) 보호 판정은 이 기준만 쓴다 — 치환은 '기존 텍스트 덮어쓰기'라
    폼 컨트롤 존재와 무관하다(컨트롤 옆 예시토큰 치환은 종전대로 허용, 적대검증 D5).
    """
    txt = _cell_text(tc)
    if not txt:
        return True
    return _is_obvious_placeholder(txt)


def _cell_is_fillable(tc) -> bool:
    """그 칸에 '새 값을 기입'해도 되는가 — 텍스트 기준 + 폼 컨트롤 가드.

    폼 컨트롤(체크박스·입력필드 등)이 든 칸은 텍스트가 비어 보여도 채우지 않는다
    (컨트롤과 글자 이중 표시 방지 — 실측: 수원 멘토위원 신청서 ☐■ 이중).
    """
    if _has_form_control(tc):
        return False
    return _cell_text_fillable(tc)


def _is_label_like(tc) -> bool:
    """그 칸이 값칸이 아니라 '라벨/안내' 칸으로 보이면 True(값 기입 금지 대상)."""
    txt = _cell_text(tc)
    if not txt:
        return False
    norm = _key(txt)
    return _cluster_rep(norm) is not None or _is_noise_label(txt, norm)


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


def _label_matches(cell_key: str, want_key: str) -> bool:
    """정규화 라벨 cell_key 가 want_key 와 같은 항목인가(정확일치 또는 동의어 클러스터)."""
    if not cell_key or not want_key:
        return False
    if cell_key == want_key:
        return True
    rep_c = _cluster_rep(cell_key)
    rep_w = _cluster_rep(want_key)
    return rep_c is not None and rep_c == rep_w


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
    sections_changed: int = 0
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
            "sections_changed": self.sections_changed,
            "notes": list(self.notes),
        }


def _strip_linesegarray(root, *, only_under=None) -> int:
    """채운 섹션의 옛 줄위치 캐시(hp:linesegarray)를 제거한다.

    텍스트를 바꿔도 예시문구 기준의 linesegarray 가 남으면 한글이 새 글씨를 옛
    좌표에 겹쳐 그린다(사용자 실측: STAR·서울 AI 허브 신청서 글씨 겹침 재발). 제거하면
    문서를 열 때 줄위치를 새로 계산한다 — 레이아웃 캐시라 내용 무손실·멱등.
    HWPX 직접 납품(.hwpx→.hwpx) 경로의 글씨 겹침을 엔진 단에서 원천 차단한다.

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


def _fill_section_xml(
    xml_bytes: bytes,
    identity: dict[str, str],
    replacements: dict[str, str],
    black: Optional[_BlackCharPr] = None,
    grid_confirm: Optional[list] = None,
    line_edits: Optional[list[dict]] = None,
    line_report: Optional[dict] = None,
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
    filled: dict[str, str] = {}
    used_keys: set[str] = set()
    replaced = 0
    changed = False
    edited: list = []  # L074: lineseg strip 대상(편집된 tc/p)

    wants = [
        (_key(lbl), lbl, val)
        for lbl, val in identity.items()
        if str(val or "").strip()
    ]

    # 1) 표 라벨→값 칸 채움 (cellAddr 기반 값칸 선택 + 라벨칸 보호)
    for tbl in root.iter(_q("tbl")):
        for tr in _direct(tbl, "tr"):
            cells = _direct(tr, "tc")
            for tc in cells:
                cell_key = _key(_cell_text(tc))
                if not cell_key:
                    continue
                for want_key, lbl, val in wants:
                    if want_key in used_keys:
                        continue
                    if not _label_matches(cell_key, want_key):
                        continue
                    target = _value_cell(tc, cells)
                    if target is None or target is tc:
                        continue
                    if _is_label_like(target):
                        continue  # 값칸 후보가 또 라벨 → 기입 금지
                    if not _cell_is_fillable(target):
                        continue  # 실제 값 있는 칸/폼컨트롤 칸 — 기입 금지
                    if _set_cell_text(target, str(val), black):
                        filled[lbl] = str(val)
                        used_keys.add(want_key)
                        changed = True
                        edited.append(target)
                    break

    # 1.5) 셀 '안' 인라인 빈칸(`라벨 : ______`) 채움 — 표 경로 '뒤'에 실행하며
    #      동일한 used_keys 를 공유한다(AC7: 표가 채운 라벨은 인라인이 재채움 금지).
    #      scope 는 각 hp:p 의 직계 텍스트 흐름만(_inline_texts, AC8 — 중첩 표 제외).
    #      '가시 빈칸'(밑줄/점/대시 채움선)만 채운다 — '라벨 :'(콜론+공백만)은
    #      옆 값칸을 가리키는 경우와 구별이 안 되므로 제외(_is_visible_blank).
    if wants:
        for tc in root.iter(_q("tc")):
            for sub in _direct(tc, "subList"):
                for p in _direct(sub, "p"):
                    if _fill_inline_fields_in_p(p, wants, used_keys, filled):
                        changed = True
                        edited.append(p)

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
                    break

    # 1.8) 표 '밖' 본문 단락 인라인 필드(`라벨 : ______`) — hs:sec 직계 hp:p 만 대상.
    #      표 셀 안 단락(hp:tc 하위)은 1.5 가 담당 — 직계 자식만 보므로 자동 배제
    #      (중복 처리 금지). 채움 규칙은 1.5 와 동일 커널(_fill_inline_fields_in_p)
    #      공유: 가시 빈칸만(산문 `주의 : ...`·콜론+공백만 `비고 : ` 는 절대 안 채움)·
    #      used_keys 공유(표/인라인/체크박스와 이중 기입 금지)·형제 run 보존.
    if wants:
        for p in _direct(root, "p"):
            if _fill_inline_fields_in_p(p, wants, used_keys, filled):
                changed = True
                edited.append(p)

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
                continue
            new = cur
            for old, rep in replacements.items():
                if old and str(rep or "").strip() and old in new:
                    new = new.replace(old, str(rep))
            if new != cur:
                t.text = new
                replaced += 1
                changed = True
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

    if not changed:
        return xml_bytes, filled, replaced, used_keys

    # L074: 편집한 문단/셀의 lineseg 만 제거(안내박스 등 미편집 영역 전역 strip 금지).
    # HWPX→한글 직접 납품 시 겹침 방지는 '텍스트를 바꾼 곳'에만 필요(L002∩L074).
    _strip_linesegarray(root, only_under=edited or None)

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
        force_black: True(기본)면 채운 값이 유색 예시체(charPr)를 승계할 때
                  글꼴·크기는 유지하고 색(글자색·밑줄/취소선/그림자색·형광배경)만
                  검정/제거인 클론으로 바꾼다(제출본 검정 원칙). 적용 범위는
                  표 라벨→값 채움과 '값 전용 run' 치환 — 인라인 빈칸(1.5/1.8)·
                  텍스트 체크(1.7)는 라벨과 run 을 공유해 미적용(유색 잔존 가능,
                  차기 run 분할 과제). 헤더에 색 정보가 없으면 no-op.

    Returns:
        HwpxFillReport — 채운 항목·치환수·잔여(미매칭 라벨)·체크 결과·변경 섹션수.
    """
    src = Path(in_hwpx)
    dst = Path(out_hwpx)
    report = HwpxFillReport(input=str(src), output=str(dst))

    identity = dict(identity or {})
    replacements = dict(replacements or {})
    check_options = [str(o) for o in (check_options or []) if str(o or "").strip()]
    line_edits = [e for e in (line_edits or []) if isinstance(e, dict)]

    # 1) 안전장치
    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    if _same_file(src, dst):
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    if src.suffix.lower() != ".hwpx":
        raise ValueError(f"HWPX 입력만 지원합니다: {src.name}")
    if dst.suffix.lower() != ".hwpx":
        raise ValueError(f"출력은 .hwpx 만 지원합니다: {dst.name}")
    if not zipfile.is_zipfile(src):
        raise ValueError(f"올바른 HWPX(ZIP)가 아닙니다: {src.name}")

    # 2) ZIP 전체를 읽어 들인다(엔트리 순서·압축방식·내용 보존용).
    with zipfile.ZipFile(src) as zin:
        infos = zin.infolist()
        data: dict[str, bytes] = {i.filename: zin.read(i.filename) for i in infos}

    section_names = [i.filename for i in infos if _SECTION_RE.search(i.filename)]
    if not section_names:
        report.notes.append("Contents/section*.xml 을 찾지 못했습니다(빈 양식?).")

    # 2.5) 유색 예시체 차단 준비 — 헤더 charPr 색 지도(파싱 실패/부재 시 no-op).
    header_name = "Contents/header.xml"
    black: Optional[_BlackCharPr] = None
    if force_black and header_name in data:
        try:
            black = _BlackCharPr(etree.fromstring(data[header_name]))
        except etree.XMLSyntaxError:
            black = None

    # 3) 섹션 XML 만 채움/치환
    all_used: set[str] = set()
    changed_names: set[str] = set()
    grid_confirm: list[str] = []
    line_report: dict[str, Any] = {"applied": 0, "notes": []}
    for name in section_names:
        try:
            new_bytes, filled, replaced, used = _fill_section_xml(
                data[name], identity, replacements, black=black,
                grid_confirm=grid_confirm,
                line_edits=line_edits, line_report=line_report,
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

    report.filled_count = len(report.filled)
    report.residual = [
        lbl
        for lbl, val in identity.items()
        if str(val or "").strip() and _key(lbl) not in all_used
    ]
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

    report.ok = True
    if not report.filled and not report.replaced and not report.checked:
        report.notes.append(
            "채운 칸이 없습니다 — 라벨이 양식과 일치하지 않거나 칸에 이미 값이 "
            "있을 수 있습니다(덮어쓰기 금지). identity 라벨/값을 확인하세요.")
    return report
