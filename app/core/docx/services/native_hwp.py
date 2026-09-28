"""Native HWP/HWPX I/O. Never calls Hancom COM or a DOCX converter.

RHWP_EXE selects a locally installed rhwp executable. Rendering success is
separate from visual approval: a readable PDF alone cannot authorize FINAL.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def file_sha256(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _rhwp_json(*args: str, timeout: int = 60) -> dict[str, Any]:
    executable = os.environ.get("RHWP_EXE") or shutil.which("rhwp")
    if not executable or not Path(executable).is_file():
        raise FileNotFoundError("rhwp 미설치: RHWP_EXE에 실행 파일 경로를 지정하세요.")
    proc = subprocess.run(
        [executable, *args, "--json"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode:
        raise ValueError(f"rhwp {args[0]} 실패(exit {proc.returncode}): {proc.stderr[-1200:]}")
    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict):
        raise ValueError("rhwp 결과가 JSON 객체가 아닙니다.")
    return payload


def prepare_native_source(source: str | Path, output: str | Path) -> tuple[Path, dict[str, Any]]:
    """Parse HWP natively and verify the HWPX working copy before using it."""
    src, dst = Path(source), Path(output)
    original_hash = file_sha256(src)
    if src.suffix.lower() == ".hwpx":
        return src, {"source_sha256": original_hash, "conversion": "NOT_NEEDED"}
    if src.suffix.lower() != ".hwp" or dst.suffix.lower() != ".hwpx":
        raise ValueError("HWP 입력과 HWPX 출력 경로가 필요합니다.")
    if src.resolve() == dst.resolve() or (dst.exists() and os.path.samefile(src, dst)):
        raise ValueError("원본 덮어쓰기는 금지입니다.")
    if dst.exists():
        raise FileExistsError(dst)
    before = _rhwp_json("info", str(src.resolve()))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-convert-", dir=dst.parent) as folder:
        candidate = Path(folder) / "candidate.hwpx"
        conversion = _rhwp_json(
            "export-hwpx", str(src.resolve()), str(candidate.resolve()),
            "--verify", "--verify-pages",
        )
        if (conversion.get("verify", {}).get("identical") is not True
                or conversion.get("verifyPages", {}).get("identical") is not True):
            raise ValueError("HWP→HWPX 구조/쪽수 보존 검증 미통과")
        reopened = _rhwp_json("info", str(candidate.resolve()))
        if reopened.get("format") != "hwpx" or reopened.get("pageCount") != before.get("pageCount"):
            raise ValueError("변환 HWPX 재열기 또는 쪽수 검증 실패")
        if file_sha256(src) != original_hash:
            raise ValueError("변환 중 원본 변경 감지")
        # Copy only the verified candidate, retaining the immutable HWP upload.
        with candidate.open("rb") as incoming, dst.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    return dst, {"source_sha256": original_hash, "working_sha256": file_sha256(dst),
                 "conversion": "VERIFIED", "source_info": before,
                 "verify": conversion["verify"], "verify_pages": conversion["verifyPages"]}


def verify_hwpx_native(path: str | Path) -> dict[str, Any]:
    """Reopen and render the exact candidate; never use a stale sibling PDF."""
    candidate = Path(path)
    evidence: dict[str, Any] = {
        "ok": False, "severity": "REVIEW_REQUIRED", "renderer": "rhwp",
        "render_status": "NOT_RUN", "reopen_status": "NOT_RUN",
        "visual_review": "NOT_RUN", "pdf": "", "page_count": 0,
    }
    try:
        if candidate.suffix.lower() != ".hwpx":
            raise ValueError("최종 HWPX 파일 자체만 검수할 수 있습니다.")
        expected = file_sha256(candidate)
        evidence["candidate_sha256"] = expected
        reopened = _rhwp_json("info", str(candidate.resolve()))
        pages = reopened.get("pageCount")
        if reopened.get("format") != "hwpx" or not isinstance(pages, int) or pages < 1:
            raise ValueError("HWPX 재열기 결과의 형식/쪽수가 유효하지 않습니다.")
        evidence.update(reopen_status="PASS", page_count=pages)
        # A unique run directory prevents concurrent or previous renders being reused.
        folder = Path(tempfile.mkdtemp(prefix="native-preview-", dir=candidate.parent))
        snapshot = folder / "candidate.hwpx"
        shutil.copyfile(candidate, snapshot)
        if file_sha256(snapshot) != expected:
            raise ValueError("렌더 스냅샷 hash 불일치")
        pdf = folder / "preview.pdf"
        rendered = _rhwp_json("export-pdf", str(snapshot.resolve()), "-o", str(pdf.resolve()))
        from pypdf import PdfReader

        actual_pages = len(PdfReader(str(pdf)).pages)
        if (rendered.get("format") != "pdf" or actual_pages != pages
                or rendered.get("pageCount") != pages or rendered.get("renderedCount") != pages):
            raise ValueError("HWPX 전체 페이지와 렌더 PDF 쪽수가 일치하지 않습니다.")
        if file_sha256(snapshot) != expected or file_sha256(candidate) != expected:
            raise ValueError("검수 도중 후보 파일 변경 감지 — 이전 렌더 무효")
        evidence.update(render_status="PASS", pdf=str(pdf), pdf_sha256=file_sha256(pdf),
                        render_source_sha256=expected, rendered_count=actual_pages,
                        message="HWPX 재열기·전체 쪽 렌더 완료. 실제 페이지 품질 검토가 필요합니다.")
    except FileNotFoundError as exc:
        evidence.update(render_status="UNAVAILABLE", message=str(exc))
    except subprocess.TimeoutExpired:
        evidence.update(render_status="TIMEOUT", message="HWPX 재열기/렌더 시간 초과")
    except Exception as exc:
        evidence.update(render_status="FAIL", message=f"{type(exc).__name__}: {exc}")
    return evidence
