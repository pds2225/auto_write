"""AW-009 P0: inspect original materials and assemble a section-scoped approval plan.

This module never generates a document. Upload and planning must not invoke an engine.
Files are stored outside the repository. No fabricated page numbers or citations.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from docx import Document
from lxml import etree

from ..document_ingest import extract_hwp_preview_text

ROOT = Path(tempfile.gettempdir()) / "aw009_p0_workspaces"
LIMIT_BYTES = 20 * 1024 * 1024
_HEADING = re.compile(r"^\s*(?:\d{1,2}(?:[.-]\d{1,2}){0,2}[.)]?\s+|[ⅠⅡⅢⅣⅤ][. ]\s*)(.{2,95})$")
_KEYWORD = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_MAJOR_TOC = re.compile(r"^\s*(?:\d{1,2}[.)]\s+|[ⅠⅡⅢⅣⅤ][. ]\s*)")
_FORMATS = {".docx", ".hwpx", ".hwp", ".pdf", ".txt", ".md"}


def _base(workspace_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", workspace_id or ""):
        raise ValueError("올바르지 않은 작업 ID입니다.")
    return ROOT / workspace_id


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _local(tag: Any) -> str:
    value = str(tag)
    return value.rsplit("}", 1)[-1]


def _elements(name: str, data: bytes) -> list[dict[str, Any]]:
    suffix = Path(name).suffix.lower()
    if suffix not in _FORMATS:
        raise ValueError(f"지원하지 않는 파일 형식: {suffix}")
    rows: list[dict[str, Any]] = []

    def add(text: str, locator: dict[str, Any], *, heading: bool = False, page: int | None = None):
        text = " ".join(str(text or "").split()).strip()
        if text:
            rows.append({"text": text[:3500], "locator": locator,
                         "heading": heading, "page": page})

    if suffix == ".docx":
        doc = Document(io.BytesIO(data))
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        pi = ti = 0
        # Preserve document order: paragraphs and tables may be interleaved.
        for element in doc.element.body.iterchildren():
            if _local(element.tag) == "p":
                paragraph = Paragraph(element, doc)
                style = str(getattr(paragraph.style, "name", "") or "").lower()
                add(paragraph.text, {"format": "docx", "paragraph": pi},
                    heading=style in {"heading 1", "제목 1"})
                pi += 1
            elif _local(element.tag) == "tbl":
                table = Table(element, doc)
                seen_cells = set()
                for ri, row in enumerate(table.rows):
                    for ci, cell in enumerate(row.cells):
                        # Merged cells have the same underlying XML node.
                        identity = id(cell._tc)
                        if identity in seen_cells:
                            continue
                        seen_cells.add(identity)
                        add(cell.text, {"format": "docx", "table": ti, "row": ri, "cell": ci})
                ti += 1
    elif suffix == ".hwpx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            sections = sorted((n for n in archive.namelist()
                               if re.fullmatch(r"Contents/section\d+\.xml", n, re.I)),
                              key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
            for s in sections:
                root = etree.fromstring(archive.read(s))
                paragraphs = [p for p in root.iter() if _local(p.tag) == "p"]
                for pi, paragraph in enumerate(paragraphs):
                    # A table-cell paragraph carries its own location; no fake page index.
                    cell = next((a for a in paragraph.iterancestors()
                                 if _local(a.tag) == "tc"), None)
                    locator = {"format": "hwpx", "section": s, "paragraph": pi}
                    if cell is not None:
                        locator["cell"] = True
                    parts = [e.text or "" for e in paragraph.iter() if _local(e.tag) == "t"]
                    add("".join(parts), locator)
    elif suffix == ".pdf":
        import fitz
        with fitz.open(stream=data, filetype="pdf") as pdf:
            for page_index, page in enumerate(pdf):
                for bi, block in enumerate(page.get_text("blocks")):
                    if len(block) > 4:
                        add(block[4], {"format": "pdf", "page": page_index + 1,
                                       "block": bi, "bbox": list(block[:4])},
                            page=page_index + 1)
    elif suffix == ".hwp":
        # HWP preview has no proven page/paragraph locator; label it honestly.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.hwp"
            path.write_bytes(data)
            text = extract_hwp_preview_text(path)
        if not text:
            raise ValueError("HWP 원문 추출 불가. HWPX로 저장 후 첨부해야 합니다.")
        for i, line in enumerate(text.splitlines()):
            add(line, {"format": "hwp_preview", "line": i, "precise": False})
    else:
        text = data.decode("utf-8-sig")
        for i, line in enumerate(text.splitlines()):
            add(line, {"format": "text", "line": i + 1})
    return rows


def _name_heading(text: str, explicit: bool) -> bool:
    return explicit or (bool(_HEADING.match(text)) and len(text) <= 110)


def _toc(rows: list[dict[str, Any]], override: str = "") -> list[dict[str, str]]:
    names = [x.strip() for x in override.splitlines() if x.strip()] if override.strip() else [
        r["text"] for r in rows if (r["heading"] or _MAJOR_TOC.match(r["text"]))
    ]
    ordered: list[str] = []
    for name in names:
        if name not in ordered:
            ordered.append(name)
    if not ordered:
        raise ValueError("양식 대목차를 확인할 수 없습니다. 실제 대목차를 직접 입력해주세요.")
    return [{"id": f"section-{i+1}", "title": name} for i, name in enumerate(ordered[:40])]


def _materials(name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Group source text under semantic headings; retain every block's locator.
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in rows:
        heading = _name_heading(row["text"], row["heading"])
        if current is None or heading:
            current = {"id": f"m-{len(groups)+1}", "name": row["text"][:100] if heading
                       else f"{name} · 모듈 {len(groups)+1}", "source_file": name,
                       "blocks": []}
            groups.append(current)
        block = dict(row)
        block["id"] = f"{current['id']}-b{len(current['blocks'])+1}"
        current["blocks"].append(block)
    for group in groups:
        group["preview"] = " ".join(b["text"] for b in group["blocks"])[:360]
        pages = sorted({b["page"] for b in group["blocks"] if b["page"] is not None})
        group["source_pages"] = pages
        group["psst_tag"] = None  # Only an optional display tag, never the final TOC.
    return groups[:200]


def start(announcement: tuple[str, bytes] | None,
          template: tuple[str, bytes], references: list[tuple[str, bytes]],
          *, combined: bool = False, toc_override: str = "",
          roles_confirmed: bool = False) -> dict[str, Any]:
    if not roles_confirmed or not template[1] or (not announcement and not combined):
        raise ValueError("공고·양식 역할을 사람이 확인해야 합니다. 공고와 양식은 필수입니다.")
    files = [template, *references]
    if announcement:
        files.append(announcement)
    if len(files) > 22:
        raise ValueError("한 작업에 최대 22개 파일까지 허용합니다.")
    for name, data in files:
        if len(data) > LIMIT_BYTES or not data:
            raise ValueError(f"파일이 비어 있거나 20MB를 초과합니다: {name}")
    toc = _toc(_elements(*template), toc_override)
    materials: list[dict[str, Any]] = []
    for name, data in references:
        for module in _materials(name, _elements(name, data)):
            for block in module["blocks"]:
                block["id"] = f"b-{len(materials)+1}-{block['id']}"
            module["id"] = f"module-{len(materials)+1}"
            materials.append(module)
    workspace_id = secrets.token_hex(16)
    folder = _base(workspace_id)
    folder.mkdir(parents=True, exist_ok=False)
    inventory = []
    for index, (name, data) in enumerate(files):
        suffix = Path(name).suffix.lower()
        saved = f"input-{index}{suffix}"
        (folder / saved).write_bytes(data)
        inventory.append({"filename": name, "stored": saved, "sha256": hashlib.sha256(data).hexdigest()})
    state = {"id": workspace_id, "status": "WAITING_PLAN", "toc": toc,
             "modules": materials, "inputs": inventory, "template_file": inventory[0],
             "announcement_file": inventory[-1] if announcement else inventory[0],
             "roles_confirmed": True, "combined": combined, "approved": False}
    _write_json(folder / "state.json", state)
    return state


def get(workspace_id: str) -> dict[str, Any]:
    return _read_json(_base(workspace_id) / "state.json")


def plan(workspace_id: str, section_id: str, selected_block_ids: list[str],
         instruction: str) -> dict[str, Any]:
    state = get(workspace_id)
    if state["status"] not in {"WAITING_PLAN", "PLAN_READY"}:
        raise ValueError("이미 승인되거나 실행 중인 작업은 수정할 수 없습니다.")
    if not any(x["id"] == section_id for x in state["toc"]):
        raise ValueError("양식에 없는 대목차입니다.")
    blocks = {b["id"]: (m, b) for m in state["modules"] for b in m["blocks"]}
    if len(selected_block_ids) != len(set(selected_block_ids)):
        raise ValueError("중복 선택된 원문 재료가 있습니다.")
    if any(x not in blocks for x in selected_block_ids):
        raise ValueError("실제 자료에 없는 선택 재료가 있습니다.")
    chosen = [{"id": k, "module": blocks[k][0]["name"], "text": blocks[k][1]["text"],
               "source_file": blocks[k][0]["source_file"],
               "page": blocks[k][1]["page"], "locator": blocks[k][1]["locator"]}
              for k in selected_block_ids]
    # Interpret only explicit, unambiguous number directives. Unknown text is
    # displayed rather than silently reworded into an authoritative AI decision.
    actions = []
    segments = {
        int(n): value.strip()
        for n, value in re.findall(
            r"\[(\d+)\]([^\[]*)(?=\[\d+\]|$)", instruction.strip()
        )
    }
    for i, item in enumerate(chosen, 1):
        phrase = segments.get(i, "")
        action = "지시 불명확 — 승인 전 확인"
        if re.search(r"그대로|원문 유지|수정하지", phrase):
            action = "원문 그대로"
        elif re.search(r"추가|삽입|넣어", phrase):
            action = "해당 파트에 추가"
        elif re.search(r"수정|보완|재작성", phrase):
            action = "해당 파트에서 보완"
        elif not instruction.strip():
            action = "선택 원문 활용"
        actions.append({"material_id": item["id"], "number": i, "action": action,
                        "original": item["text"][:220]})
    result = {"target_section": section_id, "selected_material_ids": selected_block_ids,
              "user_instruction": instruction.strip(),
              "ai_interpreted_actions": actions,
              "fill_rank": ["transcript", "similar", "generated"],
              "applicable_l_rules": [], "source_locators": [
                  {"material_id": x["id"], "source_file": x["source_file"],
                   "page": x["page"], "locator": x["locator"]} for x in chosen],
              "user_locked_ranges": [], "psst_tag": None,
              "selected_materials": chosen, "approved": False,
              "generation_label_required": not bool(chosen)}
    state["plan"] = result
    state["status"] = "PLAN_READY"
    _write_json(_base(workspace_id) / "state.json", state)
    return result


def approve(workspace_id: str) -> dict[str, Any]:
    state = get(workspace_id)
    if state["status"] != "PLAN_READY":
        raise ValueError("Composition Plan이 생성되어야 승인할 수 있습니다.")
    state["approved"] = True
    state["status"] = "APPROVED"
    state["plan"]["approved"] = True
    _write_json(_base(workspace_id) / "state.json", state)
    return state


def record_execution(workspace_id: str, status: str, **details: Any) -> None:
    state = get(workspace_id)
    if not state["approved"]:
        raise ValueError("승인 전 문서 작성은 금지입니다.")
    state["status"] = status
    state["execution"] = details
    _write_json(_base(workspace_id) / "state.json", state)
