"""PDF/PPTX → 1페이지(슬라이드)당 PNG 1개 분리."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_write.image_automation.models import VisualAsset
from auto_write.image_automation.paths import sha256_file


@dataclass(frozen=True)
class SlideExtractResult:
    assets: list[VisualAsset]
    page_count: int
    reused: bool
    dpi: int
    input_sha256: str
    render_config: dict[str, Any]


def _slide_name(index: int) -> str:
    return f"slide-{index:03d}.png"


def _manifest_path(out_dir: Path) -> Path:
    return out_dir / "slides_manifest.json"


def _load_existing(out_dir: Path, input_sha256: str, dpi: int) -> SlideExtractResult | None:
    path = _manifest_path(out_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("input_sha256") != input_sha256 or int(data.get("dpi", 0)) != dpi:
        return None
    assets: list[VisualAsset] = []
    for item in data.get("assets", []):
        rel = item["path_rel"]
        full = out_dir / Path(rel).name
        if not full.is_file() or sha256_file(full) != item["sha256"]:
            return None
        assets.append(VisualAsset(**item))
    if len(assets) != int(data.get("page_count", -1)):
        return None
    return SlideExtractResult(
        assets=assets,
        page_count=len(assets),
        reused=True,
        dpi=dpi,
        input_sha256=input_sha256,
        render_config={"dpi": dpi},
    )


def _write_manifest(out_dir: Path, result: SlideExtractResult) -> None:
    payload = {
        "input_sha256": result.input_sha256,
        "dpi": result.dpi,
        "page_count": result.page_count,
        "assets": [a.model_dump() for a in result.assets],
        "render_config": result.render_config,
    }
    _manifest_path(out_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_pdf_to_pngs(
    pdf_path: Path,
    out_dir: Path,
    *,
    dpi: int = 144,
) -> SlideExtractResult:
    """PyMuPDF로 PDF 각 페이지를 PNG로 렌더. 동일 hash+dpi면 재사용."""
    import fitz  # PyMuPDF

    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    input_sha = sha256_file(pdf_path)
    existing = _load_existing(out_dir, input_sha, dpi)
    if existing is not None:
        return existing

    doc = fitz.open(pdf_path)
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        assets: list[VisualAsset] = []
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            name = _slide_name(i)
            dest = out_dir / name
            pix.save(str(dest))
            digest = sha256_file(dest)
            assets.append(
                VisualAsset(
                    asset_id=f"slide-{digest[:12]}",
                    source_kind="slide",
                    slide_index=i,
                    path_rel=name,
                    sha256=digest,
                    width=pix.width,
                    height=pix.height,
                    dpi=dpi,
                )
            )
    finally:
        doc.close()

    result = SlideExtractResult(
        assets=assets,
        page_count=len(assets),
        reused=False,
        dpi=dpi,
        input_sha256=input_sha,
        render_config={"dpi": dpi},
    )
    _write_manifest(out_dir, result)
    return result


def convert_pptx_to_pdf(pptx_path: Path, pdf_path: Path) -> Path:
    """Windows PowerPoint COM으로 PPTX→PDF. 불가 시 RuntimeError."""
    pptx_path = Path(pptx_path).resolve()
    pdf_path = Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PowerPoint COM 변환에 pywin32(win32com)가 필요합니다.") from exc

    powerpoint = None
    presentation = None
    try:
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        powerpoint.Visible = 1
        presentation = powerpoint.Presentations.Open(str(pptx_path), WithWindow=False)
        # 32 = ppSaveAsPDF
        presentation.SaveAs(str(pdf_path), 32)
    except Exception as exc:
        raise RuntimeError(f"PPTX→PDF COM 변환 실패: {exc}") from exc
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if powerpoint is not None:
            try:
                powerpoint.Quit()
            except Exception:
                pass
    if not pdf_path.is_file() or pdf_path.stat().st_size <= 0:
        raise RuntimeError("PPTX→PDF 변환 산출물이 비어 있습니다.")
    return pdf_path


def pptx_slide_count(pptx_path: Path) -> int:
    from pptx import Presentation

    return len(Presentation(str(pptx_path)).slides)


def extract_slides(
    input_path: Path,
    out_dir: Path,
    *,
    dpi: int = 144,
    work_dir: Path | None = None,
) -> SlideExtractResult:
    """PDF 또는 PPTX를 슬라이드 PNG로 분리."""
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_to_pngs(input_path, out_dir, dpi=dpi)
    if suffix == ".pptx":
        work = Path(work_dir) if work_dir else out_dir
        work.mkdir(parents=True, exist_ok=True)
        pdf_tmp = work / "converted_from_pptx.pdf"
        convert_pptx_to_pdf(input_path, pdf_tmp)
        result = extract_pdf_to_pngs(pdf_tmp, out_dir, dpi=dpi)
        expected = pptx_slide_count(input_path)
        if result.page_count != expected:
            raise RuntimeError(
                f"PPTX 슬라이드 수({expected})와 PNG 수({result.page_count})가 일치하지 않습니다."
            )
        return result
    raise ValueError(f"지원하지 않는 입력 형식: {suffix}")
