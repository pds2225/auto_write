"""hangul_default — 자동생성·채움·제출의 사용자 산출은 한글(HWPX).

사용자 원문(2026-08-31): 「지 지금 자동으로 문서 만들면 워드로 만들어지냐
한글로 만들어지냐 한글로 만들어 줘야 돼」

계약
----
- 기본 확장자 = ``.hwpx`` (XML 채움, 한글 COM 불필요).
- ``.docx`` 는 사용자가 명시할 때만 (``-o *.docx`` / ``--required-format docx`` /
  ``--engine docx-crossform``).
- 이진 ``.hwp`` 저장은 Windows+한글 COM 전용. COM 없으면 HWPX XML 로 저장하고
  notes 에 정직히 남긴다.
- 원본 덮어쓰기 금지. L014 생성표 서식은 폼 채움 표에 쓰지 않는다.
- L050 PDF 쌍 생성은 여기서 하지 않는다(rhwp/한글 없으면 BLOCKED 유지).
"""

from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

DEFAULT_AUTO_CREATE_EXT = ".hwpx"
HANGUL_EXTS = {".hwpx", ".hwp"}
DOCX_EXTS = {".docx", ".doc"}

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_MIMETYPE = b"application/hwp+zip"


@dataclass
class HangulEmitReport:
    ok: bool = False
    method: str = ""  # copy | hancom_com | xml_wrap
    output: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "method": self.method,
            "output": self.output,
            "notes": list(self.notes),
        }


def normalize_format(name: str | None) -> str:
    return (name or "").strip().lower().lstrip(".")


def is_hangul_ext(path: str | Path) -> bool:
    return Path(path).suffix.lower() in HANGUL_EXTS


def is_docx_ext(path: str | Path) -> bool:
    return Path(path).suffix.lower() in DOCX_EXTS


def is_explicit_docx(
    *,
    requested_format: str | None = None,
    output_path: str | Path | None = None,
) -> bool:
    """사용자가 워드를 직접 지정했는지. 기본 경로 추론은 해당 없음."""
    if normalize_format(requested_format) in {"docx", "doc"}:
        return True
    if output_path is not None and Path(output_path).suffix.lower() in DOCX_EXTS:
        return True
    return False


def default_user_facing_suffix(
    *,
    requested_format: str | None = None,
    output_path: str | Path | None = None,
) -> str:
    """자동생성/채움/제출의 사용자 산출 확장자. 기본 .hwpx."""
    if is_explicit_docx(requested_format=requested_format, output_path=output_path):
        return ".docx"
    if output_path is not None:
        ext = Path(output_path).suffix.lower()
        if ext in HANGUL_EXTS:
            return ext
    req = normalize_format(requested_format)
    if req == "hwp":
        return ".hwp"
    if req == "hwpx":
        return ".hwpx"
    return DEFAULT_AUTO_CREATE_EXT


def default_auto_create_path(
    stem: str,
    directory: str | Path,
    *,
    kind: str = "bizplan",
    requested_format: str | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """미지정 출력 경로. kind 예: bizplan → {stem}_bizplan.hwpx."""
    if output_path:
        return Path(output_path)
    ext = default_user_facing_suffix(requested_format=requested_format)
    suffix = f"_{kind}" if kind else ""
    return Path(directory) / f"{stem}{suffix}{ext}"


def default_fill_output(src: str | Path, output: str | Path | None = None) -> Path:
    """채움 CLI 기본 출력. 입력 한글 확장자를 유지하고, 없으면 .hwpx."""
    src_p = Path(src)
    if output:
        return Path(output)
    ext = src_p.suffix.lower() if src_p.suffix.lower() in HANGUL_EXTS else DEFAULT_AUTO_CREATE_EXT
    return src_p.with_name(f"{src_p.stem}_제출{ext}")


def is_hangul_default_combo(outputs: list[str] | None, engine: str | None) -> bool:
    """허브/파이프라인 한글 기본: rhwp-hwpx-fill + hwpx 만."""
    outs = [normalize_format(x) for x in (outputs or ["hwpx"])]
    eng = (engine or "rhwp-hwpx-fill").strip().lower()
    return eng == "rhwp-hwpx-fill" and outs == ["hwpx"]


def emit_hangul_file(
    source: str | Path,
    dest: str | Path,
) -> HangulEmitReport:
    """사용자 산출 한글 파일을 만든다. 원본은 수정하지 않는다.

    - 입력이 .hwpx/.hwp 이고 출력이 같은 계열이면 복사.
    - 입력이 .docx 이면 COM ``docx_to_hwp`` 를 먼저 시도하고, 없으면 XML HWPX 래핑.
    - 출력이 .hwp 인데 COM 이 없으면 .hwpx 로 저장하고 notes 에 Windows-only 를 남긴다.
    """
    src = Path(source)
    dst = Path(dest)
    report = HangulEmitReport(output=str(dst))
    if not src.is_file():
        report.notes.append(f"입력이 없습니다: {src}")
        return report
    if src.resolve() == dst.resolve():
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    dst.parent.mkdir(parents=True, exist_ok=True)

    src_ext = src.suffix.lower()
    dst_ext = dst.suffix.lower()

    if src_ext in HANGUL_EXTS and dst_ext in HANGUL_EXTS:
        shutil.copy2(src, dst)
        report.ok = True
        report.method = "copy"
        return report

    if src_ext not in DOCX_EXTS:
        report.notes.append(f"한글 산출로 바꿀 수 없는 입력 확장자: {src.name}")
        return report

    from .hwp_docx_convert import docx_to_hwp, hancom_com_available

    want_hwp = dst_ext == ".hwp"
    if want_hwp and not hancom_com_available():
        dst = dst.with_suffix(DEFAULT_AUTO_CREATE_EXT)
        report.output = str(dst)
        report.notes.append(
            "이진 .hwp 저장은 Windows+한글 COM 전용입니다. HWPX(XML)로 저장합니다."
        )
        dst_ext = DEFAULT_AUTO_CREATE_EXT

    if dst_ext in HANGUL_EXTS and hancom_com_available():
        conv = docx_to_hwp(src, dst)
        report.notes.extend(conv.notes)
        if conv.ok and dst.is_file() and dst.stat().st_size > 0:
            report.ok = True
            report.method = "hancom_com"
            report.output = str(dst)
            return report
        report.notes.append("한글 COM 변환 실패 — XML HWPX로 폴백합니다.")

    xml_dst = dst if dst.suffix.lower() == ".hwpx" else dst.with_suffix(".hwpx")
    if src.resolve() == xml_dst.resolve():
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    write_docx_as_hwpx_xml(src, xml_dst)
    report.ok = xml_dst.is_file() and xml_dst.stat().st_size > 0
    report.method = "xml_wrap"
    report.output = str(xml_dst)
    if report.ok:
        report.notes.append(
            "XML HWPX(COM 없음). 서식은 단순 문단·표. 원본 양식이 HWPX면 그 파일을 직접 채우는 것이 정본."
        )
    else:
        report.notes.append("XML HWPX 쓰기에 실패했습니다.")
    return report


def write_docx_as_hwpx_xml(docx_path: str | Path, dest: str | Path) -> None:
    """DOCX 본문·표를 최소 OWPML HWPX ZIP 으로 감싼다. L014 생성표 서식은 호출하지 않는다."""
    paragraphs, tables = _docx_blocks(Path(docx_path))
    write_text_hwpx(Path(dest), paragraphs, tables=tables)


def write_text_hwpx(
    dest: str | Path,
    paragraphs: list[str],
    *,
    tables: list[list[list[str]]] | None = None,
) -> None:
    """최소 유효 HWPX(ZIP: mimetype 선두 STORED). 한글 COM 불필요."""
    dest_p = Path(dest)
    dest_p.parent.mkdir(parents=True, exist_ok=True)
    body = _section_xml(paragraphs, tables or [])
    prv = "\n".join(paragraphs[:40])
    data = {
        "mimetype": _MIMETYPE,
        "version.xml": (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" tag="5.0.1.0"/>'
        ),
        "META-INF/container.xml": (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
            b"<rootfiles>"
            b'<rootfile full-path="Contents/content.hpf" media-type="application/hwpml-package+xml"/>'
            b"</rootfiles></container>"
        ),
        "Contents/content.hpf": _content_hpf(),
        "Contents/header.xml": _header_xml(),
        "Contents/section0.xml": body,
        "Preview/PrvText.txt": prv.encode("utf-8"),
    }
    tmp = dest_p.with_suffix(dest_p.suffix + ".part")
    try:
        _write_hwpx_zip(tmp, data)
        os.replace(tmp, dest_p)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def _write_hwpx_zip(path: Path, data: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, data["mimetype"])
        for name, blob in data.items():
            if name == "mimetype":
                continue
            z.writestr(name, blob)


def _content_hpf() -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<opf:package xmlns:opf="http://www.hancom.co.kr/hwpml/2011/opf">'
        "<opf:metadata/>"
        "<opf:manifest>"
        '<opf:item id="header" href="header.xml" media-type="application/xml"/>'
        '<opf:item id="section0" href="section0.xml" media-type="application/xml"/>'
        "</opf:manifest>"
        '<opf:spine><opf:itemref idref="section0"/></opf:spine>'
        "</opf:package>"
    ).encode("utf-8")


def _header_xml() -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">'
        '<hh:refList><hh:charProperties count="1">'
        '<hh:charPr id="0" height="1000" textColor="#000000"/>'
        "</hh:charProperties></hh:refList></hh:head>"
    ).encode("utf-8")


def _section_xml(paragraphs: list[str], tables: list[list[list[str]]]) -> bytes:
    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">',
    ]
    texts = [p for p in paragraphs if str(p).strip()]
    if not texts and not tables:
        texts = [""]
    for para in texts:
        parts.append(_para_xml(para))
    for table in tables:
        parts.append(_table_xml(table))
    parts.append("</hs:sec>")
    return "".join(parts).encode("utf-8")


def _para_xml(text: str) -> str:
    return (
        '<hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{escape(text)}</hp:t>"
        "</hp:run></hp:p>"
    )


def _table_xml(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    col_cnt = max(len(r) for r in rows)
    row_cnt = len(rows)
    trs: list[str] = []
    for r_i, row in enumerate(rows):
        cells: list[str] = []
        padded = list(row) + [""] * (col_cnt - len(row))
        for c_i, val in enumerate(padded):
            cells.append(
                "<hp:tc>"
                f'<hp:cellAddr colAddr="{c_i}" rowAddr="{r_i}"/>'
                '<hp:cellSpan colSpan="1" rowSpan="1"/>'
                "<hp:subList><hp:p><hp:run charPrIDRef=\"0\">"
                f"<hp:t>{escape(val)}</hp:t>"
                "</hp:run></hp:p></hp:subList></hp:tc>"
            )
        trs.append("<hp:tr>" + "".join(cells) + "</hp:tr>")
    inner = "".join(trs)
    return (
        "<hp:p><hp:run charPrIDRef=\"0\">"
        f'<hp:tbl rowCnt="{row_cnt}" colCnt="{col_cnt}">{inner}</hp:tbl>'
        "</hp:run></hp:p>"
    )


def _docx_blocks(path: Path) -> tuple[list[str], list[list[list[str]]]]:
    """본문 순서를 최대한 유지해 문단·표를 뽑는다. python-docx 표 스타일 함수는 쓰지 않는다."""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    paragraphs: list[str] = []
    tables: list[list[list[str]]] = []
    body = doc.element.body
    for child in body:
        tag = child.tag
        if tag == qn("w:p"):
            para = Paragraph(child, doc)
            text = (para.text or "").strip()
            if text:
                paragraphs.append(text)
        elif tag == qn("w:tbl"):
            table = Table(child, doc)
            rows: list[list[str]] = []
            for row in table.rows:
                rows.append([(cell.text or "").replace("\r", "").strip() for cell in row.cells])
            if rows:
                tables.append(rows)
    return paragraphs, tables
