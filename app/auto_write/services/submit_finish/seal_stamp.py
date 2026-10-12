# -*- coding: utf-8 -*-
"""F1 직인·서명 이미지 자동 삽입(HWPX).

흐름: find_seal_slots 로 서명·날인 자리 후보를 찾고 → stamp_seals 가 회사 마스터에
등록된 직인(SealSpec)의 소유자와 **이름이 일치하고 역할이 본인 칸인 자리에만** 넣는다.
팀원·제3자·기관 서명란, 소유자를 알 수 없는 칸은 건드리지 않고 Finding(REVIEW) 로 남긴다.

재사용(재구현 금지):
- hwpx_pic_insert.build_picture_element / minimal_picture_template — 그림 XML 생성
- hwpx_pic_insert.force_signature_pos (L078: treatAsChar=0·PARA 기준)
- hwpx_pic_insert.insert_signature_into_tc (빈 값 칸 앵커)
- hwpx_pic_insert.picture_display_wh / _px_size / _next_image_id (L142: 가로·세로 둘 다 검증)
- hwpx_fill._inline_texts / _strip_linesegarray / _tc_of

배치 규칙: 글 앞(IN_FRONT_OF_TEXT)·떠 있는 개체(L096)라 줄 높이·쪽수에 영향이 없고,
음수 offset 을 쓰지 않는다(정렬 기준만 지정). 원본 PNG/JPEG 바이트를 그대로 넣어
해상도를 보존하고, 표시 크기는 원본 비율 그대로다.
멱등: 삽입한 그림의 shapeComment 에 표식(AW_SEAL:<키>)을 남겨 재실행 시 중복 삽입하지 않는다.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

from auto_write.services.hwpx_pic_insert import (
    _HWPUNIT_PER_MM,
    _ensure_pos,
    _find_child,
    _next_image_id,
    _px_size,
    build_picture_element,
    force_signature_pos,
    insert_signature_into_tc,
    minimal_picture_template,
    picture_display_wh,
)
from core.docx.services.hwpx_fill import _local, _q, _splice_run_text, _strip_linesegarray, _tc_of

from .hwpx_xml import (
    HPF_NAME,
    assert_not_same,
    cell_addr,
    cell_text,
    find_manifest,
    paragraph_text,
    paragraph_text_full,
    parse_xml,
    read_hwpx,
    section_names,
    serialize_xml,
    write_hwpx,
)
from .status import Finding, Status

# 괄호형 날인 표식: (인) (서명) (직인) (날인) (印) (서명 또는 인) (서명/인) (인 또는 서명) ...
_MARK_WORD = r"(?:서명|날인|직인|인|印|도장|sign|seal)"
_SEAL_MARKER_RE = re.compile(
    r"[\(（]\s*" + _MARK_WORD + r"(?:\s*(?:또는|혹은|or|/|,|，|및)\s*" + _MARK_WORD + r")?\s*[\)）]",
    re.IGNORECASE,
)
# 칸 전체가 '서명' 같은 라벨인 경우(옆 칸 또는 아래 칸이 서명 자리)
_LABEL_CELL_WORDS = {"서명", "서명란", "날인", "직인", "인", "서명또는인", "서명또는날인"}

_ROLE_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("member", ("팀원", "참여인력", "참여연구원", "연구원", "구성원", "직원", "참여자", "공동대표")),
    ("third_party", ("기관장", "확인자", "추천인", "추천자", "보증인", "담당자", "평가위원",
                     "위원", "입회인", "증인", "주관기관", "전담기관", "센터장", "운영기관")),
    ("representative", ("대표자", "대표이사", "대표")),
    ("applicant", ("신청인", "신청자", "제출자", "본인", "서약자", "확인인")),
)
# 마커 문단 '자체' 글자로 역할을 먼저 정한다(표 한 칸에 서명 줄이 여러 개 있는 동의서 대비).
# 팀원N 은 member 를 유지하고, 아래 표기는 대표 줄로 본다.
_OWN_MEMBER_TOKENS = ("팀원", "참여인력", "참여연구원", "구성원", "공동대표")
_OWN_REP_TOKENS = ("신청자(팀대표)", "(팀대표)", "팀대표", "대표자", "신청자")
_ALLOWED_ROLES = {"representative", "applicant", "unknown"}
_BINDABLE_ROLES = {"member", "representative", "applicant", "unknown"}  # 명시 바인딩 허용 역할
_TAG_PREFIX = "AW_SEAL:"
_DEFAULT_WIDTH_MM = {"seal": 15.0, "signature": 18.0}


@dataclass(frozen=True)
class SealSpec:
    """회사 마스터에 등록된 직인·서명 1건.

    owner: 소유자 이름(칸 주변 글자와 공백 무시 정확 포함 비교).
    aliases: 같은 소유자를 가리키는 다른 표기(예: 회사명). 칸 문맥에 owner 또는 alias 가 있어야 한다.
    source: 값 출처(예: 'company_master').
    """

    owner: str
    image: str | Path
    source: str = "company_master"
    kind: str = "seal"  # 'seal'(직인) | 'signature'(서명)
    aliases: tuple[str, ...] = ()
    width_mm: float | None = None
    # 사용자가 이 소유자(팀원)의 도장 사용을 명시 승인했을 때만 True. 기본 False 이면 팀원 칸은 REVIEW.
    # 기관·확인자(third_party) 칸은 이 값과 무관하게 자동 기입하지 않는다.
    user_approved: bool = False
    # 사용자가 "이 도장은 이 줄"이라고 지정한 슬롯 라벨(예: '팀원1'). user_approved=True 일 때만 쓰며,
    # 슬롯 label 과 정규화 후 정확히 같아야 한다(부분일치 금지). 지정된 spec 은 이름 문맥 매칭에서 빠진다.
    slot_label: str | None = None
    # 사용자가 "이 도장은 대표자(신청자) 서명란 전부"라고 승인한 경우의 역할 바인딩(예: ('representative', 'applicant')).
    # user_approved=True 일 때만 쓰며, 같은 역할 서명 줄이 여러 개여도(신청서·서약서·동의서) 모두 넣는다.
    # 칸 주변에 이름이 없는 빈 양식에서 대표 직인을 쓰기 위한 것이다. 팀원·제3자 줄은 목록에 넣지 않는 한 건드리지 않는다.
    bind_roles: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        raw = f"{self.kind}|{_compact(self.owner)}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class SealSlot:
    """서명·날인 자리 후보 1곳."""

    slot_id: str
    section: str
    kind: str  # 'marker'(괄호 표식 문단) | 'label_right'(라벨 옆 빈칸) | 'column'(서명 열 아래 칸)
    cell: tuple[int, int] | None  # (row, col) — 표 밖이면 None
    marker_text: str
    near_text: str
    role: str  # representative | applicant | member | third_party | unknown
    has_picture: bool = False
    existing_tag: str = ""
    label: str = ""  # 마커 문단에서 마커·공백·콜론을 뺀 앞부분(정규화). 예: '신청자(팀대표)성명', '팀원1'
    _anchor: Any = field(default=None, repr=False, compare=False)  # hp:p 또는 hp:tc

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id, "section": self.section, "kind": self.kind,
            "cell": self.cell, "marker_text": self.marker_text, "near_text": self.near_text,
            "role": self.role, "has_picture": self.has_picture, "label": self.label,
        }


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _norm_label(text: str) -> str:
    """라벨 정규화: 공백·콜론 제거, 전각 괄호를 반각으로."""
    out = _compact(text).replace("（", "(").replace("）", ")")
    return re.sub(r"[:：]", "", out)


def _own_role(text: str) -> str | None:
    """마커 문단 자체 글자(마커 제외)로 정한 역할. 근거가 없으면 None."""
    own = _norm_label(_SEAL_MARKER_RE.sub("", text))
    if any(token in own for token in _OWN_MEMBER_TOKENS):
        return "member"
    if any(token in own for token in _OWN_REP_TOKENS):
        return "representative"
    return None


def _role_of(text: str) -> str:
    compact = _compact(text)
    for role, tokens in _ROLE_TOKENS:
        if any(token in compact for token in tokens):
            return role
    return "unknown"


def _pics_under(el) -> list:
    return [node for node in el.iter() if _local(getattr(node, "tag", "")) == "pic"]


def _seal_tag(pic) -> str:
    sc = _find_child(pic, "shapeComment")
    text = (sc.text or "") if sc is not None else ""
    return text if text.startswith(_TAG_PREFIX) else ""


def _row_cells(tc) -> list:
    tr = tc.getparent()
    return [c for c in tr if _local(getattr(c, "tag", "")) == "tc"] if tr is not None else []


def _row_text(tc) -> str:
    return " ".join(cell_text(c) for c in _row_cells(tc))


def _table_of(tc):
    cur = tc.getparent()
    while cur is not None and _local(getattr(cur, "tag", "")) != "tbl":
        cur = cur.getparent()
    return cur


def _table_caption(tbl) -> str:
    """표 바로 앞 문단(표를 품은 문단의 앞 형제) 글자 — 표 제목 문맥."""
    holder = tbl.getparent()
    while holder is not None and _local(getattr(holder, "tag", "")) != "p":
        holder = holder.getparent()
    if holder is None:
        return ""
    prev = holder.getprevious()
    return paragraph_text_full(prev) if prev is not None and _local(prev.tag) == "p" else ""


def _prev_texts(p, limit: int = 2) -> list[str]:
    out: list[str] = []
    cur = p.getprevious()
    while cur is not None and len(out) < limit:
        if _local(getattr(cur, "tag", "")) == "p":
            text = paragraph_text_full(cur).strip()
            if text:
                out.append(text)
        cur = cur.getprevious()
    return out


def _slot_state(anchor) -> tuple[bool, str]:
    pics = _pics_under(anchor)
    tags = [t for t in (_seal_tag(p) for p in pics) if t]
    return bool(pics), (tags[0] if tags else "")


def _marker_state(p, tc) -> tuple[bool, str]:
    """표 칸 안 마커 문단의 상태. 같은 칸의 다른 서명 줄에 붙은 우리 직인(AW_SEAL)은 남의 것이라
    무시하고, 표식 없는 기존 그림이 칸에 있으면 그대로 '그림 있음'으로 본다(덮어쓰기 방지)."""
    has_pic, tag = _slot_state(p)
    if tc is not None and any(not _seal_tag(pic) for pic in _pics_under(tc)):
        has_pic = True
    return has_pic, tag


def _scan_section(sec_name: str, root) -> list[SealSlot]:
    slots: list[SealSlot] = []
    paragraphs = list(root.iter(_q("p")))
    seen_cells: set[int] = set()
    # (1) 괄호 표식 문단
    for order, p in enumerate(paragraphs):
        text = paragraph_text_full(p)
        compact = _compact(text)
        if not compact or len(compact) > 60 or compact.startswith(("※", "*", "-")):
            continue
        match = _SEAL_MARKER_RE.search(text)
        if match is None:
            continue
        tc = _tc_of(p)
        if tc is not None:
            near = _row_text(tc)
            tbl = _table_of(tc)
            context = near if _role_of(near) != "unknown" else (_table_caption(tbl) if tbl is not None else "")
            addr = cell_addr(tc)
            seen_cells.add(id(tc))
        else:
            # 문단 안에 이름이 없을 때('(서명 또는 인)' 단독 줄)만 바로 앞 1줄을 문맥으로 쓴다.
            # 앞 줄이 다른 서명 자리면 남의 이름을 끌어오므로 쓰지 않는다.
            near = text
            rest = _SEAL_MARKER_RE.sub("", compact)
            for _role, tokens in _ROLE_TOKENS:
                for token in tokens:
                    rest = rest.replace(token, "")
            if not re.sub(r"[\W_]", "", rest):
                prev = _prev_texts(p, limit=1)
                if prev and not _SEAL_MARKER_RE.search(prev[0]):
                    near = prev[0] + " " + text
            context = near
            addr = None
        has_pic, tag = _marker_state(p, tc)
        slots.append(SealSlot(
            slot_id=f"{sec_name}#p{order}", section=sec_name, kind="marker", cell=addr,
            marker_text=match.group(0), near_text=near.strip(),
            role=_own_role(text) or _role_of(context),
            has_picture=has_pic, existing_tag=tag, label=_norm_label(text[:match.start()]), _anchor=p,
        ))
    # (2) '서명' 라벨 칸 → 오른쪽 빈칸(가로형) 또는 같은 열 아래 칸들(세로형)
    for tbl_order, tbl in enumerate(root.iter(_q("tbl"))):
        rows = [r for r in tbl if _local(getattr(r, "tag", "")) == "tr"]
        for r_idx, tr in enumerate(rows):
            cells = [c for c in tr if _local(getattr(c, "tag", "")) == "tc"]
            for c_idx, tc in enumerate(cells):
                if _compact(cell_text(tc)) not in _LABEL_CELL_WORDS:
                    continue
                targets: list[tuple[str, Any]] = []
                right = cells[c_idx + 1] if c_idx + 1 < len(cells) else None
                if right is not None and not _compact(cell_text(right)):
                    targets.append(("label_right", right))
                else:
                    col = cell_addr(tc)[1]
                    for below in rows[r_idx + 1:]:
                        for cand in below:
                            if _local(getattr(cand, "tag", "")) == "tc" and cell_addr(cand)[1] == col:
                                if not _compact(cell_text(cand)) or _SEAL_MARKER_RE.fullmatch(cell_text(cand).strip()):
                                    targets.append(("column", cand))
                caption = _table_caption(tbl)
                header = _row_text(tc)
                for kind, cell in targets:
                    if id(cell) in seen_cells:
                        continue
                    seen_cells.add(id(cell))
                    near = _row_text(cell)
                    role = _role_of(near)
                    if role == "unknown":
                        role = _role_of(header + " " + caption)
                    if kind == "column" and role in {"unknown", "applicant"} and len(targets) >= 2:
                        role = "member"  # 여러 사람이 줄지어 서명하는 표 = 구성원 명단으로 본다
                    has_pic, tag = _slot_state(cell)
                    row, col = cell_addr(cell)
                    slots.append(SealSlot(
                        slot_id=f"{sec_name}#t{tbl_order}r{row}c{col}", section=sec_name, kind=kind,
                        cell=(row, col), marker_text=cell_text(tc).strip(), near_text=near.strip(),
                        role=role, has_picture=has_pic, existing_tag=tag, _anchor=cell,
                    ))
    return slots


def find_seal_slots(hwpx) -> list[SealSlot]:
    """서명·날인 자리 후보 목록(문서 순). 원본은 읽기만 한다."""
    _infos, data = read_hwpx(hwpx)
    slots: list[SealSlot] = []
    for name in section_names(data):
        slots.extend(_scan_section(name, parse_xml(data[name])))
    return slots


def _owner_hits(slot: SealSlot, seals: list[SealSpec]) -> list[SealSpec]:
    near = _compact(slot.near_text)
    hits = []
    for spec in seals:
        names = [n for n in (spec.owner, *spec.aliases) if _compact(n)]
        if any(_compact(n) in near for n in names):
            hits.append(spec)
    return hits


def _unique_ids(root) -> int:
    used = [int(el.get(k)) for el in root.iter() for k in ("id", "instid")
            if (el.get(k) or "").isdigit()]
    nxt = (max(used) + 1) if used else 1
    return nxt if nxt < 2_000_000_000 else 1_000_000_000 + (nxt % 900_000_000)


def _build_seal_pic(image_id: str, px: tuple[int, int], width_mm: float, tag: str,
                    next_id: int, align: str):
    pic = build_picture_element(minimal_picture_template(), image_id=image_id, px=px,
                                width_mm=width_mm, comment=tag)
    pic.set("id", str(next_id))
    pic.set("instid", str(next_id + 1))
    pic.set("textWrap", "IN_FRONT_OF_TEXT")  # 글 앞 — 줄 높이·쪽수 영향 없음(L096)
    force_signature_pos(pic)                 # treatAsChar=0, vertRelTo/horzRelTo=PARA (L078)
    pos = _ensure_pos(pic)
    pos.set("flowWithText", "1")
    pos.set("allowOverlap", "1")
    pos.set("vertAlign", "TOP")
    pos.set("horzAlign", align)
    pos.set("vertOffset", "0")               # 음수 offset 의존 금지
    pos.set("horzOffset", "0")
    sc = _find_child(pic, "shapeComment")
    if sc is not None:
        sc.text = tag
    return pic


def _append_to_paragraph(p, pic) -> None:
    runs = [r for r in p if _local(getattr(r, "tag", "")) == "run"]
    char_ref = runs[-1].get("charPrIDRef", "0") if runs else "0"
    run = etree.SubElement(p, _q("run"))
    run.set("charPrIDRef", char_ref)
    run.append(pic)
    _strip_linesegarray(p, only_under=[p])


_CRAMPED_MAX_HEIGHT_MM = 7.0  # 한글 본문 한 줄 높이 안쪽


def _next_paragraph_is_marker(p) -> bool:
    """바로 다음 문단이 또 다른 서명·날인 표식 줄인가(서명 줄이 쌓인 구간)."""
    nxt = p.getnext()
    while nxt is not None and _local(getattr(nxt, "tag", "")) != "p":
        nxt = nxt.getnext()
    return nxt is not None and _SEAL_MARKER_RE.search(paragraph_text_full(nxt)) is not None


def _label_bound(slot: SealSlot, spec: SealSpec) -> bool:
    """명시 바인딩 판정: 정규화 라벨 정확 일치(부분일치 금지).
    이름을 이미 써 넣은 줄('팀원1 홍길동')은 라벨+소유자 이름과 정확히 같을 때만 같은 줄로 본다(재실행 멱등)."""
    want = _norm_label(spec.slot_label or "")
    if not (spec.user_approved and want and slot.label):
        return False
    return slot.label in (want, want + _norm_label(spec.owner))


def _text_width(text: str) -> int:
    """공백 칸 수로 본 글자 폭 — 한글·한자 등 전각은 2칸, 그 외 1칸."""
    return sum(2 if ord(ch) >= 0x2E80 else 1 for ch in text)


def _write_owner_name_before_tab(p, name: str) -> tuple[bool, str]:
    """표식이 `<t>라벨<tab/>(서명/인)</t>` 처럼 탭 뒤 tail 글자에 있는 줄 — 탭 앞 라벨 뒤에 이름을 붙인다.

    실양식(마포)의 서명 줄 모양이다. 라벨이 비었거나 라벨 뒤에 이미 다른 글자가 있으면 건드리지 않는다."""
    from core.docx.services.hwpx_fill import _inline_texts, _invalidate_lineseg

    for t in _inline_texts(p):
        tails = "".join((child.tail or "") for child in t)
        if _SEAL_MARKER_RE.search(tails) is None:
            continue
        head = t.text or ""
        if _compact(name) in _compact(head):
            return False, "already"
        if not head.strip():
            return False, "no_marker"
        colon = max(head.rfind(":"), head.rfind("："))
        if colon >= 0:
            if head[colon + 1:].strip():
                return False, "other_name"
        elif re.search(r"\s{2,}\S", head.strip()):
            return False, "other_name"
        t.text = head.rstrip() + "  " + name + "  "
        _invalidate_lineseg(p)
        return True, "written"
    return False, "no_marker"


def _write_owner_name(p, owner: str) -> tuple[bool, str]:
    """마커 앞 빈 공백 구간에 소유자 이름을 넣는다. 공백은 이름 폭만큼 줄여 한 줄을 유지한다.

    반환: (썼는지, 사유) — 사유: written | already | other_name | no_room | no_marker | cross_run
    """
    name = (owner or "").strip()
    flat = paragraph_text(p)
    match = _SEAL_MARKER_RE.search(flat)
    if match is None and name:
        return _write_owner_name_before_tab(p, name)
    if match is None or not name:
        return False, "no_marker"
    prefix = flat[:match.start()]
    if _compact(name) in _compact(prefix):
        return False, "already"
    colon = max(prefix.rfind(":"), prefix.rfind("："))
    if colon >= 0:
        if prefix[colon + 1:].strip():
            return False, "other_name"
        start, lead = colon + 1, 1
    else:
        head = prefix.strip()
        if re.search(r"\s{2,}\S", head):  # '팀원1  홍길동' 처럼 라벨 뒤에 이미 다른 글자가 있음
            return False, "other_name"
        start, lead = len(prefix.rstrip()), 2
    gap = len(prefix) - start
    width = _text_width(name)
    if gap < width + lead + 1:
        return False, "no_room"
    new = " " * lead + name + " " * (gap - width - lead)
    if not _splice_run_text(p, start, match.start(), new):
        return False, "cross_run"
    _strip_linesegarray(p, only_under=[p])
    return True, "written"


def _mm(hwpunit: int) -> float:
    return round(hwpunit / _HWPUNIT_PER_MM, 1)


def stamp_seals(in_hwpx, out_hwpx, seals: list[SealSpec], *, slots: list[str] | None = None,
                write_names: bool = False) -> dict[str, Any]:
    """소유자가 일치하는 자리에만 직인을 넣어 out_hwpx 로 저장한다(원본 미수정).

    slots: 특정 slot_id 만 대상으로 제한(없으면 전체 후보).
    write_names: True 면 slot_label 바인딩으로 넣은 마커 줄에 이름이 비어 있을 때 소유자 이름도 기입.
    반환: {"output": 경로, "inserted": 삽입 수, "slots": [...], "findings": [Finding]}
    """
    assert_not_same(in_hwpx, out_hwpx)
    for spec in seals:
        if not Path(spec.image).is_file():
            raise FileNotFoundError(f"직인 이미지 없음: {Path(spec.image).name}")
    infos, data = read_hwpx(in_hwpx)
    hpf_root = parse_xml(data[HPF_NAME])
    manifest = find_manifest(hpf_root)
    if manifest is None:
        raise ValueError("content.hpf 에 manifest 가 없습니다.")
    opf_ns = etree.QName(manifest).namespace
    next_image = _next_image_id(data[HPF_NAME].decode("utf-8"))
    registered: dict[str, str] = {}  # spec.key → image id (한 직인은 BinData 1개만)
    added: dict[str, bytes] = {}
    findings: list[Finding] = []
    all_slots: list[SealSlot] = []
    inserted = 0

    # 명시 바인딩(user_approved + slot_label) spec 은 이름 문맥 매칭에서 뺀다.
    bound_specs = [s for s in seals if s.user_approved and _norm_label(s.slot_label or "")]
    role_specs = [s for s in seals if s.user_approved and s.bind_roles and s not in bound_specs]
    name_specs = [s for s in seals if s not in bound_specs and s not in role_specs]
    roots = {name: parse_xml(data[name]) for name in section_names(data)}
    scanned = {name: _scan_section(name, root) for name, root in roots.items()}
    # 한 spec 이 여러 줄에 걸리면(같은 라벨 중복) 어느 줄인지 모호 → 그 spec 은 REVIEW
    spec_hits: dict[int, int] = {}
    for section_slots in scanned.values():
        for slot in section_slots:
            for spec in bound_specs:
                if _label_bound(slot, spec):
                    spec_hits[id(spec)] = spec_hits.get(id(spec), 0) + 1

    for name, root in roots.items():
        section_slots = scanned[name]
        all_slots.extend(section_slots)
        changed = False
        next_id = _unique_ids(root)
        for slot in section_slots:
            if slots is not None and slot.slot_id not in slots:
                continue
            meta: dict[str, Any] = {"slot_id": slot.slot_id, "role": slot.role, "cell": slot.cell,
                                    "kind": slot.kind, "label": slot.label, "inserted": False}
            evidence = f"{slot.slot_id} role={slot.role}"
            bound = [s for s in bound_specs if _label_bound(slot, s)]
            role_hits = [] if bound else [s for s in role_specs if slot.role in s.bind_roles]
            if role_hits:
                meta["binding"] = "role"
                if len(role_hits) > 1:
                    meta["candidates"] = [s.owner for s in role_hits]
                    findings.append(Finding("F1_SEAL_BINDING_CONFLICT", Status.REVIEW,
                                            "같은 역할 서명 줄에 도장 지정이 겹침 — 자동 기입 안 함, 사용자 확인 필요",
                                            source="engine", evidence=evidence, meta=meta))
                    continue
                spec = role_hits[0]
            elif bound:
                meta["binding"] = "slot_label"
                if len(bound) > 1 or spec_hits.get(id(bound[0]), 0) > 1:
                    meta["candidates"] = [s.owner for s in bound]
                    findings.append(Finding("F1_SEAL_BINDING_CONFLICT", Status.REVIEW,
                                            "같은 서명 줄에 도장 지정이 겹침(또는 같은 라벨 줄이 여러 개) "
                                            "— 자동 기입 안 함, 사용자 확인 필요",
                                            source="engine", evidence=evidence, meta=meta))
                    continue
                if slot.role not in _BINDABLE_ROLES:
                    findings.append(Finding("F1_SEAL_OTHER_PARTY", Status.REVIEW,
                                            "제3자·기관 서명란 — 지정이 있어도 자동 기입 안 함, 사용자 확인 필요",
                                            source="engine", evidence=evidence, meta=meta))
                    continue
                spec = bound[0]
            else:
                hits = _owner_hits(slot, name_specs)
                approved_member = (slot.role == "member" and len(hits) == 1 and hits[0].user_approved)
                if slot.role not in _ALLOWED_ROLES and not approved_member:
                    findings.append(Finding("F1_SEAL_OTHER_PARTY", Status.REVIEW,
                                            "팀원·제3자·기관 서명란 — 자동 기입 안 함, 사용자 확인 필요",
                                            source="engine", evidence=evidence, meta=meta))
                    continue
                if len(hits) != 1:
                    reason = "소유자 불명" if not hits else "소유자 후보 여러 명"
                    findings.append(Finding("F1_SEAL_OWNER_UNKNOWN", Status.REVIEW,
                                            f"{reason} — 자동 기입 안 함, 사용자 확인 필요",
                                            source="engine", evidence=evidence, meta=meta))
                    continue
                spec = hits[0]
            tag = f"{_TAG_PREFIX}{spec.key}"
            meta.update({"target": spec.owner, "source": spec.source, "seal_kind": spec.kind})
            name_ok = bool(write_names and meta.get("binding") and _local(slot._anchor.tag) == "p")
            if slot.existing_tag == tag:
                meta["already"] = True
                if name_ok:
                    written, why = _write_owner_name(slot._anchor, spec.owner)
                    meta.update({"name_written": written, "name_reason": why})
                    changed = changed or written
                findings.append(Finding("F1_SEAL_PRESENT", Status.PASS,
                                        "이미 같은 직인이 있음(중복 삽입 안 함) — 자동 검사 PASS",
                                        source="engine", evidence=evidence + f" source={spec.source}", meta=meta))
                continue
            if slot.has_picture:
                findings.append(Finding("F1_SEAL_SLOT_HAS_PICTURE", Status.REVIEW,
                                        "자리에 기존 그림이 있음 — 덮어쓰지 않음, 사용자 확인 필요",
                                        source="engine", evidence=evidence, meta=meta))
                continue

            image = Path(spec.image)
            if spec.key not in registered:
                image_id = f"image{next_image}"
                next_image += 1
                suffix = image.suffix.lower()
                href = f"BinData/{image_id}{suffix}"
                media = "image/png" if suffix == ".png" else "image/jpeg"
                etree.SubElement(manifest, f"{{{opf_ns}}}item" if opf_ns else "item",
                                 id=image_id, href=href,
                                 **{"media-type": media, "isEmbeded": "1"})
                added[href] = image.read_bytes()  # 원본 바이트 그대로 = 해상도 보존
                registered[spec.key] = image_id
            px = _px_size(image)
            width_mm = float(spec.width_mm or _DEFAULT_WIDTH_MM.get(spec.kind, 15.0))
            # 서명 줄이 연달아 쌓인 칸(대표→팀원1…)은 줄 간격(≈7mm)보다 큰 그림이 다음 줄 라벨을 덮는다(실양식 렌더에서 확인).
            if _local(slot._anchor.tag) == "p" and _next_paragraph_is_marker(slot._anchor):
                capped = _CRAMPED_MAX_HEIGHT_MM * px[0] / max(px[1], 1)
                if capped < width_mm:
                    width_mm = round(capped, 2)
                    meta["cramped_cap"] = True
            align = "RIGHT" if (slot.kind == "marker" and slot.cell is None) else "CENTER"
            pic = _build_seal_pic(registered[spec.key], px, width_mm, tag, next_id, align)
            next_id += 2
            anchor = slot._anchor
            if _local(anchor.tag) == "tc":
                insert_signature_into_tc(anchor, pic)
                pos = _ensure_pos(pic)  # insert_signature_into_tc 가 다시 PARA 로 강제 — 정렬 유지 확인
                pos.set("horzAlign", align)
            else:
                if name_ok:  # 이름은 그림 run 을 붙이기 전에 기존 글자 run 안에서만 고친다
                    written, why = _write_owner_name(anchor, spec.owner)
                    meta.update({"name_written": written, "name_reason": why})
                _append_to_paragraph(anchor, pic)
            w, h = picture_display_wh(pic)  # L142: 가로·세로 모두 >0 검증
            meta.update({"inserted": True, "width_mm": _mm(w), "height_mm": _mm(h),
                         "size_mm": f"{_mm(w)}x{_mm(h)}", "image_px": f"{px[0]}x{px[1]}"})
            inserted += 1
            changed = True
            findings.append(Finding("F1_SEAL_INSERTED", Status.PASS,
                                    f"직인 삽입 {_mm(w)}x{_mm(h)}mm — 자동 검사 PASS, 렌더 위치 사용자 확인 필요",
                                    source="engine", evidence=evidence + f" source={spec.source}", meta=meta))
        if changed:
            data[name] = serialize_xml(root, data[name])

    if added:
        data[HPF_NAME] = serialize_xml(hpf_root, data[HPF_NAME])
    out = write_hwpx(infos, data, out_hwpx, added)
    return {
        "output": str(out),
        "inserted": inserted,
        "slots": [s.to_dict() for s in all_slots],
        "findings": findings,
    }
