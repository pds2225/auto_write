"""Read-only HWPX adapter for DOCX-oriented analysis engines.

This module extracts paragraph-like text and image counts directly from the HWPX
ZIP/XML package. It never converts HWPX to DOCX and never mutates the source
file, so DOCX analyzers can reuse their decision logic without a round-trip.
"""

from __future__ import annotations

import re
from hashlib import sha256
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from lxml import etree

_SECTION_RE = re.compile(r"^Contents/section(\d+)\.xml$")
_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

# Positive evidence, not a generic "short text looks like a label" heuristic.
# Unknown headings remain visible in ambiguous_regions for explicit review.
_INPUT_LABELS = frozenset(
    re.sub(r"\s+", "", label).casefold()
    for label in (
        "성명", "이름", "소속", "직위", "직급", "연락처", "전화번호", "이메일",
        "주소", "생년월일", "기업명", "회사명", "기관명", "법인명", "팀명",
        "대표자", "대표자명", "사업자등록번호", "법인등록번호", "설립일",
        "과제명", "사업명", "아이템명", "창업 아이템명", "창업아이템 소개",
        "아이템 소개", "사업 개요", "사업 내용", "사업 목적", "사업 목표",
        "배경 및 필요성", "개발 배경 및 필요성", "문제인식", "해결방안",
        "실현가능성", "성장전략", "팀 구성", "팀원 현황 및 역량",
        "목표시장", "목표시장 분석", "창업아이템의 목표시장 분석",
        "목표시장 및 사업화 전략", "현황 및 구체화 방안", "현황 및 실현 방안",
        "창업아이템의 현황 및 실현 방안", "경쟁력 확보 방안", "차별성",
        "ESG 가치 실현 정도 및 경쟁력 확보방안", "비즈니스 모델", "수익모델",
        "사업화 전략", "목표시장 진출 방안", "사업 추진 일정", "추진 일정",
        "자금 소요 및 조달계획", "소요 예산", "기대효과", "주요 경력",
        "수상 이력", "수상이력", "투자유치 사항", "담당 업무", "보유 역량",
    )
)


def _input_label(text: str) -> bool:
    label = re.sub(r"^\s*\d+(?:[-.]\d+)*[.)]?\s*", "", text)
    label = re.sub(r"\s*\((?:Problem|Solution|Scale-up|Team)\)\s*$", "", label, flags=re.I)
    return re.sub(r"\s+", "", label.rstrip(" :：")).casefold() in _INPUT_LABELS


def _children(node, name: str) -> list:
    return list(node.iterchildren(f"{{{_HP}}}{name}"))


def _owner(node, name: str):
    return next((parent for parent in node.iterancestors(f"{{{_HP}}}{name}")), None)


def _owned_paragraphs(cell) -> list:
    return [p for p in cell.iter(f"{{{_HP}}}p") if _owner(p, "tc") is cell]


def _raw_cell_text(cell) -> str:
    return "".join(str(t.text or "") for t in cell.iter(f"{{{_HP}}}t"))


def _placed_cell(cell: dict) -> bool:
    return all(cell[key] is not None for key in ("row", "col", "row_span", "col_span"))


def _table_cells(table) -> list[dict]:
    """Direct cells. Missing cellAddr and span stay null.

    Physical tr/tc order is stored separately and is not used as a logical
    address. This matches index_hwpx_structure.
    """
    rows = _children(table, "tr")
    result = []
    for row_index, row in enumerate(rows):
        for row_cell_index, cell in enumerate(_children(row, "tc")):
            address = next(iter(_children(cell, "cellAddr")), None)
            span = next(iter(_children(cell, "cellSpan")), None)
            logical_row = logical_col = row_span = col_span = None
            try:
                if address is not None and address.get("rowAddr") is not None and address.get("colAddr") is not None:
                    logical_row = int(address.get("rowAddr"))
                    logical_col = int(address.get("colAddr"))
                    if logical_row < 0 or logical_col < 0:
                        logical_row = logical_col = None
                if span is not None and span.get("rowSpan") is not None and span.get("colSpan") is not None:
                    parsed_row_span = int(span.get("rowSpan"))
                    parsed_col_span = int(span.get("colSpan"))
                    if parsed_row_span >= 1 and parsed_col_span >= 1:
                        row_span = parsed_row_span
                        col_span = parsed_col_span
            except (TypeError, ValueError):
                logical_row = logical_col = row_span = col_span = None
            result.append({
                "node": cell, "cell_index": len(result), "row_index": row_index,
                "row_cell_index": row_cell_index, "row": logical_row, "col": logical_col,
                "row_span": row_span, "col_span": col_span, "grid_valid": False,
                "has_address": logical_row is not None and logical_col is not None,
                "text": "\n".join(_paragraph_text(p) for p in _owned_paragraphs(cell)).strip(),
            })

    valid = all(_placed_cell(cell) for cell in result)
    if valid:
        for index, cell in enumerate(result):
            for other in result[:index]:
                if (
                    cell["row"] < other["row"] + other["row_span"]
                    and other["row"] < cell["row"] + cell["row_span"]
                    and cell["col"] < other["col"] + other["col_span"]
                    and other["col"] < cell["col"] + cell["col_span"]
                ):
                    valid = False
    for cell in result:
        cell["grid_valid"] = valid
    return result


def _label_evidence(cell: dict, cells: list[dict], table, paragraph_indexes: dict) -> tuple[str, dict | None]:
    """Use only touching label cells or a heading directly above a one-cell table."""
    candidates = []
    for other in cells:
        if not _input_label(other["text"]) or not _placed_cell(cell) or not _placed_cell(other):
            continue
        left = (other["col"] + other["col_span"] == cell["col"]
                and other["row"] == cell["row"] and other["row_span"] == cell["row_span"])
        above = (other["row"] + other["row_span"] == cell["row"]
                 and other["col"] == cell["col"] and other["col_span"] == cell["col_span"])
        if left or above:
            candidates.append((other["text"], {"kind": "left_cell" if left else "above_cell",
                                               "cell_index": other["cell_index"]}))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return "", {"kind": "conflicting_adjacent_labels", "labels": [c[0] for c in candidates]}
    if len(cells) == 1:
        paragraph = _owner(table, "p")
        previous = paragraph.getprevious() if paragraph is not None else None
        if (paragraph is not None and not _paragraph_text(paragraph)
                and previous is not None and previous.tag == f"{{{_HP}}}p"):
            heading = _paragraph_text(previous)
            if _input_label(heading):
                return heading, {"kind": "preceding_paragraph", "paragraph_index": paragraph_indexes[previous]}
    return "", None


@dataclass(frozen=True)
class HwpxAnalysis:
    paragraphs: tuple[str, ...]
    existing_images: int
    section_count: int

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


def _local_name(tag: object) -> str:
    text = str(tag or "")
    if "}" in text:
        return text.rsplit("}", 1)[-1]
    return text


def _paragraph_text(paragraph) -> str:
    """Return text owned by one hp:p, excluding nested hp:p descendants.

    HWPX tables can live inside an outer paragraph. Without this guard, table
    cell paragraphs are counted once through the outer paragraph and again as
    their own paragraphs.
    """
    parts: list[str] = []

    def walk(node) -> None:
        for child in node:
            name = _local_name(child.tag)
            if name == "p":
                continue
            if name == "t":
                parts.append("".join(child.itertext()))
                continue
            walk(child)

    walk(paragraph)
    return "".join(parts).strip()


def read_hwpx_analysis(path: str | Path) -> HwpxAnalysis:
    """Extract lightweight analysis data directly from an HWPX package."""
    src = Path(path)
    if src.suffix.lower() != ".hwpx":
        raise ValueError(f"HWPX 파일이 아님: {src}")
    if not src.exists():
        raise FileNotFoundError(src)

    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)

    try:
        with ZipFile(src) as archive:
            section_entries: list[tuple[int, str]] = []
            for name in archive.namelist():
                match = _SECTION_RE.match(name)
                if match:
                    section_entries.append((int(match.group(1)), name))
            section_entries.sort()

            if not section_entries:
                raise ValueError("HWPX section XML이 없습니다.")

            paragraphs: list[str] = []
            existing_images = 0
            for _index, name in section_entries:
                root = etree.fromstring(archive.read(name), parser=parser)
                for element in root.iter():
                    local = _local_name(element.tag)
                    if local == "pic":
                        existing_images += 1
                    elif local == "p":
                        text = _paragraph_text(element)
                        if text:
                            paragraphs.append(text)

            return HwpxAnalysis(
                paragraphs=tuple(paragraphs),
                existing_images=existing_images,
                section_count=len(section_entries),
            )
    except BadZipFile as exc:
        raise ValueError(f"유효한 HWPX ZIP이 아님: {src}") from exc


# ---------------------------------------------------------------------------
# Structure index. This is a coordinate contract, not a write permission.
# write_target_candidate from older batch JSON must not be treated as allowed.
# ---------------------------------------------------------------------------

_OPF = "http://www.idpf.org/2007/opf/"
_NOTE_SCOPES = frozenset({"footNote", "endNote"})
_STORY_REGIONS = _NOTE_SCOPES | {"header", "footer", "caption"}
_OBJECT_NAMES = frozenset({
    "pic", "rect", "ellipse", "line", "polygon", "curve", "arc", "chart",
    "equation", "container", "ole", "drawText", "textart",
})


def _parser():
    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, recover=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_t(node) -> str:
    """Text of one hp:t, including tails of its direct children. No stripping."""
    parts = [node.text or ""]
    for child in node:
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _positive_int(value: str | None) -> tuple[int | None, str]:
    if value is None:
        return None, "MISSING"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None, "INVALID"
    if number < 0:
        return None, "INVALID"
    return number, "PRESENT"


def _span_int(value: str | None) -> tuple[int | None, str]:
    if value is None:
        return None, "MISSING"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None, "INVALID"
    if number < 1:
        return None, "INVALID"
    return number, "PRESENT"


@dataclass(frozen=True)
class HwpxTextNode:
    text_node_index: int
    raw_text: str


@dataclass(frozen=True)
class HwpxRunRecord:
    run_index: int
    char_pr_id: str
    raw_text: str
    text_nodes: tuple[HwpxTextNode, ...]
    has_nested_table: bool
    has_non_text_object: bool


@dataclass(frozen=True)
class HwpxParagraphRecord:
    paragraph_index: int
    section_index: int
    section_member: str
    story_scope: str
    table_index: int | None
    physical_tr_index: int | None
    physical_tc_index: int | None
    raw_text: str
    runs: tuple[HwpxRunRecord, ...]


@dataclass(frozen=True)
class HwpxCellRecord:
    physical_tr_index: int
    physical_tc_index: int
    row: int | None
    col: int | None
    row_span: int | None
    col_span: int | None
    address_status: str
    span_status: str
    paragraph_indexes: tuple[int, ...]
    has_nested_table: bool
    has_non_text_object: bool


@dataclass(frozen=True)
class HwpxTableRecord:
    table_index: int
    table_index_in_section: int
    section_index: int
    section_member: str
    story_scope: str
    parent_table_index: int | None
    table_path: tuple[int, ...]
    parent_physical_tr_index: int | None
    parent_physical_tc_index: int | None
    cells: tuple[HwpxCellRecord, ...]
    addresses_overlap: bool


@dataclass(frozen=True)
class HwpxSectionRecord:
    section_index: int
    section_member: str
    paragraphs: tuple[HwpxParagraphRecord, ...]
    table_indexes: tuple[int, ...]


@dataclass(frozen=True)
class HwpxStructureIndex:
    """Read-only coordinate index. It does not grant permission to write."""

    source_path: str
    source_sha256: str
    source_size: int
    analysis_status: str
    section_order_confirmed: bool
    section_order: tuple[str, ...]
    sections: tuple[HwpxSectionRecord, ...]
    tables: tuple[HwpxTableRecord, ...]
    errors: tuple[str, ...]

    @property
    def table_count(self) -> int:
        return len(self.tables)


def _section_order(archive: ZipFile) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    """Return section members in package spine order.

    Filename sorting is not document order. A missing or empty spine does not
    invent an order; the caller marks the index PARTIAL.
    """
    name = "Contents/content.hpf"
    if name not in archive.namelist():
        return (), ("SECTION_ORDER_UNCONFIRMED",), False
    try:
        root = etree.fromstring(archive.read(name), parser=_parser())
    except etree.XMLSyntaxError:
        return (), ("SECTION_ORDER_UNCONFIRMED",), False
    manifest: dict[str, str] = {}
    for element in root.iter():
        if _local_name(element.tag) == "item" and element.get("id") and element.get("href"):
            manifest[element.get("id")] = element.get("href").replace("\\", "/")
    ordered: list[str] = []
    for element in root.iter():
        if _local_name(element.tag) != "itemref" or not element.get("idref"):
            continue
        href = manifest.get(element.get("idref"))
        if href and _SECTION_RE.match(href):
            ordered.append(href)
    if not ordered:
        return (), ("SECTION_ORDER_UNCONFIRMED",), False
    errors: list[str] = []
    if len(ordered) != len(set(ordered)):
        errors.append("DUPLICATE_SECTION_IN_SPINE")
    return tuple(ordered), tuple(errors), not errors


def _rectangles_overlap(cells: list[HwpxCellRecord]) -> bool:
    located = [
        cell for cell in cells
        if cell.address_status == "PRESENT" and cell.span_status == "PRESENT"
        and cell.row is not None and cell.col is not None
        and cell.row_span is not None and cell.col_span is not None
    ]
    for index, cell in enumerate(located):
        for other in located[:index]:
            if (
                cell.row < other.row + other.row_span
                and other.row < cell.row + cell.row_span
                and cell.col < other.col + other.col_span
                and other.col < cell.col + cell.col_span
            ):
                return True
    return False


def _index_section(root, section_index: int, section_member: str, state: dict) -> HwpxSectionRecord:
    paragraphs: list[HwpxParagraphRecord] = []
    table_indexes: list[int] = []

    def index_table(element, scope: str, parent: HwpxTableRecord | None, parent_cell: HwpxCellRecord | None) -> None:
        if parent_cell is not None:
            _mark_nested(parent_cell)
        cells: list[HwpxCellRecord] = []
        record = HwpxTableRecord(
            table_index=state["table_count"],
            table_index_in_section=len(table_indexes),
            section_index=section_index,
            section_member=section_member,
            story_scope=scope,
            parent_table_index=None if parent is None else parent.table_index,
            table_path=(
                () if parent is None else parent.table_path + (parent.table_index,)
            ),
            parent_physical_tr_index=None if parent_cell is None else parent_cell.physical_tr_index,
            parent_physical_tc_index=None if parent_cell is None else parent_cell.physical_tc_index,
            cells=(),
            addresses_overlap=False,
        )
        state["table_count"] += 1
        state["tables"].append(record)
        table_indexes.append(record.table_index)

        def walk(node, scope: str, cell: HwpxCellRecord | None) -> None:
            for child in node:
                name = _local_name(child.tag)
                if not name:
                    continue
                if name == "tbl":
                    index_table(child, scope, record, cell)
                elif name in _STORY_REGIONS:
                    walk(child, name, cell)
                elif name == "p":
                    consume_paragraph(child, scope, cell)
                elif name in _OBJECT_NAMES and cell is not None:
                    _mark_object(cell)
                    walk(child, scope, cell)
                else:
                    walk(child, scope, cell)

        def consume_paragraph(paragraph, scope: str, cell: HwpxCellRecord | None) -> None:
            reserved = len(paragraphs)
            paragraphs.append(None)
            runs: list[HwpxRunRecord] = []
            run_index = 0
            for child in paragraph:
                name = _local_name(child.tag)
                if name == "tbl":
                    index_table(child, scope, record, cell)
                    continue
                if name in _STORY_REGIONS:
                    walk(child, name, cell)
                    continue
                if name != "run":
                    if name in _OBJECT_NAMES and cell is not None:
                        _mark_object(cell)
                    walk(child, scope, cell)
                    continue
                texts: list[HwpxTextNode] = []
                nested = False
                obj = False
                text_index = 0
                for sub in child:
                    sub_name = _local_name(sub.tag)
                    if sub_name == "t":
                        texts.append(HwpxTextNode(text_index, _raw_t(sub)))
                        text_index += 1
                    elif sub_name == "tbl":
                        nested = True
                        index_table(sub, scope, record, cell)
                    elif sub_name in _STORY_REGIONS:
                        walk(sub, sub_name, cell)
                    elif sub_name in _OBJECT_NAMES:
                        obj = True
                        if cell is not None:
                            _mark_object(cell)
                        walk(sub, scope, cell)
                    else:
                        walk(sub, scope, cell)
                runs.append(HwpxRunRecord(
                    run_index=run_index,
                    char_pr_id=child.get("charPrIDRef") or "",
                    raw_text="".join(node.raw_text for node in texts),
                    text_nodes=tuple(texts),
                    has_nested_table=nested,
                    has_non_text_object=obj,
                ))
                run_index += 1
            paragraphs[reserved] = HwpxParagraphRecord(
                paragraph_index=reserved,
                section_index=section_index,
                section_member=section_member,
                story_scope=scope,
                table_index=record.table_index,
                physical_tr_index=None if cell is None else cell.physical_tr_index,
                physical_tc_index=None if cell is None else cell.physical_tc_index,
                raw_text="".join(run.raw_text for run in runs),
                runs=tuple(runs),
            )
            if cell is not None:
                _attach_paragraph(cell, reserved)
                if any(run.has_nested_table for run in runs):
                    _mark_nested(cell)

        row_index = 0
        for child in element:
            name = _local_name(child.tag)
            if name == "caption":
                walk(child, "caption", None)
            elif name == "tr":
                cell_index = 0
                for cell_el in child:
                    if _local_name(cell_el.tag) != "tc":
                        walk(cell_el, scope, None)
                        continue
                    address = next((node for node in cell_el if _local_name(node.tag) == "cellAddr"), None)
                    span = next((node for node in cell_el if _local_name(node.tag) == "cellSpan"), None)
                    row, row_status = _positive_int(None if address is None else address.get("rowAddr"))
                    col, col_status = _positive_int(None if address is None else address.get("colAddr"))
                    row_span, row_span_status = _span_int(None if span is None else span.get("rowSpan"))
                    col_span, col_span_status = _span_int(None if span is None else span.get("colSpan"))
                    address_status = "PRESENT" if row_status == "PRESENT" and col_status == "PRESENT" else (
                        "INVALID" if "INVALID" in {row_status, col_status} else "MISSING"
                    )
                    span_status = "PRESENT" if row_span_status == "PRESENT" and col_span_status == "PRESENT" else (
                        "INVALID" if "INVALID" in {row_span_status, col_span_status} else "MISSING"
                    )
                    if address_status == "INVALID":
                        state["errors"].append(
                            "INVALID_COORDINATE"
                            f" section={section_member} table_index={record.table_index}"
                            f" tr={row_index} tc={cell_index}"
                        )
                    if address_status != "PRESENT":
                        row = None
                        col = None
                    if span_status != "PRESENT":
                        row_span = None
                        col_span = None
                    cell = HwpxCellRecord(
                        physical_tr_index=row_index,
                        physical_tc_index=cell_index,
                        row=row,
                        col=col,
                        row_span=row_span,
                        col_span=col_span,
                        address_status=address_status,
                        span_status=span_status,
                        paragraph_indexes=(),
                        has_nested_table=False,
                        has_non_text_object=False,
                    )
                    cells.append(cell)
                    walk(cell_el, scope, cell)
                    cell_index += 1
                row_index += 1
            elif name == "tbl":
                index_table(child, scope, record, None)
            else:
                walk(child, scope, None)
        overlap = _rectangles_overlap(cells)
        state["tables"][record.table_index] = HwpxTableRecord(
            table_index=record.table_index,
            table_index_in_section=record.table_index_in_section,
            section_index=record.section_index,
            section_member=record.section_member,
            story_scope=record.story_scope,
            parent_table_index=record.parent_table_index,
            table_path=record.table_path,
            parent_physical_tr_index=record.parent_physical_tr_index,
            parent_physical_tc_index=record.parent_physical_tc_index,
            cells=tuple(cells),
            addresses_overlap=overlap,
        )
        if overlap:
            state["errors"].append(
                f"COORDINATE_OVERLAP section={section_member} table_index={record.table_index}"
            )

    def walk(node, scope: str, table: HwpxTableRecord | None, cell: HwpxCellRecord | None) -> None:
        for child in node:
            name = _local_name(child.tag)
            if not name:
                continue
            if name == "tbl":
                index_table(child, scope, table, cell)
            elif name in _STORY_REGIONS:
                walk(child, name, table, cell)
            elif name == "p":
                consume_paragraph_free(child, scope, table, cell)
            elif name in _OBJECT_NAMES and cell is not None:
                _mark_object(cell)
                walk(child, scope, table, cell)
            else:
                walk(child, scope, table, cell)

    def consume_paragraph_free(paragraph, scope: str, table: HwpxTableRecord | None, cell: HwpxCellRecord | None) -> None:
        reserved = len(paragraphs)
        paragraphs.append(None)
        runs: list[HwpxRunRecord] = []
        run_index = 0
        for child in paragraph:
            name = _local_name(child.tag)
            if name == "tbl":
                index_table(child, scope, table, cell)
                continue
            if name in _STORY_REGIONS:
                walk(child, name, table, cell)
                continue
            if name != "run":
                walk(child, scope, table, cell)
                continue
            texts: list[HwpxTextNode] = []
            nested = False
            obj = False
            text_index = 0
            for sub in child:
                sub_name = _local_name(sub.tag)
                if sub_name == "t":
                    texts.append(HwpxTextNode(text_index, _raw_t(sub)))
                    text_index += 1
                elif sub_name == "tbl":
                    nested = True
                    index_table(sub, scope, table, cell)
                elif sub_name in _STORY_REGIONS:
                    walk(sub, sub_name, table, cell)
                else:
                    if sub_name in _OBJECT_NAMES:
                        obj = True
                        if cell is not None:
                            _mark_object(cell)
                    walk(sub, scope, table, cell)
            runs.append(HwpxRunRecord(
                run_index=run_index,
                char_pr_id=child.get("charPrIDRef") or "",
                raw_text="".join(node.raw_text for node in texts),
                text_nodes=tuple(texts),
                has_nested_table=nested,
                has_non_text_object=obj,
            ))
            run_index += 1
        paragraphs[reserved] = HwpxParagraphRecord(
            paragraph_index=reserved,
            section_index=section_index,
            section_member=section_member,
            story_scope=scope,
            table_index=None if table is None else table.table_index,
            physical_tr_index=None if cell is None else cell.physical_tr_index,
            physical_tc_index=None if cell is None else cell.physical_tc_index,
            raw_text="".join(run.raw_text for run in runs),
            runs=tuple(runs),
        )

    # Outside tables, paragraphs are reserved before nested tables so document order matches XML.
    # after both functions exist — they do, because index_table is only invoked
    # from walk/index_table at runtime.
    walk(root, "body", None, None)
    return HwpxSectionRecord(
        section_index=section_index,
        section_member=section_member,
        paragraphs=tuple(paragraphs),
        table_indexes=tuple(table_indexes),
    )


def _mark_object(cell: HwpxCellRecord) -> None:
    object.__setattr__(cell, "has_non_text_object", True)


def _attach_paragraph(cell: HwpxCellRecord, paragraph_index: int) -> None:
    object.__setattr__(cell, "paragraph_indexes", cell.paragraph_indexes + (paragraph_index,))


def _mark_nested(cell: HwpxCellRecord) -> None:
    object.__setattr__(cell, "has_nested_table", True)


def index_hwpx_structure(path: str | Path) -> HwpxStructureIndex:
    """Index section, table, cell, paragraph, run, and text without writing.

    Tables inside captions and other non-cell containers are included.
    Logical row/col come only from cellAddr. Missing addresses stay null.
    Raw text keeps whitespace. This index does not authorize writing.
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(src)
    source_hash = _sha256_file(src)
    source_size = src.stat().st_size
    errors: list[str] = []
    if src.suffix.lower() != ".hwpx":
        return HwpxStructureIndex(
            source_path=str(src), source_sha256=source_hash, source_size=source_size,
            analysis_status="FAILED", section_order_confirmed=False, section_order=(),
            sections=(), tables=(), errors=("NOT_HWPX",),
        )
    try:
        archive = ZipFile(src)
    except BadZipFile:
        return HwpxStructureIndex(
            source_path=str(src), source_sha256=source_hash, source_size=source_size,
            analysis_status="FAILED", section_order_confirmed=False, section_order=(),
            sections=(), tables=(), errors=("NOT_ZIP",),
        )
    with archive:
        ordered, order_errors, confirmed = _section_order(archive)
        errors.extend(order_errors)
        discovered = [name for name in archive.namelist() if _SECTION_RE.match(name)]
        if len(discovered) != len(set(discovered)):
            errors.append("DUPLICATE_PACKAGE_ENTRY")
        if not ordered:
            # Do not pretend filename order is package order.
            ordered = tuple(discovered)
        else:
            missing = [name for name in discovered if name not in ordered]
            if missing:
                errors.append("SECTION_NOT_IN_SPINE")
                ordered = ordered + tuple(missing)
        if not ordered:
            errors.append("NO_SECTION_XML")
            return HwpxStructureIndex(
                source_path=str(src), source_sha256=source_hash, source_size=source_size,
                analysis_status="FAILED", section_order_confirmed=False,
                section_order=(), sections=(), tables=(), errors=tuple(errors),
            )
        state = {"table_count": 0, "tables": [], "errors": errors}
        sections: list[HwpxSectionRecord] = []
        parsed = 0
        for section_index, member in enumerate(ordered):
            if member not in archive.namelist():
                errors.append(f"SECTION_MISSING:{member}")
                continue
            try:
                root = etree.fromstring(archive.read(member), parser=_parser())
            except etree.XMLSyntaxError:
                errors.append(f"XML_PARSE_ERROR:{member}")
                continue
            parsed += 1
            sections.append(_index_section(root, section_index, member, state))
        status = "COMPLETE" if parsed == len(ordered) and confirmed and not errors else (
            "FAILED" if parsed == 0 else "PARTIAL"
        )
        if _sha256_file(src) != source_hash:
            errors.append("SOURCE_CHANGED")
            status = "FAILED"
        return HwpxStructureIndex(
            source_path=str(src),
            source_sha256=source_hash,
            source_size=source_size,
            analysis_status=status,
            section_order_confirmed=confirmed and "SECTION_NOT_IN_SPINE" not in errors,
            section_order=tuple(ordered),
            sections=tuple(sections),
            tables=tuple(state["tables"]),
            errors=tuple(errors),
        )
