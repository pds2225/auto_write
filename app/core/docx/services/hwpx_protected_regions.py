# -*- coding: utf-8 -*-
"""Protected-region classification on a HWPX structure index.

P0-2 separates protection from write permission. Nothing here sets
auto_write_allowed. Label linking and T02 approval belong to later stages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.docx.services.hwpx_analysis_adapter import (
    HwpxParagraphRecord,
    HwpxStructureIndex,
)

_GUIDANCE_MARKERS = ("※", "☞", "＊", "◈")
_GUIDANCE_TITLES = ("작성요령", "작성방법", "기재요령", "참고")
_GUIDANCE_COMMANDS = ("삭제 후 작성", "삭제후 작성", "삭제후작성", "해당 내용 작성")
_CHOICE_HEADERS = frozenset({"해당", "여", "부", "예", "아니오", "확인"})
_FAKE_LABELS = frozenset({
    "(서술 칸)", "(서술칸)", "(빈 칸)", "(빈칸)", "(이름 없음)", "(이름없음)",
})
_SIGNATURE_RE = re.compile(
    r"[\(（]\s*(?:서명|날인|직인|인)(?:\s*[,，]\s*(?:서명|날인|직인|인))?\s*[\)）]"
)
_DATE_SCAFFOLD_RE = re.compile(r"(?:\d{4}\s*)?년\s*월\s*일")
_LABEL_ONLY_RE = re.compile(r"^\s*\S.{0,40}?\s*[:：]\s*$", re.DOTALL)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _blank(text: str) -> bool:
    return (text or "").strip() == ""


def guidance_status(raw_text: str) -> str:
    """Return guidance, body, ambiguous, or none.

    A title or an opening instruction can be guidance. The same words inside
    a normal sentence are not. Unclear context stays ambiguous.
    """
    text = (raw_text or "").strip()
    if not text:
        return "none"
    if text.startswith(_GUIDANCE_MARKERS):
        return "guidance"
    imperative = any(token in text for token in ("십시오", "하시오", "하라", "하세요"))
    for title in _GUIDANCE_TITLES:
        if not text.startswith(title):
            continue
        after = text[len(title):]
        if after == "" or after[0] in ":：":
            if after == "" or imperative:
                return "guidance"
            return "ambiguous"
        break
    for command in _GUIDANCE_COMMANDS:
        if text.startswith(command):
            if imperative:
                return "guidance"
            return "ambiguous"
    mentions = any(title in text for title in _GUIDANCE_TITLES) or any(
        command in text for command in _GUIDANCE_COMMANDS
    )
    if not mentions:
        return "none"
    compact = _compact(text)
    if any(token in compact for token in ("배포했다", "개발했다", "개발하였다", "하였다")):
        return "body"
    return "ambiguous"


def is_guidance_paragraph(raw_text: str) -> bool:
    """True only for a clear guidance paragraph, never for a keyword alone."""
    return guidance_status(raw_text) == "guidance"


_HEADING_TOKENS = ("개요", "문제점", "전략")
_WEAK_HEADING_WORDS = ("계획", "현황", "내용", "방안")
_CHOICE_MARKS = ("□", "■", "○", "◯", "◦", "●", "☐", "◉", "☑", "〇", "✓", "✔")
_OPTION_MARKS = _CHOICE_MARKS
_CHOICE_MARK_RE = re.compile("[" + re.escape("".join(_CHOICE_MARKS)) + "]")
_UNIT_LABELS = frozenset({
    "대", "식", "개", "명", "원", "건", "회", "월", "일", "년", "시", "분",
    "호", "매", "장", "권", "통", "벌", "점", "차", "쪽",
})
_CONSENT_TOKENS = (
    "개인정보", "고유식별", "동의서", "동의자", "비동의", "동의함",
    "이용동의", "제공동의", "수집동의", "날인",
    # bare forms: 투자동의 / 동의하지않음 / 이행확약서 가 T02 로 남던 공백
    "동의", "확약", "서약",
)


def is_choice_header_text(raw_text: str) -> bool:
    return _compact(raw_text) in _CHOICE_HEADERS


def _is_square_heading(raw_text: str) -> bool:
    """Section-title bullet. A word such as 계획/현황/내용/방안 is not enough."""
    text = (raw_text or "").strip()
    if not text.startswith(("□", "■", "☐")):
        return False
    if len(_CHOICE_MARK_RE.findall(text)) != 1:
        return False
    rest = _compact(re.sub(r"^[□■☐☑○◉]\s*", "", text))
    if not rest or rest in {"예", "아니오", "유", "무", "동의", "동의함", "부동의"}:
        return False
    if any(token in rest for token in ("동의", "선택", "체크")):
        return False
    if not any(token in rest for token in _HEADING_TOKENS):
        return False
    without_weak = rest
    for word in _WEAK_HEADING_WORDS:
        without_weak = without_weak.replace(word, "")
    return any(token in without_weak for token in _HEADING_TOKENS)


def _is_option_line(raw_text: str) -> bool:
    """One selection mark plus an option label, including 계획 있음/계획 없음."""
    text = (raw_text or "").strip()
    if not text.startswith(_OPTION_MARKS):
        return False
    if len(_CHOICE_MARK_RE.findall(text)) != 1:
        return False
    rest = _compact(_CHOICE_MARK_RE.sub("", text, count=1))
    return bool(rest)


def _is_multi_choice(raw_text: str) -> bool:
    """Several selection marks, or one mark on a consent choice."""
    text = raw_text or ""
    count = len(_CHOICE_MARK_RE.findall(text))
    if count >= 2:
        return True
    compact = _compact(text)
    return count >= 1 and any(token in compact for token in ("비동의", "동의함", "동의하지", "부동의"))


def _is_choice_option(raw_text: str) -> bool:
    """A marked line that can belong to a choice group. Section titles cannot."""
    return _is_option_line(raw_text) and not _is_square_heading(raw_text)


def _is_question_label(raw_text: str) -> bool:
    text = (raw_text or "").strip()
    if not text or _is_option_line(text) or _is_multi_choice(text) or is_choice_header_text(text) or _is_square_heading(text):
        return False
    return True


@dataclass(frozen=True)
class ProtectionDecision:
    """A protection judgement. auto_write_allowed is never true in P0-2."""

    section_index: int
    paragraph_index: int
    run_index: int | None
    decision: str
    auto_write_allowed: bool
    field_label: str | None
    role: str
    review_reasons: tuple[str, ...]
    observed_text: str


@dataclass(frozen=True)
class ProtectionReport:
    decisions: tuple[ProtectionDecision, ...]

    @property
    def auto_write_allowed_count(self) -> int:
        return sum(1 for decision in self.decisions if decision.auto_write_allowed)


def _decision(
    paragraph: HwpxParagraphRecord,
    run_index: int | None,
    *,
    decision: str,
    role: str,
    reasons: tuple[str, ...],
    observed_text: str,
) -> ProtectionDecision:
    if decision not in {"NO_TARGET", "REVIEW_REQUIRED"}:
        raise ValueError(decision)
    label = None
    if label in _FAKE_LABELS:
        raise ValueError(label)
    return ProtectionDecision(
        section_index=paragraph.section_index,
        paragraph_index=paragraph.paragraph_index,
        run_index=run_index,
        decision=decision,
        auto_write_allowed=False,
        field_label=label,
        role=role,
        review_reasons=reasons,
        observed_text=observed_text,
    )


def _runs_of(paragraph: HwpxParagraphRecord):
    if paragraph.runs:
        return paragraph.runs
    return ()


def _is_date_scaffold_paragraph(raw_text: str) -> bool:
    text = raw_text or ""
    if not _DATE_SCAFFOLD_RE.search(text):
        return False
    return _DATE_SCAFFOLD_RE.sub("", text).strip() == ""


def _nearest_nonblank(runs, index: int, step: int):
    cursor = index + step
    while 0 <= cursor < len(runs):
        if not _blank(runs[cursor].raw_text):
            return runs[cursor]
        cursor += step
    return None


def _axis_range(start: int | None, span: int | None, address_status: str, span_status: str):
    if address_status != "PRESENT" or span_status != "PRESENT" or start is None or span is None:
        return None
    return (start, start + span)


def _ranges_overlap(left, right) -> bool:
    return left is not None and right is not None and left[0] < right[1] and right[0] < left[1]


def _choice_structure(section_paragraphs, table, paragraph: HwpxParagraphRecord) -> bool:
    """Confirm a choice group from cellAddr occupancy, not from a mark alone.

    A same-row pair of options is one group. A repeated column is a group only
    when a question or label shares that row or column. Section titles in one
    column are not options. Physical tc order is not a column.
    """
    if table is None:
        return False
    owner = next((cell for cell in table.cells if paragraph.paragraph_index in cell.paragraph_indexes), None)
    if owner is None:
        return False
    owner_text = "".join(section_paragraphs[index].raw_text for index in owner.paragraph_indexes)
    owner_row = _axis_range(owner.row, owner.row_span, owner.address_status, owner.span_status)
    owner_col = _axis_range(owner.col, owner.col_span, owner.address_status, owner.span_status)
    if owner_row is None or owner_col is None:
        return False

    def cell_text(cell) -> str:
        return "".join(section_paragraphs[index].raw_text for index in cell.paragraph_indexes)

    options = []
    plain_options = []
    headers = []
    labels = []
    for cell in table.cells:
        text = cell_text(cell)
        row = _axis_range(cell.row, cell.row_span, cell.address_status, cell.span_status)
        col = _axis_range(cell.col, cell.col_span, cell.address_status, cell.span_status)
        if row is None or col is None:
            continue
        if is_choice_header_text(text):
            headers.append((row, col))
        elif _is_option_line(text):
            options.append((row, col))
            if not _is_square_heading(text):
                plain_options.append((row, col))
        elif _is_question_label(text):
            labels.append((row, col))

    def same_row(items) -> int:
        return sum(1 for row, _col in items if _ranges_overlap(owner_row, row))

    def same_col(items) -> int:
        return sum(1 for _row, col in items if _ranges_overlap(owner_col, col))

    if _is_option_line(owner_text) and same_row(options) >= 2:
        return True
    if is_choice_header_text(owner_text):
        return same_row(headers) >= 2 or same_col(headers) >= 2
    if _is_square_heading(owner_text) or not _is_choice_option(owner_text):
        return False
    options = plain_options
    if same_row(options) >= 2:
        return True
    label_overlaps = any(
        _ranges_overlap(owner_row, row) or _ranges_overlap(owner_col, col)
        for row, col in labels
    )
    return same_col(options) >= 2 and (label_overlaps or same_col(headers) >= 1)


def _is_banner_heading(section_paragraphs, table, paragraph: HwpxParagraphRecord) -> bool:
    """A merged title row. The word 계획 is not evidence by itself."""
    del section_paragraphs
    text = (paragraph.raw_text or "").strip()
    compact = _compact(text)
    if (
        not compact
        or len(compact) > 40
        or any(mark in text for mark in _OPTION_MARKS)
        or text.endswith(("다", "요", "까", "음", "함", "니다"))
        or ":" in text
        or "：" in text
        or table is None
    ):
        return False
    owner = next((cell for cell in table.cells if paragraph.paragraph_index in cell.paragraph_indexes), None)
    if owner is None or owner.col_span is None or owner.col_span < 2:
        return False
    owner_row = _axis_range(owner.row, owner.row_span, owner.address_status, owner.span_status)
    if owner_row is None:
        return False
    for cell in table.cells:
        if cell is owner:
            continue
        row = _axis_range(cell.row, cell.row_span, cell.address_status, cell.span_status)
        if _ranges_overlap(owner_row, row):
            return False
    return True


def _span_decisions(
    paragraph: HwpxParagraphRecord,
    *,
    role: str,
    reasons: tuple[str, ...],
    decision: str,
) -> list[ProtectionDecision]:
    if not paragraph.runs:
        return [_decision(
            paragraph, None, decision=decision, role=role,
            reasons=reasons, observed_text=paragraph.raw_text,
        )]
    return [
        _decision(
            paragraph, run.run_index, decision=decision, role=role,
            reasons=reasons, observed_text=run.raw_text,
        )
        for run in paragraph.runs
    ]


def _classify_paragraph(
    paragraph: HwpxParagraphRecord,
    choice_ready: bool,
    banner_heading: bool = False,
) -> list[ProtectionDecision]:
    status = guidance_status(paragraph.raw_text)
    if status == "guidance":
        return _span_decisions(
            paragraph, role="GUIDANCE", decision="NO_TARGET", reasons=("GUIDANCE_ONLY",),
        )
    if status == "ambiguous":
        return _span_decisions(
            paragraph, role="AMBIGUOUS", decision="REVIEW_REQUIRED", reasons=("GUIDANCE_AMBIGUOUS",),
        )
    if _is_date_scaffold_paragraph(paragraph.raw_text):
        return _protected_span(paragraph, role="DATE_SCAFFOLD", reason="TARGET_BOUNDARY_AMBIGUOUS")
    if _SIGNATURE_RE.search(paragraph.raw_text or ""):
        return _protected_span(paragraph, role="SIGNATURE", reason="SIGNATURE_PROTECTED")
    if is_choice_header_text(paragraph.raw_text):
        if choice_ready:
            return _span_decisions(
                paragraph, role="CHOICE_HEADER", decision="NO_TARGET", reasons=("QUESTION_UNRESOLVED",),
            )
        return _span_decisions(
            paragraph, role="UNCONFIRMED_CHOICE", decision="REVIEW_REQUIRED", reasons=("QUESTION_UNRESOLVED",),
        )
    if _is_option_line(paragraph.raw_text) and choice_ready:
        return _span_decisions(
            paragraph, role="CHOICE_MARK", decision="NO_TARGET", reasons=("QUESTION_UNRESOLVED",),
        )
    if _is_square_heading(paragraph.raw_text):
        return _span_decisions(
            paragraph, role="HEADING", decision="NO_TARGET", reasons=("LABEL_PROTECTED",),
        )
    if _is_option_line(paragraph.raw_text):
        return _span_decisions(
            paragraph, role="UNCONFIRMED_CHOICE", decision="REVIEW_REQUIRED", reasons=("QUESTION_UNRESOLVED",),
        )
    if _is_multi_choice(paragraph.raw_text):
        return _span_decisions(
            paragraph, role="UNCONFIRMED_CHOICE", decision="REVIEW_REQUIRED", reasons=("QUESTION_UNRESOLVED",),
        )
    if banner_heading:
        return _span_decisions(
            paragraph, role="HEADING", decision="NO_TARGET", reasons=("LABEL_PROTECTED",),
        )
    if (paragraph.raw_text or "").strip().startswith(("□", "■", "☐")):
        return _span_decisions(
            paragraph, role="UNCONFIRMED_CHOICE", decision="REVIEW_REQUIRED", reasons=("QUESTION_UNRESOLVED",),
        )

    results: list[ProtectionDecision] = []
    runs = _runs_of(paragraph)
    if not runs:
        return [_decision(
            paragraph, None, decision="REVIEW_REQUIRED", role="EMPTY",
            reasons=("TARGET_BOUNDARY_AMBIGUOUS",), observed_text=paragraph.raw_text,
        )]
    for index, run in enumerate(runs):
        later = any(not _blank(other.raw_text) for other in runs if other.run_index > run.run_index)
        text = run.raw_text
        if _blank(text) and later:
            previous = _nearest_nonblank(runs, index, -1)
            following = _nearest_nonblank(runs, index, 1)
            between_labels = (
                previous is not None and following is not None
                and _LABEL_ONLY_RE.match(previous.raw_text) is not None
                and _LABEL_ONLY_RE.match(following.raw_text) is not None
            )
            if between_labels or previous is not None:
                results.append(_decision(
                    paragraph, run.run_index, decision="REVIEW_REQUIRED", role="EMPTY",
                    reasons=("TARGET_BOUNDARY_AMBIGUOUS",), observed_text=text,
                ))
            else:
                results.append(_decision(
                    paragraph, run.run_index, decision="NO_TARGET", role="SPACER",
                    reasons=("TARGET_BOUNDARY_AMBIGUOUS",), observed_text=text,
                ))
            continue
        if _LABEL_ONLY_RE.match(text):
            results.append(_decision(
                paragraph, run.run_index, decision="NO_TARGET", role="LABEL",
                reasons=("LABEL_PROTECTED",), observed_text=text,
            ))
            continue
        if not _blank(text):
            results.append(_decision(
                paragraph, run.run_index, decision="NO_TARGET", role="EXISTING_VALUE",
                reasons=("EXISTING_VALUE",), observed_text=text,
            ))
            continue
        results.append(_decision(
            paragraph, run.run_index, decision="REVIEW_REQUIRED", role="EMPTY",
            reasons=("WRITER_CAPABILITY_UNVERIFIED",), observed_text=text,
        ))
    return results


def _protected_span(paragraph: HwpxParagraphRecord, *, role: str, reason: str) -> list[ProtectionDecision]:
    """Apply one paragraph meaning to every run that belongs to that meaning."""
    runs = list(paragraph.runs)
    if not runs:
        return [_decision(
            paragraph, None, decision="REVIEW_REQUIRED", role=role,
            reasons=(reason, "TARGET_BOUNDARY_AMBIGUOUS"), observed_text=paragraph.raw_text,
        )]
    first_content = next((index for index, run in enumerate(runs) if not _blank(run.raw_text)), None)
    results: list[ProtectionDecision] = []
    for index, run in enumerate(runs):
        if first_content is not None and index < first_content:
            results.append(_decision(
                paragraph, run.run_index, decision="NO_TARGET", role="SPACER",
                reasons=("TARGET_BOUNDARY_AMBIGUOUS",), observed_text=run.raw_text,
            ))
            continue
        reasons = (reason,) if len([item for item in runs if not _blank(item.raw_text)]) == 1 and not _blank(run.raw_text) else (
            reason, "TARGET_BOUNDARY_AMBIGUOUS",
        )
        single = len([item for item in runs if not _blank(item.raw_text)]) == 1 and not _blank(run.raw_text)
        if role == "SIGNATURE" and single:
            remainder = _SIGNATURE_RE.sub("", run.raw_text).strip()
            results.append(_decision(
                paragraph, run.run_index,
                decision="NO_TARGET" if not remainder else "REVIEW_REQUIRED",
                role=role,
                reasons=("SIGNATURE_PROTECTED",) if not remainder else ("SIGNATURE_PROTECTED", "TARGET_BOUNDARY_AMBIGUOUS"),
                observed_text=run.raw_text,
            ))
            continue
        results.append(_decision(
            paragraph, run.run_index, decision="REVIEW_REQUIRED", role=role,
            reasons=reasons, observed_text=run.raw_text,
        ))
    return results


def classify_protected_regions(index: HwpxStructureIndex) -> ProtectionReport:
    """Mark protected text and refuse write permission.

    Guidance, labels, existing values, signatures, date scaffolds, and choice
    headers are not write targets. An empty run in front of a label is not a
    write target. This stage does not approve any automatic write.
    """
    decisions: list[ProtectionDecision] = []
    paragraphs_by_section = {section.section_index: section.paragraphs for section in index.sections}
    for section in index.sections:
        for paragraph in section.paragraphs:
            table = index.tables[paragraph.table_index] if paragraph.table_index is not None else None
            section_paragraphs = paragraphs_by_section[section.section_index]
            choice_ready = _choice_structure(section_paragraphs, table, paragraph)
            banner_heading = _is_banner_heading(section_paragraphs, table, paragraph)
            decisions.extend(_classify_paragraph(paragraph, choice_ready, banner_heading))
    for decision in decisions:
        if decision.auto_write_allowed:
            raise RuntimeError("P0-2 cannot grant write permission")
        if decision.field_label in _FAKE_LABELS:
            raise RuntimeError("synthetic field label")
        if decision.role == "GUIDANCE" and decision.observed_text.strip() and not is_guidance_paragraph(
            next(
                paragraph.raw_text
                for section in index.sections
                if section.section_index == decision.section_index
                for paragraph in section.paragraphs
                if paragraph.paragraph_index == decision.paragraph_index
            )
        ):
            raise RuntimeError("guidance role without guidance paragraph")
    return ProtectionReport(decisions=tuple(decisions))


@dataclass(frozen=True)
class T02Target:
    """A unique label whose value cell is completely empty. This is the only AUTO shape."""

    field_label: str
    section_member: str
    section_index: int
    paragraph_index: int
    run_index: int
    text_node_index: int | None
    expected_raw_text: str
    table_index: int
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1


_NOT_T02_LABELS = frozenset({"해당", "여", "부", "예", "아니오", "확인"})


def _cell_joined(section, cell) -> str:
    return "".join(section.paragraphs[index].raw_text for index in cell.paragraph_indexes)


def _cell_placed(cell) -> bool:
    return (
        cell.address_status == "PRESENT"
        and cell.span_status == "PRESENT"
        and None not in (cell.row, cell.col, cell.row_span, cell.col_span)
    )


def _right_value_cell(table, cell):
    if not _cell_placed(cell):
        return None
    start = cell.col + cell.col_span
    hits = []
    for other in table.cells:
        if not _cell_placed(other):
            continue
        same_row = cell.row < other.row + other.row_span and other.row < cell.row + cell.row_span
        if same_row and other.col == start:
            hits.append(other)
    if len(hits) != 1:
        return None
    return hits[0]


def _sign_consent_label(compact: str) -> bool:
    """Privacy, consent, and seal wording. 부서명 and 겸직인력 stay eligible."""
    if any(token in compact for token in _CONSENT_TOKENS):
        return True
    without_department = compact.replace("부서명", "")
    if "서명" in without_department:
        return True
    without_concurrent = compact.replace("겸직인", "")
    if "직인" in without_concurrent:
        return True
    return False


def _guidance_title_label(text: str, compact: str) -> bool:
    """A section or appendix title, not a short notes field such as 참고사항."""
    stripped = (text or "").strip().lstrip("-–—▪•· ")
    folded = _compact(stripped)
    # "참 고" / "참고:" is the reference heading. "참고사항" stays a notes field.
    if folded == "참고" or re.fullmatch(r"참고[\d.．:：\-‐-―]+", folded):
        return True
    if re.fullmatch(r"(?:참고|예시)\d+(?:[-‐.~．]\d+)*", folded):
        return True
    if re.search(r"(?:작성요령|작성방법|기재요령)$", compact):
        return True
    if compact.endswith("안내"):
        return True
    if "안내" in compact and (stripped[:1] in "-–—▪" or "/" in text):
        return True
    if "유의사항" in compact and "문의" in compact:
        return True
    if re.search(r"[\(（]\s*예시\s*[\)）]", text):
        return True
    return False


def _t02_label(raw_text: str) -> str | None:
    text = (raw_text or "").strip()
    compact = _compact(text).rstrip(":：")
    if not compact or compact in _NOT_T02_LABELS or len(compact) > 40:
        return None
    if compact.isdigit() or re.fullmatch(r"서식\d+", compact):
        return None
    if _guidance_title_label(text, compact):
        return None
    if compact in _UNIT_LABELS or re.fullmatch(r"\d+(?:대|식|개|명|원|건|회|호)", compact):
        return None
    if re.fullmatch(r"\d{2,4}년", compact) or re.fullmatch(r"\d{1,2}월", compact) or re.fullmatch(r"\d{1,2}일", compact):
        return None
    if re.match(r"^(?:\d+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)[.．)]", text):
        return None
    if _CHOICE_MARK_RE.search(text) or _is_multi_choice(text):
        return None
    if any(mark in text for mark in ("※", "☞", "•", "∙", "·")):
        return None
    if any(mark in text for mark in ("?", "？")) or compact.endswith(("나요", "가요", "습니까", "인가요")):
        return None
    if guidance_status(text) == "guidance" or _is_square_heading(text):
        return None
    if any(compact.startswith(_compact(command)) for command in _GUIDANCE_COMMANDS):
        return None
    if _sign_consent_label(compact):
        return None
    if re.search(r"[:：]\s*\S", text):
        return None
    if _SIGNATURE_RE.search(text) or _is_date_scaffold_paragraph(text):
        return None
    if text.endswith(("다.", "요.", "니다.", "까.")):
        return None
    if not re.search(r"[가-힣]", compact) and not re.fullmatch(r"[A-Za-z][A-Za-z0-9@._+-]{1,30}", compact):
        return None
    return compact


def _touches(left, right) -> bool:
    row_overlap = left.row < right.row + right.row_span and right.row < left.row + left.row_span
    col_overlap = left.col < right.col + right.col_span and right.col < left.col + left.col_span
    row_touch = left.row + left.row_span == right.row or right.row + right.row_span == left.row
    col_touch = left.col + left.col_span == right.col or right.col + right.col_span == left.col
    return (row_overlap and col_touch) or (col_overlap and row_touch)


def _neighbor_is_guidance(section, table, value) -> bool:
    for other in table.cells:
        if other is value or not _cell_placed(other):
            continue
        row_overlap = value.row < other.row + other.row_span and other.row < value.row + value.row_span
        col_touch = value.col + value.col_span == other.col or other.col + other.col_span == value.col
        if not (row_overlap and col_touch):
            continue
        text = _cell_joined(section, other).strip()
        if "※" in text or guidance_status(text) == "guidance":
            return True
    return False


def _value_claim_counts(index: HwpxStructureIndex) -> dict[tuple[int, int, int, int], int]:
    """How many non-empty cells treat the same physical cell as their right neighbor."""
    counts: dict[tuple[int, int, int, int], int] = {}
    for section in index.sections:
        for table_index in section.table_indexes:
            table = index.tables[table_index]
            for cell in table.cells:
                if not _cell_placed(cell) or not _cell_joined(section, cell).strip():
                    continue
                value = _right_value_cell(table, cell)
                if value is None or not _cell_placed(value):
                    continue
                key = (section.section_index, table.table_index, value.row, value.col)
                counts[key] = counts.get(key, 0) + 1
    return counts


def _repeated_entry_row(section, table, value_cell) -> bool:
    """Continuation blank rows under the same value column, with no label of their own."""

    def unlabeled_blank_at(row: int) -> bool:
        matches = [
            other for other in table.cells
            if other is not value_cell and _cell_placed(other)
            and other.col == value_cell.col and other.row == row
            and other.row_span == 1 and other.col_span == 1
        ]
        if len(matches) != 1:
            return False
        other = matches[0]
        if _cell_joined(section, other).strip():
            return False
        left = [
            cell for cell in table.cells
            if cell is not other and _cell_placed(cell) and cell.col + cell.col_span == other.col
            and cell.row < other.row + other.row_span and other.row < cell.row + cell.row_span
        ]
        return not left or all(not _cell_joined(section, cell).strip() for cell in left)

    extras = 0
    for step in (-1, 1):
        cursor = value_cell.row + step
        while unlabeled_blank_at(cursor):
            extras += 1
            cursor += step
            if extras >= 2:
                return True
    return False


def _above_label_conflict(section, table, value_cell) -> bool:
    """A header directly above the value, with no label of its own, claims the cell."""
    for other in table.cells:
        if not _cell_placed(other) or other.col != value_cell.col:
            continue
        if other.row + other.row_span != value_cell.row:
            continue
        if not _cell_joined(section, other).strip():
            continue
        left = [
            cell for cell in table.cells
            if cell is not other and _cell_placed(cell) and cell.col + cell.col_span == other.col
            and cell.row < other.row + other.row_span and other.row < cell.row + cell.row_span
            and _cell_joined(section, cell).strip()
        ]
        if not left:
            return True
    return False


def _ambiguous_guidance_phrase(text: str) -> bool:
    """A guidance phrase, not a short notes label such as 참고사항."""
    if guidance_status(text) != "ambiguous":
        return False
    compact = _compact(text)
    if any(token in compact for token in ("안내", "요령", "관련")):
        return True
    return len(compact) > 12


def _protected_label_paragraphs(index: HwpxStructureIndex) -> set[tuple[int, int]]:
    """Label paragraphs whose protection is unresolved or explicitly unsafe."""
    blocked: set[tuple[int, int]] = set()
    unsafe_roles = {
        "GUIDANCE", "SIGNATURE", "DATE_SCAFFOLD",
        "CHOICE_HEADER", "CHOICE_MARK", "HEADING", "UNCONFIRMED_CHOICE",
    }
    for decision in classify_protected_regions(index).decisions:
        if decision.role == "AMBIGUOUS" and _ambiguous_guidance_phrase(decision.observed_text):
            blocked.add((decision.section_index, decision.paragraph_index))
        elif decision.role in unsafe_roles:
            blocked.add((decision.section_index, decision.paragraph_index))
        elif decision.decision == "REVIEW_REQUIRED" and decision.role not in {"EMPTY", "AMBIGUOUS"}:
            blocked.add((decision.section_index, decision.paragraph_index))
    return blocked


def _left_t02_label_for_value_cell(section, table, value_cell, protection: dict[tuple[int, int], ProtectionDecision]) -> str | None:
    """Immediate logical-left label for non-auto assessment records."""
    if not _cell_placed(value_cell):
        return None
    candidates = []
    for other in table.cells:
        if other is value_cell or other.has_nested_table or other.has_non_text_object or not _cell_placed(other):
            continue
        same_row = other.row < value_cell.row + value_cell.row_span and value_cell.row < other.row + other.row_span
        if same_row and other.col + other.col_span == value_cell.col:
            candidates.append(other)
    if len(candidates) != 1:
        return None
    label_cell = candidates[0]
    unsafe_roles = {
        "GUIDANCE", "SIGNATURE", "DATE_SCAFFOLD",
        "CHOICE_HEADER", "CHOICE_MARK", "HEADING", "UNCONFIRMED_CHOICE",
    }
    for paragraph_index in label_cell.paragraph_indexes:
        decision = protection.get((section.section_index, paragraph_index))
        if decision is None:
            continue
        if decision.role == "AMBIGUOUS" and _ambiguous_guidance_phrase(decision.observed_text):
            return None
        if decision.role in unsafe_roles:
            return None
    return _t02_label(_cell_joined(section, label_cell))


def _repeated_value_columns(section, table) -> set[int]:
    """Columns with a heading cell and 3 or more following empty instance rows."""
    by_col: dict[int, list] = {}
    for cell in table.cells:
        if _cell_placed(cell) and cell.row_span == 1 and cell.col_span == 1:
            by_col.setdefault(cell.col, []).append(cell)
    repeated: set[int] = set()
    for col, cells in by_col.items():
        ordered = sorted(cells, key=lambda cell: cell.row)
        previous_row = None
        run = 0
        armed = False
        for cell in ordered:
            if previous_row is not None and cell.row != previous_row + 1:
                run = 0
                armed = False
            previous_row = cell.row
            if _cell_joined(section, cell).strip():
                armed = True
                run = 0
                continue
            if not armed:
                continue
            neighbors = [
                other for other in table.cells
                if other is not cell and _cell_placed(other) and other.row == cell.row
                and _cell_joined(section, other).strip()
            ]
            if not neighbors:
                run = 0
                continue
            run += 1
            if run >= 3:
                repeated.add(col)
    return repeated


def _plain_empty_run(run) -> bool:
    if run.has_nested_table or run.has_non_text_object or (run.raw_text or "").strip():
        return False
    if len(run.text_nodes) > 1:
        return False
    if len(run.text_nodes) == 1 and run.text_nodes[0].raw_text != "":
        return False
    return True


def _t02_value_run(section, paragraph):
    """Return the run identity for a T02 value cell, or None if unsupported."""
    if len(paragraph.runs) == 1:
        run = paragraph.runs[0]
        return run if _plain_empty_run(run) else None
    if section.section_index > 0 and paragraph.runs and all(_plain_empty_run(run) for run in paragraph.runs):
        return paragraph.runs[0]
    return None


def _t02_value_span_supported(section, value_cell) -> bool:
    if value_cell.row_span != 1:
        return False
    if value_cell.col_span == 1:
        return True
    return section.section_index > 0 and value_cell.col_span is not None and value_cell.col_span > 1


def find_t02_auto_targets(index: HwpxStructureIndex) -> tuple[T02Target, ...]:
    """Return only label-plus-completely-empty-cell targets. Nothing else is AUTO."""
    if index.analysis_status != "COMPLETE":
        return ()
    blocked = _protected_label_paragraphs(index)
    counted: dict[tuple[int, int, str], int] = {}
    located = []
    for section in index.sections:
        for table_index in section.table_indexes:
            table = index.tables[table_index]
            if table.story_scope != "body" or table.parent_table_index is not None:
                continue
            for cell in table.cells:
                if cell.has_nested_table or cell.has_non_text_object or not _cell_placed(cell):
                    continue
                if cell.row_span != 1:
                    continue
                if any((section.section_index, item) in blocked for item in cell.paragraph_indexes):
                    continue
                label_paragraphs = [section.paragraphs[item] for item in cell.paragraph_indexes]
                if any(item.story_scope != "body" for item in label_paragraphs):
                    continue
                label = _t02_label(_cell_joined(section, cell))
                if label is None:
                    continue
                key = (section.section_index, table.table_index, label)
                counted[key] = counted.get(key, 0) + 1
                located.append((section, table, cell, label))
    claims = _value_claim_counts(index)
    results: list[T02Target] = []
    for section, table, cell, label in located:
        if counted.get((section.section_index, table.table_index, label), 0) != 1:
            continue
        value = _right_value_cell(table, cell)
        if value is None or value.has_nested_table or value.has_non_text_object or not _cell_placed(value):
            continue
        if not _t02_value_span_supported(section, value):
            continue
        if value.col in _repeated_value_columns(section, table):
            continue
        if _repeated_entry_row(section, table, value) or _above_label_conflict(section, table, value):
            continue
        claim_key = (section.section_index, table.table_index, value.row, value.col)
        if claims.get(claim_key, 0) != 1:
            continue
        if _neighbor_is_guidance(section, table, value):
            continue
        if _cell_joined(section, value).strip():
            continue
        if len(value.paragraph_indexes) != 1:
            continue
        paragraph = section.paragraphs[value.paragraph_indexes[0]]
        if paragraph.story_scope != "body":
            continue
        run = _t02_value_run(section, paragraph)
        if run is None:
            continue
        results.append(T02Target(
            field_label=label,
            section_member=section.section_member,
            section_index=section.section_index,
            paragraph_index=paragraph.paragraph_index,
            run_index=run.run_index,
            text_node_index=None if not run.text_nodes else run.text_nodes[0].text_node_index,
            expected_raw_text="",
            table_index=table.table_index,
            row=value.row,
            col=value.col,
            row_span=value.row_span,
            col_span=value.col_span,
        ))
    return tuple(results)


@dataclass(frozen=True)
class FieldAssessment:
    field_label: str | None
    field_type: str
    structure_types: tuple[str, ...]
    section_member: str
    section_index: int
    table_index: int | None
    paragraph_index: int | None
    run_index: int | None
    text_node_index: int | None
    row: int | None
    col: int | None
    row_span: int | None
    col_span: int | None
    content_state: str
    protected: bool
    guidance: bool
    confidence: str
    decision: str
    review_reason: tuple[str, ...]
    evidence: tuple[str, ...]
    auto_write_allowed: bool
    write_target: tuple | None = None
    eligible: bool = False
    story_scope: str = ""
    table_index_in_section: int | None = None
    physical_tr_index: int | None = None
    physical_tc_index: int | None = None
    parent_table_index: int | None = None
    address_status: str = ""
    span_status: str = ""
    protection_role: str = ""
    protection_decision: str = ""


def _owned_cell(index: HwpxStructureIndex, paragraph: HwpxParagraphRecord):
    if paragraph.table_index is None or paragraph.table_index >= len(index.tables):
        return None, None
    table = index.tables[paragraph.table_index]
    cell = next((item for item in table.cells if paragraph.paragraph_index in item.paragraph_indexes), None)
    return table, cell


def _structure_fields(index: HwpxStructureIndex, paragraph: HwpxParagraphRecord) -> dict:
    """Copy P0-1 coordinates. Missing XML stays null; a non-cell is marked, not erased."""
    table, cell = _owned_cell(index, paragraph)
    return {
        "story_scope": paragraph.story_scope,
        "table_index_in_section": None if table is None else table.table_index_in_section,
        "row": None if cell is None else cell.row,
        "col": None if cell is None else cell.col,
        "row_span": None if cell is None else cell.row_span,
        "col_span": None if cell is None else cell.col_span,
        "physical_tr_index": paragraph.physical_tr_index if cell is None else cell.physical_tr_index,
        "physical_tc_index": paragraph.physical_tc_index if cell is None else cell.physical_tc_index,
        "parent_table_index": None if table is None else table.parent_table_index,
        "address_status": "NOT_IN_TABLE" if cell is None else cell.address_status,
        "span_status": "" if cell is None else cell.span_status,
    }


def _assessment_from_paragraph(index, section, paragraph, types: tuple[str, ...], **kwargs) -> FieldAssessment:
    table_index = paragraph.table_index
    run = paragraph.runs[0] if paragraph.runs else None
    node = run.text_nodes[0] if run and run.text_nodes else None
    structure = _structure_fields(index, paragraph)
    for key in structure:
        if key in kwargs:
            structure[key] = kwargs[key]
    return FieldAssessment(
        field_label=kwargs.get("field_label"),
        field_type=types[0],
        structure_types=types,
        section_member=section.section_member,
        section_index=section.section_index,
        table_index=table_index,
        paragraph_index=paragraph.paragraph_index,
        run_index=None if run is None else run.run_index,
        text_node_index=None if node is None else node.text_node_index,
        content_state=kwargs.get("content_state", "MIXED"),
        protected=kwargs.get("protected", True),
        guidance=kwargs.get("guidance", False),
        confidence=kwargs.get("confidence", "LOW"),
        decision=kwargs.get("decision", "REVIEW_REQUIRED"),
        review_reason=kwargs.get("review_reason", ("UNRESOLVED",)),
        evidence=kwargs.get("evidence", ()),
        auto_write_allowed=False,
        protection_role=kwargs.get("protection_role", ""),
        protection_decision=kwargs.get("protection_decision", ""),
        **structure,
    )


def assess_fields(index: HwpxStructureIndex) -> tuple[FieldAssessment, ...]:
    """Detect T01–T16. P0-2 records T02 candidates and does not authorize writes."""
    records: list[FieldAssessment] = []
    protection = {
        (decision.section_index, decision.paragraph_index): decision
        for decision in classify_protected_regions(index).decisions
    }
    for target in find_t02_auto_targets(index):
        section = next(item for item in index.sections if item.section_index == target.section_index)
        paragraph = section.paragraphs[target.paragraph_index]
        table = index.tables[target.table_index]
        value_cell = next(cell for cell in table.cells if target.paragraph_index in cell.paragraph_indexes)
        label_decision = next((
            protection[(section.section_index, cell_paragraph)]
            for cell in table.cells
            if _cell_placed(cell) and _right_value_cell(table, cell) is value_cell
            for cell_paragraph in cell.paragraph_indexes
            if (section.section_index, cell_paragraph) in protection
        ), None)
        value_decision = protection.get((section.section_index, paragraph.paragraph_index))
        records.append(FieldAssessment(
            field_label=target.field_label,
            field_type="T02",
            structure_types=("T02",),
            section_member=target.section_member,
            section_index=target.section_index,
            table_index=target.table_index,
            paragraph_index=target.paragraph_index,
            run_index=target.run_index,
            text_node_index=target.text_node_index,
            row=value_cell.row,
            col=value_cell.col,
            row_span=value_cell.row_span,
            col_span=value_cell.col_span,
            content_state="EMPTY",
            protected=False,
            guidance=False,
            confidence="HIGH",
            decision="REVIEW_REQUIRED",
            review_reason=("AUTHORIZATION_PENDING",),
            evidence=("UNIQUE_LABEL", "EMPTY_VALUE_CELL", "LOGICAL_RIGHT", "T02_CANDIDATE"),
            auto_write_allowed=False,
            write_target=None,
            eligible=True,
            story_scope=paragraph.story_scope,
            table_index_in_section=table.table_index_in_section,
            physical_tr_index=value_cell.physical_tr_index,
            physical_tc_index=value_cell.physical_tc_index,
            parent_table_index=table.parent_table_index,
            address_status=value_cell.address_status,
            span_status=value_cell.span_status,
            protection_role="" if label_decision is None else label_decision.role,
            protection_decision="" if value_decision is None else value_decision.decision,
        ))
    auto_paragraphs = {(item.section_index, item.paragraph_index) for item in records}
    for section in index.sections:
        paragraphs = section.paragraphs
        for paragraph in paragraphs:
            if (section.section_index, paragraph.paragraph_index) in auto_paragraphs:
                continue
            text = paragraph.raw_text or ""
            types: list[str] = []
            label = None
            state = "EXISTING" if text.strip() else "EMPTY"
            guidance = guidance_status(text) == "guidance"
            reasons: list[str] = []
            evidence: list[str] = []
            decision = "REVIEW_REQUIRED"
            if guidance:
                types.append("T07")
                state = "GUIDANCE"
                decision = "NO_TARGET"
                reasons.append("GUIDANCE_ONLY")
                cell_paras = []
                if paragraph.table_index is not None:
                    table = index.tables[paragraph.table_index]
                    owner = next((cell for cell in table.cells if paragraph.paragraph_index in cell.paragraph_indexes), None)
                    if owner is not None:
                        cell_paras = [paragraphs[index_] for index_ in owner.paragraph_indexes]
                if not any(not item.raw_text.strip() for item in cell_paras if item.paragraph_index != paragraph.paragraph_index):
                    types.append("T08")
                    evidence.append("NO_SEPARATE_EMPTY_PARAGRAPH")
            if _is_date_scaffold_paragraph(text):
                types.append("T05")
                state = "DATE"
                decision = "NO_TARGET"
                reasons.append("DATE_SCAFFOLD")
            if _SIGNATURE_RE.search(text):
                types.append("T06")
                state = "SIGNATURE"
                decision = "NO_TARGET"
                reasons.append("SIGNATURE_PROTECTED")
                label = None
            if is_choice_header_text(text) or _is_option_line(text):
                types.append("T09")
                decision = "REVIEW_REQUIRED"
                reasons.append("CHOICE_NOT_QUESTION")
                label = None
                evidence.append("CHOICE_MARK")
            if len(paragraph.runs) == 1 and text.strip() and (":" in text or "：" in text) and (
                _SIGNATURE_RE.search(text) or _is_date_scaffold_paragraph(text) or not _t02_label(text)
            ):
                types.append("T03")
                decision = "NO_TARGET"
                reasons.append("SAME_RUN_LABEL")
                label = None
            if len(paragraph.runs) >= 2 and any(not run.raw_text.strip() for run in paragraph.runs) and any(run.raw_text.strip() for run in paragraph.runs):
                types.append("T04")
                decision = "REVIEW_REQUIRED"
                reasons.append("FIRST_EMPTY_RUN_NOT_TARGET")
                label = None
            if section.section_index > 0:
                types.append("T14")
                evidence.append("LATER_SECTION")
            if paragraph.table_index is not None:
                table = index.tables[paragraph.table_index]
                owner = next((cell for cell in table.cells if paragraph.paragraph_index in cell.paragraph_indexes), None)
                if owner is not None and not text.strip():
                    label = _left_t02_label_for_value_cell(section, table, owner, protection)
                if owner is not None and owner.has_nested_table:
                    types.append("T13")
                    reasons.append("NESTED_TABLE")
                if owner is not None and owner.has_non_text_object:
                    types.append("T15")
                    reasons.append("NON_TEXT_OBJECT")
                if owner is not None and owner.address_status != "PRESENT":
                    types.append("T01")
                    reasons.append("ADDRESS_MISSING")
                if owner is not None and _is_banner_heading(paragraphs, table, paragraph):
                    types.append("T10")
                    label = None
                    decision = "NO_TARGET"
                    reasons.append("MERGED_HEADING_NOT_LABEL")
            if text.strip() and not types:
                types.append("T11")
                decision = "NO_TARGET"
                reasons.append("EXISTING_VALUE")
            elif not text.strip() and not types:
                types.append("T16")
                decision = "REVIEW_REQUIRED"
                reasons.append("EMPTY_WITHOUT_LABEL")
                evidence.append("NOT_FIRST_EMPTY_RUN_TARGET")
            if not types:
                continue
            if "T02" in types:
                continue
            guarded = protection.get((section.section_index, paragraph.paragraph_index))
            records.append(_assessment_from_paragraph(
                index, section, paragraph, tuple(dict.fromkeys(types)),
                field_label=label,
                content_state=state,
                guidance=guidance,
                decision=decision,
                review_reason=tuple(dict.fromkeys(reasons)) or ("UNRESOLVED",),
                evidence=tuple(evidence),
                protected=decision != "AUTO",
                protection_role="" if guarded is None else guarded.role,
                protection_decision="" if guarded is None else guarded.decision,
            ))
    repeated: dict[tuple[int, int], int] = {}
    for section in index.sections:
        for table_index in section.table_indexes:
            table = index.tables[table_index]
            for cell in table.cells:
                if _cell_placed(cell) and not _cell_joined(section, cell).strip():
                    repeated[(table.table_index, cell.col)] = repeated.get((table.table_index, cell.col), 0) + 1
    for (table_index, col), count in repeated.items():
        if count < 3:
            continue
        records.append(FieldAssessment(
            field_label=None, field_type="T12", structure_types=("T12",),
            section_member="", section_index=0, table_index=table_index,
            paragraph_index=None, run_index=None, text_node_index=None,
            row=None, col=col, row_span=None, col_span=None,
            content_state="EMPTY", protected=True, guidance=False, confidence="LOW",
            decision="REVIEW_REQUIRED", review_reason=("REPEATED_EMPTY_COLUMN",),
            evidence=(f"count={count}",), auto_write_allowed=False,
        ))
    for record in records:
        if record.decision == "AUTO" or record.auto_write_allowed or record.write_target is not None:
            raise RuntimeError("P0-2 cannot authorize a write")
        if record.eligible and record.field_type != "T02":
            raise RuntimeError("only T02 may be eligible")
        if record.field_label in _FAKE_LABELS:
            raise RuntimeError("synthetic field label")
    return tuple(records)


@dataclass(frozen=True)
class T02WriteAuthorization:
    """Internal P1 grant. A JSON flag cannot be substituted for one of these."""

    source_sha256: str
    field_label: str
    section_member: str
    section_index: int
    table_index: int
    row: int
    col: int
    row_span: int
    col_span: int
    paragraph_index: int
    run_index: int
    text_node_index: int | None
    expected_raw_text: str
    story_scope: str


def _exact_writer_supports(index: HwpxStructureIndex, target: T02Target) -> bool:
    """The existing exact writer can change only one empty hp:t in a body cell."""
    if target.row_span != 1 or target.col_span != 1 or target.expected_raw_text != "":
        return False
    if target.table_index >= len(index.tables):
        return False
    table = index.tables[target.table_index]
    if table.story_scope != "body" or table.parent_table_index is not None:
        return False
    section = next((item for item in index.sections if item.section_index == target.section_index), None)
    if section is None or target.paragraph_index >= len(section.paragraphs):
        return False
    paragraph = section.paragraphs[target.paragraph_index]
    if paragraph.story_scope != "body" or len(paragraph.runs) != 1:
        return False
    run = paragraph.runs[0]
    if run.run_index != target.run_index or run.has_nested_table or run.has_non_text_object:
        return False
    if len(run.text_nodes) > 1 or (run.raw_text or "").strip():
        return False
    if run.text_nodes and run.text_nodes[0].raw_text != "":
        return False
    return True


def authorize_t02_writes(index: HwpxStructureIndex) -> tuple[T02WriteAuthorization, ...]:
    """Issue grants from the index. Assessment never sets auto_write_allowed."""
    if index.analysis_status != "COMPLETE" or not index.source_sha256:
        return ()
    fields = {
        (field.section_index, field.table_index, field.row, field.col, field.field_label): field
        for field in assess_fields(index)
        if field.field_type == "T02" and field.eligible and field.field_label
    }
    grants: list[T02WriteAuthorization] = []
    for target in find_t02_auto_targets(index):
        field = fields.get((target.section_index, target.table_index, target.row, target.col, target.field_label))
        if field is None or field.protected or field.guidance or not field.eligible:
            continue
        if field.protection_role in {
            "GUIDANCE", "AMBIGUOUS", "SIGNATURE", "DATE_SCAFFOLD",
            "CHOICE_HEADER", "CHOICE_MARK", "HEADING", "UNCONFIRMED_CHOICE",
        }:
            continue
        if field.row_span != 1 or field.col_span != 1 or field.story_scope != "body":
            continue
        if field.address_status not in {"", "PRESENT"}:
            continue
        if not _exact_writer_supports(index, target):
            continue
        grants.append(T02WriteAuthorization(
            source_sha256=index.source_sha256,
            field_label=target.field_label,
            section_member=target.section_member,
            section_index=target.section_index,
            table_index=target.table_index,
            row=target.row,
            col=target.col,
            row_span=target.row_span,
            col_span=target.col_span,
            paragraph_index=target.paragraph_index,
            run_index=target.run_index,
            text_node_index=target.text_node_index,
            expected_raw_text=target.expected_raw_text,
            story_scope=field.story_scope,
        ))
    return tuple(grants)


def authorization_is_current(index: HwpxStructureIndex, grant: T02WriteAuthorization) -> bool:
    """A serialized or edited grant is current only when the index issues the same one."""
    return any(item == grant for item in authorize_t02_writes(index))


def t02_write_authorized(index: HwpxStructureIndex, field: FieldAssessment) -> bool:
    """True when the index itself grants this identity. Caller flags are ignored."""
    if index.analysis_status != "COMPLETE" or field.field_type != "T02" or not field.eligible:
        return False
    if field.table_index is None or field.row is None or field.col is None or not field.field_label:
        return False
    return any(
        grant.field_label == field.field_label
        and grant.section_index == field.section_index
        and grant.table_index == field.table_index
        and grant.row == field.row
        and grant.col == field.col
        and grant.source_sha256 == index.source_sha256
        for grant in authorize_t02_writes(index)
    )
