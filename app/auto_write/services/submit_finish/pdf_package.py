"""F6 제출용 PDF 변환·합본.

기존 코드를 얇게 감싼다(재구현 없음).
- 변환: hwp_docx_convert.export_pdf_via_com (엔진이 띄운 한글 PID 만 종료하는
  소유권 보호가 이미 그 안에 있다. 여기서는 사용자가 연 한글 PID 가 변환 후에도
  살아있는지 사후 확인만 한다).
- 재시도·1차 타임아웃 원인 보존: submission_gates._try_hangul_com_pdf 와 같은 방식.
- 합본은 pypdf 로 하되 페이지 매니페스트·누락 검증을 더한다.
보고 문구에는 최종 제출 판단 표현을 쓰지 않는다(status.assert_no_forbidden).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .status import Finding, Status

Converter = Callable[[Path, Path], None]

_BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass
class ConvertResult:
    ok: bool
    pdf: Path | None
    attempts: int
    real_com: bool  # True: 실제 한글 COM 으로 변환. False: 주입된(가짜) 변환기.
    reasons: list[str] = field(default_factory=list)  # 시도별 실패 원인(1차 타임아웃 포함)
    user_pids_preserved: bool | None = None  # 변환 전부터 있던 Hwp PID 생존 여부(확인 불가면 None)
    findings: list[Finding] = field(default_factory=list)


@dataclass
class MergeResult:
    ok: bool
    out: Path | None
    total_pages: int
    manifest: list[dict[str, Any]] = field(default_factory=list)  # name/path/start_page/end_page/pages
    findings: list[Finding] = field(default_factory=list)


def _safe(text: str) -> str:
    cleaned = _BAD_NAME_CHARS.sub("", (text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def build_submission_name(doc_name: str, company: str, rep: str) -> str:
    """`(제출) <서류명>_<회사명>_<대표자명>_합본.pdf` (금지문자 제거)."""
    parts = [_safe(doc_name), _safe(company), _safe(rep)]
    if not all(parts):
        raise ValueError("서류명·회사명·대표자명은 비울 수 없습니다")
    return f"(제출) {parts[0]}_{parts[1]}_{parts[2]}_합본.pdf"


def _versioned(path: Path) -> Path:
    n = 2
    while True:
        cand = path.with_name(f"{path.stem}_v{n}{path.suffix}")
        if not cand.exists():
            return cand
        n += 1


def _resolve_out(out: Path, overwrite: bool, versioned: bool) -> Path:
    out = Path(out)
    if out.exists():
        if overwrite:
            return out
        if versioned:
            return _versioned(out)
        raise ValueError(f"이미 존재하는 파일은 덮어쓰지 않습니다: {out}")
    return out


def _hwp_pids() -> set[int] | None:
    try:
        from core.docx.services.hwp_docx_convert import _hangul_image_pids
    except ImportError:
        try:
            from app.core.docx.services.hwp_docx_convert import _hangul_image_pids
        except ImportError:
            return None
    try:
        return set(_hangul_image_pids())
    except Exception:
        return None


def _default_converter() -> Converter:
    try:
        from core.docx.services.hwp_docx_convert import export_pdf_via_com
    except ImportError:
        from app.core.docx.services.hwp_docx_convert import export_pdf_via_com
    return export_pdf_via_com


def convert_hwpx_to_pdf(
    hwpx: Path,
    pdf: Path,
    *,
    converter: Converter | None = None,
    retries: int = 2,
    overwrite: bool = False,
    versioned: bool = False,
    retry_wait: float = 5.0,
) -> ConvertResult:
    """HWPX -> PDF. retries 는 총 시도 횟수. 실패 사유는 reasons 에 모두 남긴다."""
    hwpx, pdf = Path(hwpx), Path(pdf)
    real = converter is None or bool(getattr(converter, "real_com", False))
    if not hwpx.is_file():
        raise FileNotFoundError(f"입력 없음: {hwpx}")
    pdf = _resolve_out(pdf, overwrite, versioned)
    conv = converter or _default_converter()
    before = _hwp_pids() if real else None
    pdf.parent.mkdir(parents=True, exist_ok=True)

    reasons: list[str] = []
    ok = False
    attempts = 0
    total = max(1, retries)
    for attempts in range(1, total + 1):
        try:
            conv(hwpx, pdf)
            if pdf.is_file() and pdf.stat().st_size > 0:
                ok = True
                break
            reasons.append(f"시도{attempts}: 변환기가 빈 PDF 를 남김")
        except Exception as exc:  # 타임아웃 포함, 원인 문구를 보존
            reasons.append(f"시도{attempts}: {type(exc).__name__}: {exc}")
        if pdf.is_file() and pdf.stat().st_size == 0:
            pdf.unlink()
        if attempts < total and retry_wait > 0:
            time.sleep(retry_wait)

    preserved: bool | None = None
    if before is not None:
        after = _hwp_pids()
        if after is not None:
            preserved = before <= after
    findings: list[Finding] = [Finding(
        "F6-CONVERT", Status.PASS if ok else Status.FAIL,
        "PDF 변환 완료" if ok else "PDF 변환 실패: " + " | ".join(reasons),
        source="engine", evidence=f"attempts={attempts} real_com={real}")]
    if not real:
        findings.append(Finding(
            "F6-REAL-COM", Status.UNVERIFIED,
            "가짜/주입 변환기 사용: 실제 한글 COM 변환 기술적 검증 미실행", source="engine"))
    if preserved is False:
        findings.append(Finding(
            "F6-USER-PID", Status.FAIL,
            "변환 전부터 있던 한글 프로세스가 사라짐: 사용자 확인 필요", source="engine"))
    return ConvertResult(ok, pdf if ok else None, attempts, real, reasons, preserved, findings)


def _page_count(path: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(path)).pages)


def merge_pdfs(
    inputs: Sequence[Path],
    out: Path,
    *,
    overwrite: bool = False,
    versioned: bool = False,
) -> MergeResult:
    """지정 순서로 합본. 입력 누락·0쪽이 하나라도 있으면 합본을 만들지 않고 FAIL."""
    from pypdf import PdfReader, PdfWriter

    inputs = [Path(p) for p in inputs]
    out = _resolve_out(Path(out), overwrite, versioned)
    findings: list[Finding] = []
    counts: list[int] = []
    for p in inputs:
        n = 0
        if not p.is_file():
            findings.append(Finding("F6-MISSING", Status.FAIL, "첨부 파일 없음", evidence=p.name))
        else:
            try:
                n = _page_count(p)
            except Exception as exc:
                findings.append(Finding("F6-UNREADABLE", Status.FAIL,
                                        f"PDF 를 읽지 못함: {type(exc).__name__}", evidence=p.name))
            else:
                if n <= 0:
                    findings.append(Finding("F6-EMPTY", Status.FAIL, "페이지 0", evidence=p.name))
        counts.append(n)
    if not inputs:
        findings.append(Finding("F6-MISSING", Status.FAIL, "합본 입력이 비어 있음"))
    if findings:
        return MergeResult(False, None, 0, [], findings)

    writer = PdfWriter()
    manifest: list[dict[str, Any]] = []
    cursor = 1
    for p, n in zip(inputs, counts):
        for page in PdfReader(str(p)).pages:
            writer.add_page(page)
        manifest.append({"name": p.name, "path": str(p), "pages": n,
                         "start_page": cursor, "end_page": cursor + n - 1})
        cursor += n
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        writer.write(fh)

    total = cursor - 1
    actual = _page_count(out)
    if actual != total:
        findings.append(Finding("F6-PAGES", Status.FAIL,
                                f"합본 쪽수 불일치 기대={total} 실제={actual}", evidence=out.name))
        return MergeResult(False, out, actual, manifest, findings)
    findings.append(Finding("F6-MERGE", Status.PASS,
                            f"합본 {len(inputs)}개 문서, 총 {total}쪽, 첨부 누락 0",
                            evidence=out.name, meta={"manifest": manifest}))
    return MergeResult(True, out, total, manifest, findings)


def package(
    application_hwpx: Path,
    attachments: Sequence[Path],
    out_dir: Path,
    *,
    doc_name: str,
    company: str,
    rep: str,
    converter: Converter | None = None,
    retries: int = 2,
    overwrite: bool = False,
    versioned: bool = False,
    retry_wait: float = 5.0,
) -> tuple[ConvertResult, MergeResult | None]:
    """신청서 HWPX 변환 후 [신청서 PDF] + 첨부 PDF(지정 순서) 합본. 변환 실패 시 합본 없음."""
    out_dir = Path(out_dir)
    application_hwpx = Path(application_hwpx)
    app_pdf = out_dir / f"{application_hwpx.stem}.pdf"
    conv = convert_hwpx_to_pdf(application_hwpx, app_pdf, converter=converter,
                               retries=retries, overwrite=overwrite,
                               versioned=versioned, retry_wait=retry_wait)
    if not conv.ok or conv.pdf is None:
        return conv, None
    name = build_submission_name(doc_name, company, rep)
    merged = merge_pdfs([conv.pdf, *attachments], out_dir / name,
                         overwrite=overwrite, versioned=versioned)
    return conv, merged
