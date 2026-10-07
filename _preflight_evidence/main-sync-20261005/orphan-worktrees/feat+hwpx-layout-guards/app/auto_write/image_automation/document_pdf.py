"""입력 문서를 NotebookLM 업로드용 정규화 PDF로 변환·검증."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from auto_write.image_automation.paths import sha256_file


@dataclass(frozen=True)
class NormalizedPdf:
    path: Path
    sha256: str
    page_count: int
    source_kind: str


def _pdf_page_count(pdf_path: Path) -> int:
    import fitz

    doc = fitz.open(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


def validate_pdf(pdf_path: Path) -> int:
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF 없음: {pdf_path}")
    if pdf_path.stat().st_size <= 0:
        raise ValueError("PDF 파일이 비어 있습니다.")
    pages = _pdf_page_count(pdf_path)
    if pages <= 0:
        raise ValueError("PDF 페이지 수가 0입니다.")
    return pages


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> Path:
    docx_path = Path(docx_path).resolve()
    pdf_path = Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("DOCX→PDF 에 Word COM(pywin32)이 필요합니다.") from exc

    word = None
    doc = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(docx_path))
        # 17 = wdFormatPDF
        doc.SaveAs(str(pdf_path), FileFormat=17)
    except Exception as exc:
        raise RuntimeError(
            f"DOCX→PDF 변환 실패. 수동으로 PDF를 만들어 --input 에 지정하세요: {exc}"
        ) from exc
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
    validate_pdf(pdf_path)
    return pdf_path


def convert_hwp_family_to_pdf(src: Path, pdf_path: Path) -> Path:
    """rhwp export-pdf <입력> -o <출력>."""
    src = Path(src).resolve()
    pdf_path = Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["rhwp", "export-pdf", str(src), "-o", str(pdf_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise RuntimeError("rhwp 가 PATH에 없습니다. HWP/HWPX→PDF 변환에 필요합니다.") from exc
    if proc.returncode != 0 or not pdf_path.is_file():
        raise RuntimeError(
            f"rhwp export-pdf 실패 (exit={proc.returncode}): {(proc.stderr or proc.stdout)[:400]}"
        )
    validate_pdf(pdf_path)
    return pdf_path


def normalize_to_pdf(input_path: Path, out_dir: Path) -> NormalizedPdf:
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = input_path.suffix.lower()
    dest = out_dir / "normalized.pdf"

    if suffix == ".pdf":
        shutil.copy2(input_path, dest)
        kind = "pdf"
    elif suffix == ".docx":
        convert_docx_to_pdf(input_path, dest)
        kind = "docx"
    elif suffix in {".hwp", ".hwpx"}:
        convert_hwp_family_to_pdf(input_path, dest)
        kind = suffix.lstrip(".")
    else:
        raise ValueError(f"정규화 PDF를 만들 수 없는 형식: {suffix}")

    pages = validate_pdf(dest)
    return NormalizedPdf(path=dest, sha256=sha256_file(dest), page_count=pages, source_kind=kind)
