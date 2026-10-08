# -*- coding: utf-8 -*-
"""F2 체크박스 자동 선택(HWPX) — 근거가 있는 그룹만 □ → ■.

그룹 = 같은 셀(또는 같은 행에서 라벨 칸 뒤에 이어지는 옵션 칸들), 표 밖이면 같은 문단.
□ 와 옵션 글자가 여러 text run 에 나뉘어 있어도 문단의 직계 텍스트 흐름(hwpx_fill._inline_texts)
기준 flat 문자열로 묶어 본다. 실제 치환은 □ 1글자만 바꾸므로(hwpx_fill._splice_run_text)
형제 run·글자 서식은 그대로다.

입력 계약:
    decisions = {그룹 라벨 또는 group_id: {"value": str | list[str],
                                         "source": "company_master|plan|user",
                                         "single": bool(기본 True)}}
    consents  = {동의 그룹 라벨 또는 group_id: True}   # 항목별 사용자 명시 승인만 인정

규칙: 옵션 매칭은 정규화 후 **정확일치만**(L025, 부분문자열 금지). 단일선택 그룹에 2개 이상이면
FAIL(아무것도 안 바꿈). 근거 없는 그룹·동의 미승인 그룹은 건드리지 않고 REVIEW.
이미 ■ 인 항목은 유지. 원본 파일은 읽기만 한다.

재사용: hwpx_fill._iter_empty_boxes / _splice_run_text / _inline_texts / _tc_of,
cross_form_autofill._option_text / _normalize_choice / _ANY_BOX_RE,
label_utils.key, hwpx_protected_regions._CONSENT_TOKENS / _is_square_heading.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.docx.services.cross_form_autofill import _normalize_choice, _option_text
from core.docx.services.hwpx_fill import _iter_empty_boxes, _local, _q, _splice_run_text, _tc_of
from core.docx.services.hwpx_protected_regions import _CONSENT_TOKENS, _is_square_heading
from core.docx.services.label_utils import key as label_key

from .hwpx_xml import (
    cell_text,
    paragraph_text,
    parse_xml,
    read_hwpx,
    section_names,
    serialize_xml,
    assert_not_same,
    write_hwpx,
)
from .status import Finding, Status

_CHECKED_RE = re.compile(r"[■☑☒✓✔◼◾🗹]|\[[√vV✓✔xX■]\]")
_MAX_OPTION_LEN = 30   # 이보다 긴 '옵션'은 글머리표 문장으로 본다
_ALLOWED_SOURCES = {"company_master", "plan", "user"}


@dataclass
class _Option:
    label: str
    p: Any
    start: int
    end: int
    mark: str | None   # 빈 박스면 치환 기호, 이미 체크면 None
    checked: bool


@dataclass
class CheckboxGroup:
    group_id: str
    label: str
    options: list[_Option] = field(default_factory=list)

    @property
    def consent(self) -> bool:
        text = re.sub(r"\s+", "", self.label + "".join(o.label for o in self.options))
        return any(token in text for token in _CONSENT_TOKENS)

    def to_dict(self) -> dict[str, Any]:
        return {"group_id": self.group_id, "label": self.label, "consent": self.consent,
                "options": [{"label": o.label, "checked": o.checked} for o in self.options]}


def _norm(text: str) -> str:
    return _normalize_choice(label_key(re.sub(r"[:：]\s*$", "", (text or "").strip())))


def _parse_options(p) -> tuple[str, list[_Option]]:
    """문단 → (인라인 라벨, 옵션들). 체크된 박스도 옵션으로 포함(유지·중복 판정용)."""
    flat = paragraph_text(p)
    boxes = [(s, e, m, False) for s, e, m in _iter_empty_boxes(flat)]
    boxes += [(m.start(), m.end(), None, True) for m in _CHECKED_RE.finditer(flat)]
    boxes.sort(key=lambda b: b[0])
    if not boxes:
        return "", []
    if len(boxes) == 1 and _is_square_heading(flat):
        return "", []  # '□ 사업 개요' 같은 제목 글머리표
    options: list[_Option] = []
    for i, (start, end, mark, checked) in enumerate(boxes):
        stop = boxes[i + 1][0] if i + 1 < len(boxes) else len(flat)
        label = _option_text(flat[end:stop]).strip(" ,/·ㆍ")
        if not label or len(label) > _MAX_OPTION_LEN:
            return "", []
        options.append(_Option(label, p, start, end, mark, checked))
    inline = re.sub(r"[:：]\s*$", "", flat[: boxes[0][0]].strip()).strip()
    return inline, options


def _scan_groups(sec_name: str, root) -> list[CheckboxGroup]:
    paragraphs = list(root.iter(_q("p")))
    order = {id(p): i for i, p in enumerate(paragraphs)}
    parsed: dict[int, tuple[str, list[_Option]]] = {}
    for p in paragraphs:
        inline, options = _parse_options(p)
        if options:
            parsed[id(p)] = (inline, options)

    groups: list[CheckboxGroup] = []
    done: set[int] = set()

    def new_group(first_p, label: str) -> CheckboxGroup:
        group = CheckboxGroup(f"{sec_name}#p{order[id(first_p)]}", label)
        groups.append(group)
        return group

    # 표 안: 행 단위로 왼쪽→오른쪽. 옵션 없는 칸 글자가 다음 옵션들의 그룹 라벨이 된다.
    for tr in root.iter(_q("tr")):
        current: CheckboxGroup | None = None
        label = ""
        for tc in (c for c in tr if _local(getattr(c, "tag", "")) == "tc"):
            own = [p for p in tc.iter(_q("p")) if _tc_of(p) is tc]
            option_ps = [p for p in own if id(p) in parsed]
            if not option_ps:
                text = cell_text(tc).strip()
                if text:
                    label, current = text, None
                continue
            for p in option_ps:
                inline, options = parsed[id(p)]
                done.add(id(p))
                if inline:
                    current = new_group(p, inline)
                elif current is None:
                    current = new_group(p, label)
                current.options.extend(options)
    # 표 밖 문단: 문단 = 그룹. 인라인 라벨이 없으면 바로 앞 문단 글자를 라벨로.
    for p in paragraphs:
        if id(p) in done or id(p) not in parsed:
            continue
        inline, options = parsed[id(p)]
        label = inline
        if not label:
            prev = p.getprevious()
            while prev is not None and _local(getattr(prev, "tag", "")) != "p":
                prev = prev.getprevious()
            if prev is not None and id(prev) not in parsed:
                label = paragraph_text(prev).strip()
        group = new_group(p, label)
        group.options.extend(options)
    groups.sort(key=lambda g: int(g.group_id.rsplit("#p", 1)[1]))
    return groups


def find_checkbox_groups(hwpx) -> list[CheckboxGroup]:
    """문서의 체크박스 그룹 목록(읽기 전용)."""
    _infos, data = read_hwpx(hwpx)
    out: list[CheckboxGroup] = []
    for name in section_names(data):
        out.extend(_scan_groups(name, parse_xml(data[name])))
    return out


def _lookup(table: dict | None, group: CheckboxGroup, label_counts: dict[str, int]):
    """group_id 우선, 다음 라벨(정규화 정확일치·문서 내 유일할 때만)."""
    if not table:
        return None, None
    if group.group_id in table:
        return group.group_id, table[group.group_id]
    norm = _norm(group.label)
    if not norm:
        return None, None
    for k, v in table.items():
        if _norm(k) == norm:
            if label_counts.get(norm, 0) > 1:
                return k, "AMBIGUOUS"
            return k, v
    return None, None


def select_checkboxes(in_hwpx, out_hwpx, decisions: dict, *, consents: dict | None = None) -> dict[str, Any]:
    """근거(decisions)·동의 승인(consents)이 있는 그룹만 ■ 로 바꿔 out_hwpx 에 저장."""
    assert_not_same(in_hwpx, out_hwpx)
    infos, data = read_hwpx(in_hwpx)
    findings: list[Finding] = []
    used_keys: set[str] = set()
    all_groups: list[CheckboxGroup] = []
    selected = 0
    parsed_roots = {name: parse_xml(data[name]) for name in section_names(data)}
    groups_by_sec = {name: _scan_groups(name, root) for name, root in parsed_roots.items()}
    label_counts: dict[str, int] = {}
    for groups in groups_by_sec.values():
        for g in groups:
            n = _norm(g.label)
            if n:
                label_counts[n] = label_counts.get(n, 0) + 1

    for name, root in parsed_roots.items():
        changed = False
        for btn in (el for el in root.iter() if _local(getattr(el, "tag", "")) == "checkBtn"):
            findings.append(Finding("F2_FORM_CONTROL", Status.REVIEW,
                                    "폼 컨트롤 체크박스 — 자동 선택 미지원, 사용자 확인 필요",
                                    source="engine", evidence=f"{name} checkBtn",
                                    meta={"caption": btn.get("caption", "")}))
        for group in groups_by_sec[name]:
            all_groups.append(group)
            meta: dict[str, Any] = {"group_id": group.group_id, "label": group.label,
                                    "options": [o.label for o in group.options]}
            ev = group.group_id
            dkey, decision = _lookup(decisions, group, label_counts)
            if dkey is not None:
                used_keys.add(dkey)
            if decision == "AMBIGUOUS":
                findings.append(Finding("F2_GROUP_AMBIGUOUS", Status.REVIEW,
                                        "같은 라벨 그룹이 여러 개 — group_id 로 지정 필요, 사용자 확인 필요",
                                        source="engine", evidence=ev, meta=meta))
                continue
            if group.consent:
                ckey, approved = _lookup(consents, group, label_counts)
                if ckey is not None:
                    used_keys.add(f"consent:{ckey}")
                if approved is not True:
                    findings.append(Finding("F2_CONSENT_UNAPPROVED", Status.REVIEW,
                                            "동의 항목 — 사용자 명시 승인 없음, 자동 체크 안 함",
                                            source="engine", evidence=ev, meta=meta))
                    continue
                if decision is None:
                    agree = [o for o in group.options if _norm(o.label) in {"동의", "동의함"}]
                    if len(agree) == 1:
                        decision = {"value": agree[0].label, "source": "user", "single": True}
            if decision is None:
                findings.append(Finding("F2_NO_BASIS", Status.REVIEW,
                                        "선택 근거 없음 — 건드리지 않음, 사용자 확인 필요",
                                        source="engine", evidence=ev, meta=meta))
                continue
            values = decision.get("value")
            values = [values] if isinstance(values, str) else [str(v) for v in (values or [])]
            source = str(decision.get("source") or "")
            single = bool(decision.get("single", True))
            meta.update({"value": values, "source": source, "single": single})
            if source not in _ALLOWED_SOURCES or not values:
                findings.append(Finding("F2_NO_BASIS", Status.REVIEW,
                                        "근거 출처·값 누락 — 건드리지 않음, 사용자 확인 필요",
                                        source="engine", evidence=ev, meta=meta))
                continue
            wanted: list[_Option] = []
            unmatched: list[str] = []
            for value in values:
                hits = [o for o in group.options if _norm(o.label) == _norm(value)]
                if len(hits) == 1:
                    if hits[0] not in wanted:
                        wanted.append(hits[0])
                else:
                    unmatched.append(value)
            if unmatched:
                findings.append(Finding("F2_OPTION_UNMATCHED", Status.REVIEW,
                                        "값과 정확히 일치하는 옵션 없음 — 건드리지 않음, 사용자 확인 필요",
                                        source="engine", evidence=ev, meta={**meta, "unmatched": unmatched}))
                continue
            final = {id(o) for o in group.options if o.checked} | {id(o) for o in wanted}
            if single and len(final) > 1:
                findings.append(Finding("F2_SINGLE_MULTI", Status.FAIL,
                                        "단일선택 그룹에 2개 이상 선택 — 구조 검사 FAIL, 변경 안 함",
                                        source="engine", evidence=ev, meta=meta))
                continue
            failed = False
            done_labels: list[str] = []
            # 같은 문단에서 뒤쪽부터 바꾼다 — '[ ]'→'[√]' 처럼 길이가 바뀌어도 앞 offset 이 안 밀린다.
            for opt in sorted(wanted, key=lambda o: o.start, reverse=True):
                if opt.checked:
                    done_labels.append(opt.label)
                    continue
                if _splice_run_text(opt.p, opt.start, opt.end, opt.mark):
                    opt.checked = True
                    done_labels.append(opt.label)
                    selected += 1
                    changed = True
                else:
                    failed = True
            meta["selected"] = sorted(done_labels)
            if failed:
                findings.append(Finding("F2_SPLICE_SKIPPED", Status.REVIEW,
                                        "체크 기호가 여러 run 에 걸쳐 자동 변경 못 함 — 사용자 확인 필요",
                                        source="engine", evidence=ev, meta=meta))
            else:
                findings.append(Finding("F2_SELECTED", Status.PASS,
                                        f"근거({source}) 기반 선택 — 자동 검사 PASS",
                                        source="engine", evidence=f"{ev} source={source}", meta=meta))
        if changed:
            data[name] = serialize_xml(root, data[name])

    for k in decisions or {}:
        if k not in used_keys:
            findings.append(Finding("F2_DECISION_UNUSED", Status.REVIEW,
                                    "결정 항목과 맞는 체크박스 그룹 없음 — 사용자 확인 필요",
                                    source="engine", evidence=str(k)[:40], meta={"key": k}))
    out = write_hwpx(infos, data, out_hwpx)
    return {"output": str(out), "selected": selected,
            "groups": [g.to_dict() for g in all_groups], "findings": findings}
