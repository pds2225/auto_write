"""다운로드 파일 검증: magic/MIME, stale 배제, 페이지/슬라이드 수."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PDF_MAGIC = b"%PDF"
# PPTX = ZIP with [Content_Types].xml — ZIP local file header
ZIP_MAGIC = b"PK\x03\x04"


@dataclass(frozen=True)
class VerifiedDownload:
    path: Path
    kind: str  # pdf | pptx
    page_or_slide_count: int
    size: int


def sniff_kind(path: Path) -> str:
    data = path.read_bytes()[:8]
    if data.startswith(PDF_MAGIC):
        return "pdf"
    if data.startswith(ZIP_MAGIC):
        # confirm pptx via content types if possible
        try:
            import zipfile

            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
            if "[Content_Types].xml" in names and any(n.startswith("ppt/") for n in names):
                return "pptx"
        except Exception:
            pass
        raise ValueError("ZIP이지만 PPTX가 아닙니다.")
    raise ValueError("지원하지 않는 다운로드 magic/MIME 입니다.")


def count_pages_or_slides(path: Path, kind: str) -> int:
    if kind == "pdf":
        import fitz

        doc = fitz.open(path)
        try:
            return doc.page_count
        finally:
            doc.close()
    if kind == "pptx":
        from pptx import Presentation

        return len(Presentation(str(path)).slides)
    raise ValueError(f"unknown kind: {kind}")


def verify_download(
    path: Path,
    *,
    allowed_preexisting: set[Path] | None = None,
) -> VerifiedDownload:
    path = Path(path)
    preexisting = {p.resolve() for p in (allowed_preexisting or set())}
    if path.resolve() in preexisting:
        raise ValueError("stale preexisting file은 채택하지 않습니다.")
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("다운로드 파일이 0 byte 입니다.")
    if path.suffix.lower() == ".crdownload" or path.name.endswith(".crdownload"):
        raise ValueError("다운로드가 아직 완료되지 않았습니다 (.crdownload).")
    kind = sniff_kind(path)
    count = count_pages_or_slides(path, kind)
    if count <= 0:
        raise ValueError("페이지/슬라이드 수가 0입니다.")
    return VerifiedDownload(path=path, kind=kind, page_or_slide_count=count, size=size)


def pick_download_event_file(
    download_path: Path,
    download_dir: Path,
) -> Path:
    """Playwright download event가 준 경로만 채택. 디렉터리 스캔으로 stale을 고르지 않는다."""
    download_path = Path(download_path)
    download_dir = Path(download_dir)
    if download_path.parent.resolve() != download_dir.resolve():
        # allow move into download_dir
        dest = download_dir / download_path.name
        if download_path.is_file() and not dest.exists():
            download_path.replace(dest)
            return dest
    if not download_path.is_file():
        raise FileNotFoundError(f"download event 파일이 없습니다: {download_path}")
    return download_path
