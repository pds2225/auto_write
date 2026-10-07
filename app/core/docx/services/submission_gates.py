"""submission_gates — Wave B/C 제출·이력서 결정론 가드 (재구현 금지, 기존 엔진 배선).

L040 필수서식은 usage_acceptance.check_missing_required_documents 가 이미 있다.
여기 모듈은 그 검사에 안 들어 있던 파일명·폴더·양식출처·페이지 기준선·이력서 골격을
한곳에 모아 fill/submit/수용검사가 호출한다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# L059 — 상태 접미사(_DRAFT)만 허용. 작업서술·중간산출물은 제출 폴더 오염.
WORK_SUFFIXES: tuple[str, ...] = (
    "_converted",
    "_고도화",
    "_통합",
    "_노트북LM",
    "_notebooklm",
    "_auto",
    "_draft_backup",
)
_ALLOWED_STATUS_SUFFIXES: tuple[str, ...] = ("_DRAFT", "_DRAFT2", "_제출용")

# L037/계획 L049 — 공고·모집요강을 빈 양식처럼 채우지 않는다.
# 맨줄기 '공고' 단독은 오탐(공고문식·공고결과)이라 쓰지 않는다.
_ANNOUNCEMENT_NAME_KEYWORDS: tuple[str, ...] = (
    "공고문", "모집공고", "모집요강", "사업공고", "모집안내",
)

# L048 — 제출 폴더에 원본/중간본이 섞이면 안 된다.
_SUBMIT_MIX_NAME_RE = re.compile(
    r"(원본|양식원본|구버전|_converted|_고도화|_노트북LM|_notebooklm|_정리본|backup)",
    re.IGNORECASE,
)

# L043
_SLASH_HEADER_RE = re.compile(
    r"학력\s*/\s*경력|경력\s*/\s*자격|학력\s*/\s*경력\s*/\s*자격"
)

# L044 — 필수 골격 표지(별칭). 컨설팅·기타는 선택(있으면 삭제 금지).
RESUME_SKELETON_ALIASES: tuple[tuple[str, ...], ...] = (
    ("인적", "성명", "인적사항"),
    ("경력", "경력사항"),
    ("강의", "주최기관"),
    ("수행", "프로젝트명", "수행실적"),
)
RESUME_SKELETON_REQUIRED: tuple[str, ...] = tuple(g[0] for g in RESUME_SKELETON_ALIASES)
RESUME_SKELETON_PRESERVE: tuple[str, ...] = ("기타",)

PORTFOLIO_MARKER = "[포트폴리오 이미지 삽입 필요]"
PHOTO_MARKER = "[사진 삽입 필요]"

TEMPLATE_EXAMPLE_BLUE = "0000FF"
DEFAULT_ACCENT_BLUE = "2E74B5"

# L156 — 참고이미지 표 프레임 (mm). 제목 6mm + 이미지 ≈49mm.
REF_IMAGE_FRAME_MM: tuple[float, float] = (170.0, 55.0)
REF_IMAGE_TITLE_HEIGHT_MM = 6.0
_HWPUNIT_PER_MM = 7200 / 25.4

_HANGUL_REQUIRED_RE = re.compile(
    r"한글\s*(전용|만|파일)|HWPX?\s*(만|전용|로\s*제출)",
    re.IGNORECASE,
)


class AnnouncementFormError(ValueError):
    """공고 파일/PDF 를 양식처럼 채우려고 할 때."""


class SampleSectionError(ValueError):
    """L154: 전체 적용 전에 1섹션 샘플 OK 가 없을 때."""


def work_suffix_hits(name: str) -> list[str]:
    """파일명(확장자 포함 가능)에서 금지 작업접미사를 찾는다. _DRAFT 는 허용."""
    stem = Path(str(name)).stem
    hits = [sfx for sfx in WORK_SUFFIXES if sfx.lower() in stem.lower() or sfx in stem]
    return hits


def is_announcement_form_path(path: str | Path) -> bool:
    """파일명·확장자로 '공고를 양식처럼 채우려는 입력'인지 본다 (L049)."""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return True
    stem = p.stem
    return any(kw in stem for kw in _ANNOUNCEMENT_NAME_KEYWORDS)


def assert_not_announcement_form(path: str | Path) -> None:
    """채움 입력으로 공고 PDF/공고 HWPX 를 거부한다."""
    p = Path(path)
    if not is_announcement_form_path(p):
        return
    if p.suffix.lower() == ".pdf":
        raise AnnouncementFormError(
            f"PDF는 양식이 아닙니다(L049). 공고 PDF를 채우지 마세요: {p.name}"
        )
    raise AnnouncementFormError(
        f"공고 파일은 양식이 아닙니다(L049/L037). 서식만 채우세요: {p.name}"
    )


def submit_folder_contamination(paths: Iterable[str | Path]) -> list[str]:
    """제출 대상 목록에서 원본·중간본 혼입 파일명을 반환한다 (L048)."""
    dirty: list[str] = []
    for raw in paths:
        p = Path(raw)
        if _SUBMIT_MIX_NAME_RE.search(p.name):
            dirty.append(p.name)
        elif is_announcement_form_path(p):
            dirty.append(p.name)
    return dirty


def infer_hangul_required(text: str) -> bool:
    """공고 문장이 한글(HWP/HWPX) 전용 제출을 요구하면 True (L050)."""
    return bool(text and _HANGUL_REQUIRED_RE.search(text))


def estimate_page_count(path: str | Path) -> int:
    """XML 페이지 분절 추정. 한글 렌더 쪽수는 L005 — 이 값은 기준선 비교용."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".hwpx" and zipfile.is_zipfile(p):
        return _count_hwpx_page_breaks(p) + 1
    if suffix == ".docx" and zipfile.is_zipfile(p):
        return _count_docx_page_breaks(p) + 1
    return 1


def page_count_increased(before: int, after: int) -> bool:
    return int(after) > int(before)


def _count_hwpx_page_breaks(path: Path) -> int:
    n = 0
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".xml"):
                continue
            data = zf.read(name)
            n += data.count(b"pageBreak")
            n += data.count(b'type="PAGE"')
            n += data.count(b"type='PAGE'")
    return n


def _count_docx_page_breaks(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
    except (KeyError, OSError, zipfile.BadZipFile):
        return 0
    return xml.count(b'w:type="page"') + xml.count(b"w:type='page'")


def slash_combo_headers(text: str) -> list[str]:
    """학력/경력처럼 슬래시로 뭉갠 헤더 (L043)."""
    return _SLASH_HEADER_RE.findall(text or "")


def missing_resume_skeleton_sections(text: str) -> list[str]:
    """표준 이력서 필수 골격 표지가 본문에 없으면 목록으로 반환 (L044)."""
    blob = text or ""
    missing: list[str] = []
    for group in RESUME_SKELETON_ALIASES:
        if not any(mark in blob for mark in group):
            missing.append(group[0])
    return missing


def dropped_other_history(source_text: str, output_text: str) -> bool:
    """원본에 '기타' 이력이 있었는데 출력에서 사라졌는지 (L044)."""
    if "기타" not in (source_text or ""):
        return False
    return "기타" not in (output_text or "")


def portfolio_ok(text: str, *, has_image: bool = False) -> bool:
    """포트폴리오 실물 또는 삽입 마커 (L039)."""
    if has_image:
        return True
    return PORTFOLIO_MARKER in (text or "")


def ensure_portfolio_marker(text: str, *, has_image: bool = False) -> str:
    if portfolio_ok(text, has_image=has_image):
        return text
    base = (text or "").rstrip()
    return f"{base}\n\n{PORTFOLIO_MARKER}" if base else PORTFOLIO_MARKER


def photo_slot_ok(text: str, *, has_photo: bool = False) -> bool:
    """증명사진 또는 [사진 삽입 필요] (JSON L061 사진칸)."""
    if has_photo:
        return True
    return PHOTO_MARKER in (text or "")


def resume_layout_warnings(
    text: str,
    *,
    has_image: bool = False,
    has_photo: bool = False,
) -> list[str]:
    """이력서 본문에서 L039/L043/L044/L061 구멍을 경고로 모은다."""
    warns: list[str] = []
    slashes = slash_combo_headers(text)
    if slashes:
        warns.append(f"L043: 슬래시 합성 헤더 {slashes} — 블록별 서브헤더로 나눠라")
    missing = missing_resume_skeleton_sections(text)
    if missing:
        warns.append(f"L044: 표준 골격 표지 누락 {missing}")
    if not portfolio_ok(text, has_image=has_image):
        warns.append(f"L039: 포트폴리오 실물 또는 {PORTFOLIO_MARKER}")
    if not photo_slot_ok(text, has_photo=has_photo):
        warns.append(f"L061: 증명사진 또는 {PHOTO_MARKER}")
    return warns


def _norm_hex(color: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", color or "").upper()


def is_template_example_blue(color: str) -> bool:
    return _norm_hex(color) == TEMPLATE_EXAMPLE_BLUE


def safe_body_accent(color: str) -> str:
    """본문 강조색. #0000FF 는 양식 예시체라 평가용 accent 로 쓰지 않는다 (L155)."""
    if is_template_example_blue(color):
        return DEFAULT_ACCENT_BLUE
    return color.lstrip("#") or DEFAULT_ACCENT_BLUE


def require_sample_ok(*, sample_ok: bool, full_document: bool) -> None:
    """레이아웃 전체 적용 전 최소 1섹션 샘플 OK (L154)."""
    if full_document and not sample_ok:
        raise SampleSectionError(
            "L154: 전체 적용 전 최소 1섹션 샘플 산출물·OK 가 필요합니다."
        )


def reference_image_frame_hwpunit() -> tuple[int, int]:
    w_mm, h_mm = REF_IMAGE_FRAME_MM
    return (
        int(round(w_mm * _HWPUNIT_PER_MM)),
        int(round(h_mm * _HWPUNIT_PER_MM)),
    )


def reference_image_title_hwpunit() -> int:
    return int(round(REF_IMAGE_TITLE_HEIGHT_MM * _HWPUNIT_PER_MM))


# ---------------------------------------------------------------------------
# L049 — YYYYMMDD 공고명/제출/
# ---------------------------------------------------------------------------

SUBMIT_DIR_NAME = "제출"
_DATED_NOTICE_RE = re.compile(r"^(\d{8})(?:\s+|_)(.+)$")
_INVALID_FN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _stem_token(text: str, *, fallback: str = "미상") -> str:
    s = _INVALID_FN.sub("", (text or "").strip())
    s = re.sub(r"\s+", "", s)
    return s or fallback


def is_dated_notice_folder(path: str | Path) -> bool:
    return bool(_DATED_NOTICE_RE.match(Path(path).name))


def dated_notice_parts(path: str | Path) -> tuple[str, str] | None:
    m = _DATED_NOTICE_RE.match(Path(path).name)
    if not m:
        return None
    return m.group(1), m.group(2)


def build_submit_layout_dir(
    notice_folder: str | Path,
    *,
    today: str | None = None,
    wrap_undated: bool = False,
) -> Path:
    """``YYYYMMDD 공고명/제출``. 이미 날짜 접두면 ``notice/제출``.

    wrap_undated=False(기본)는 현행처럼 ``notice/제출`` 만 만든다 — 폴더를 옮기지 않는다.
    """
    folder = Path(notice_folder)
    if is_dated_notice_folder(folder):
        return folder / SUBMIT_DIR_NAME
    if wrap_undated:
        ymd = today or datetime.now().strftime("%Y%m%d")
        return folder / f"{ymd} {folder.name}" / SUBMIT_DIR_NAME
    return folder / SUBMIT_DIR_NAME


def is_submit_layout_path(path: str | Path) -> bool:
    """경로에 ``YYYYMMDD …/제출`` 구간이 있으면 True."""
    parts = Path(path).parts
    submit_idx = next((i for i, part in enumerate(parts) if part == SUBMIT_DIR_NAME), None)
    if submit_idx is None or submit_idx == 0:
        return False
    return bool(_DATED_NOTICE_RE.match(parts[submit_idx - 1]))


# ---------------------------------------------------------------------------
# L048 — 공고 명명 튜플 + 기존 PDF 합본 (한글 COM 렌더는 아님)
# ---------------------------------------------------------------------------

def announcement_tuple_stem(
    *,
    yyyymmdd: str,
    notice_name: str,
    doc_kind: str = "증빙합본",
) -> str:
    """``YYYYMMDD_공고명_서류명`` (공백·금지문자 제거)."""
    ymd = re.sub(r"\D", "", yyyymmdd or "")[:8]
    if len(ymd) != 8:
        raise ValueError("L048: yyyymmdd는 8자리 숫자여야 합니다")
    return f"{ymd}_{_stem_token(notice_name)}_{_stem_token(doc_kind)}"


def merge_pdfs(sources: Iterable[str | Path], dest: str | Path) -> Path:
    """기존 PDF 들을 한 파일로 합친다. 한글 렌더/변환이 아니다."""
    from pypdf import PdfReader, PdfWriter

    srcs = [Path(s) for s in sources]
    if not srcs:
        raise ValueError("L048: 합본할 PDF가 없습니다")
    dest_p = Path(dest)
    writer = PdfWriter()
    for src in srcs:
        if not src.is_file():
            raise FileNotFoundError(f"L048: PDF 없음 {src}")
        reader = PdfReader(str(src))
        for page in reader.pages:
            writer.add_page(page)
    dest_p.parent.mkdir(parents=True, exist_ok=True)
    with dest_p.open("wb") as fh:
        writer.write(fh)
    return dest_p


# ---------------------------------------------------------------------------
# L050 — 동일 stem PDF 쌍 검사. 생성은 rhwp/한글만. 이 클라우드 BLOCKED. soffice 미인정.
# ---------------------------------------------------------------------------

def sibling_pdf_path(path: str | Path) -> Path:
    return Path(path).with_suffix(".pdf")


def is_draft_artifact(path: str | Path) -> bool:
    stem = Path(path).stem
    return stem.endswith("_DRAFT") or stem.endswith("_DRAFT2")


def missing_pdf_pair(path: str | Path) -> bool:
    """초안이 아닌 HWP/HWPX/DOCX 에 같은 이름 PDF 가 없으면 True."""
    p = Path(path)
    if is_draft_artifact(p):
        return False
    if p.suffix.lower() not in {".hwp", ".hwpx", ".docx"}:
        return False
    return not sibling_pdf_path(p).is_file()


@dataclass(frozen=True)
class PdfPairGenerateResult:
    """L050 생성 시도 결과. generated=True 가 아니면 mechanized 로 올리지 않는다."""

    generated: bool
    skipped: bool
    blocked: bool
    reason: str
    evidence: str = ""
    attempts: int = 0
    attempt_reasons: tuple[str, ...] = ()


def hangul_pdf_tool() -> str | None:
    """제출 품질 PDF 실행 파일. ``RHWP_EXE`` 절대경로 다음 PATH ``rhwp``.

    LibreOffice(soffice) 는 한글 레이아웃이 달라 인정하지 않는다.
    한글 COM PDF 저장으로 대체하지 않는다.
    """
    from .native_hwp import resolve_rhwp_executable

    return resolve_rhwp_executable()


def l050_evidence_path(pdf: str | Path) -> Path:
    pdf_p = Path(pdf)
    return pdf_p.with_name(f"{pdf_p.stem}.l050.json")


def _executable_basename(tool: str) -> str:
    """Windows 증거 JSON 의 ``C:\\...\\rhwp.exe`` 도 Linux 에서 이름만 뽑는다."""
    normalized = str(tool).strip().strip('"').replace("\\", "/")
    return normalized.rsplit("/", 1)[-1].lower()


def _write_l050_evidence(source: Path, dest: Path, tool: str) -> str:
    """Windows 실측 성공만 증거 파일을 남긴다. Linux 성공으로 mechanized 를 만들지 않는다."""
    if sys.platform != "win32":
        return ""
    evidence = l050_evidence_path(dest)
    payload = {
        "lesson": "L050",
        "generated": True,
        "platform": "win32",
        "tool": tool,
        "soffice": False,
        "source": str(source.resolve()),
        "pdf": str(dest.resolve()),
        "pdf_bytes": dest.stat().st_size,
        "note": (
            "Windows rhwp export-pdf 산출. lessons_coverage 의 L050 은 "
            "Mimo 실측 전까지 gap 이다. 이 파일만으로 mechanized 가 아니다."
        ),
    }
    try:
        evidence.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return ""
    return str(evidence)


def _try_hangul_com_pdf(source: Path, dest: Path) -> PdfPairGenerateResult | None:
    """Windows 한글 COM SaveAs PDF.

    COM 이 없으면 None. 성공해도 rhwp 증거 파일은 쓰지 않고 mechanized 로
    올리지 않는다. 예외는 삼키고 BLOCKED 를 돌려 제출을 깨지 않는다.
    """
    if sys.platform != "win32":
        return None
    from .hwp_docx_convert import (
        HangulComTimeout,
        export_pdf_via_com,
        hancom_com_available,
    )

    if not hancom_com_available():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    import time
    reasons = []
    for attempt in range(1, 3):
        try:
            # export_pdf_via_com always performs its owned-PID cleanup in finally.
            # Never enumerate/kill newly appearing user windows from this layer.
            export_pdf_via_com(source, dest)
        except HangulComTimeout as exc:
            reasons.append(str(exc))
            if dest.is_file():
                try:
                    dest.unlink()
                except OSError:
                    pass
            if attempt == 1:
                time.sleep(5)
                continue
            return PdfPairGenerateResult(False, False, True, f"BLOCKED: {exc}",
                attempts=attempt, attempt_reasons=tuple(reasons))
        except Exception:
            if dest.is_file() and dest.stat().st_size == 0:
                try:
                    dest.unlink()
                except OSError:
                    pass
            reason = "BLOCKED-by-form: Hangul refused SaveAs PDF for this form"
            return PdfPairGenerateResult(False, False, True, reason,
                attempts=attempt, attempt_reasons=tuple(reasons+[reason]))
        if dest.is_file() and dest.stat().st_size > 0:
            reasons.append("Hangul COM SaveAs PDF")
            return PdfPairGenerateResult(True, False, False, reasons[-1], "",
                attempt, tuple(reasons))
        reason = "BLOCKED-by-form: Hangul refused SaveAs PDF for this form"
        return PdfPairGenerateResult(False, False, True, reason,
            attempts=attempt, attempt_reasons=tuple(reasons+[reason]))


def try_generate_sibling_pdf(path: str | Path) -> PdfPairGenerateResult:
    """동일 stem PDF 를 만든다. rhwp 가 있으면 export-pdf, 없으면 Windows 한글 COM.

    초안은 생성하지 않는다. soffice 폴백 없음. COM 성공은 파일을 만들 뿐
    mechanized 근거(``*.l050.json``)가 아니다. ``RHWP_EXE`` 를 PATH ``rhwp`` 보다
    먼저 쓴다.
    """
    p = Path(path)
    if is_draft_artifact(p):
        return PdfPairGenerateResult(False, True, False, "draft skipped")
    if p.suffix.lower() not in {".hwp", ".hwpx", ".docx"}:
        return PdfPairGenerateResult(False, True, False, "not a document pair source")
    dest = sibling_pdf_path(p)
    if dest.is_file() and dest.stat().st_size > 0:
        return PdfPairGenerateResult(False, True, False, "pdf already exists")
    tool = hangul_pdf_tool()
    if tool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run_kwargs: dict[str, Any] = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": 120,
        }
        if sys.platform == "win32":
            run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                [tool, "export-pdf", str(p.resolve()), "-o", str(dest.resolve())],
                **run_kwargs,
            )
        except subprocess.TimeoutExpired:
            return PdfPairGenerateResult(False, False, True, "BLOCKED: rhwp export-pdf timeout")
        except OSError as exc:
            return PdfPairGenerateResult(
                False, False, True, f"BLOCKED: rhwp launch failed {exc}"
            )
        if dest.is_file() and dest.stat().st_size > 0:
            evidence = _write_l050_evidence(p, dest, tool)
            return PdfPairGenerateResult(True, False, False, f"rhwp:{tool}", evidence)
        if dest.is_file() and dest.stat().st_size == 0:
            try:
                dest.unlink()
            except OSError:
                pass
        err = (proc.stderr or proc.stdout or "").strip()[:200]
        return PdfPairGenerateResult(
            False, False, True, f"BLOCKED: rhwp failed rc={proc.returncode} {err}"
        )
    com = _try_hangul_com_pdf(p, dest)
    if com is not None:
        return com
    if sys.platform == "win32":
        return PdfPairGenerateResult(
            False,
            False,
            True,
            "BLOCKED: rhwp 없음, 한글 COM PDF 도 사용할 수 없음",
        )
    return PdfPairGenerateResult(
        False,
        False,
        True,
        "BLOCKED: no rhwp/Hangul (this cloud cannot generate L050 pair)",
    )


def l050_mechanization_status(evidence: str | Path | None = None) -> dict[str, Any]:
    """L050 JSON 을 mechanized 로 올릴 자격이 있는지.

    Linux/클라우드는 증거 파일이 있어도 BLOCKED. Windows 도 증거 파일이
    rhwp export-pdf 성공을 증명하기 전에는 BLOCKED. 증명돼도 ``mechanized`` 는
    false — 커버리지 분류는 Mimo 실측 뒤에만 바꾼다.
    """
    blocked = {
        "status": "BLOCKED",
        "mechanized": False,
        "platform": sys.platform,
        "generated": False,
        "reason": "BLOCKED: L050 stays gap until a Windows rhwp evidence artifact exists",
    }
    if sys.platform != "win32":
        blocked["reason"] = "BLOCKED: this platform cannot claim L050 generation (cloud/Linux)"
        return blocked
    if not evidence:
        blocked["reason"] = "BLOCKED: Windows rhwp evidence artifact missing"
        return blocked
    path = Path(evidence)
    if not path.is_file():
        blocked["reason"] = "BLOCKED: Windows rhwp evidence artifact missing"
        return blocked
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        blocked["reason"] = "BLOCKED: L050 evidence unreadable"
        return blocked
    if not isinstance(data, dict):
        blocked["reason"] = "BLOCKED: L050 evidence is not an object"
        return blocked
    pdf = Path(str(data.get("pdf") or ""))
    tool_name = _executable_basename(str(data.get("tool") or ""))
    proven = (
        data.get("lesson") == "L050"
        and data.get("generated") is True
        and data.get("platform") == "win32"
        and data.get("soffice") is False
        and "soffice" not in tool_name
        and "libreoffice" not in tool_name
        and (tool_name == "rhwp" or tool_name.startswith("rhwp."))
        and pdf.is_file()
        and pdf.suffix.lower() == ".pdf"
        and pdf.stat().st_size > 0
    )
    if not proven:
        blocked["reason"] = "BLOCKED: L050 evidence does not prove Windows rhwp export-pdf"
        return blocked
    return {
        "status": "GENERATED",
        "mechanized": False,
        "platform": sys.platform,
        "generated": True,
        "reason": (
            "Windows rhwp sibling PDF recorded. lessons_coverage stays gap until "
            "Mimo proves the live export. Do not mark mechanized from this status alone."
        ),
        "evidence": str(path),
        "pdf": str(pdf),
    }


def sibling_pdf_attempt(path: str | Path) -> dict[str, Any]:
    """제출 경로가 호출하는 L050 시도. mechanized 는 항상 false."""
    gen = try_generate_sibling_pdf(path)
    claim = l050_mechanization_status(gen.evidence or None)
    return {
        "generated": gen.generated,
        "skipped": gen.skipped,
        "blocked": gen.blocked,
        "reason": gen.reason,
        "attempts": gen.attempts,
        "attempt_reasons": list(gen.attempt_reasons),
        "evidence": gen.evidence,
        "missing": missing_pdf_pair(path),
        "mechanized": False,
        "claim_status": claim["status"],
    }


# ---------------------------------------------------------------------------
# L005 — 한글 GUI 픽셀. pytest PASS 는 검증이 아니다. 증거 파일이 있어야 PASS.
# ---------------------------------------------------------------------------

L005_CHECKLIST: tuple[str, ...] = ("overlap", "page_count", "table_grid", "image_size")
_L005_SHOT_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_HANGUL_GUI_DIRS = (
    r"C:\Program Files (x86)\HNC",
    r"C:\Program Files\HNC",
)
_L005_RULE = (
    "Open the output in 한글 2022 (한컴오피스). Check overlap, page count, "
    "table grid, image size on screen. Screenshot. pytest PASS is not L005."
)


def hangul_gui_available() -> bool:
    """한글 GUI 설치 흔적만 본다. COM Dispatch 와 PDF 저장은 하지 않는다."""
    if sys.platform != "win32":
        return False
    try:
        from .hwp_docx_convert import hancom_com_available

        if hancom_com_available():
            return True
    except Exception:
        pass
    return any(Path(folder).is_dir() for folder in _HANGUL_GUI_DIRS)


def _l005_base() -> dict[str, Any]:
    return {
        "logic_review_is_verification": False,
        "pytest_pass_counts": False,
        "platform": sys.platform,
        "hangul_gui": hangul_gui_available(),
        "rule": _L005_RULE,
        "checklist": list(L005_CHECKLIST),
    }


def _safe_screenshot(folder: Path, named: str) -> Path | None:
    if not named or Path(named).is_absolute() or ".." in Path(named).parts:
        return None
    shot = folder / named
    try:
        shot.resolve().relative_to(folder.resolve())
    except ValueError:
        return None
    if (
        shot.is_file()
        and shot.stat().st_size > 0
        and shot.suffix.lower() in _L005_SHOT_SUFFIXES
    ):
        return shot
    return None


def _l005_packet_ok(folder: Path) -> tuple[bool, str]:
    checklist_path = folder / "l005_checklist.json"
    if not checklist_path.is_file():
        return False, "checklist missing"
    try:
        data = json.loads(checklist_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "checklist unreadable"
    if not isinstance(data, dict) or data.get("lesson") != "L005":
        return False, "not an L005 checklist"
    if data.get("pytest_pass_counts") is True:
        return False, "pytest PASS cannot satisfy L005"
    checks = data.get("checklist")
    if not isinstance(checks, dict):
        return False, "checklist object missing"
    for key in L005_CHECKLIST:
        if checks.get(key) is not True:
            return False, f"checklist incomplete: {key}"
    named = _safe_screenshot(folder, str(data.get("screenshot") or ""))
    if named is not None:
        return True, str(named)
    for fallback in ("hangul_gui.png", "hangul_gui.jpg", "hangul_gui.jpeg", "hangul_gui.webp"):
        found = _safe_screenshot(folder, fallback)
        if found is not None:
            return True, str(found)
    return False, "screenshot missing"


def write_l005_review_template(
    dest_dir: str | Path,
    *,
    document: str | Path | None = None,
) -> Path:
    """체크리스트를 전부 false 로 만든다. 스크린샷은 만들지 않으며 PASS 가 아니다."""
    folder = Path(dest_dir)
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "lesson": "L005",
        "document": "" if document is None else str(document),
        "checklist": {key: False for key in L005_CHECKLIST},
        "screenshot": "hangul_gui.png",
        "pytest_pass_counts": False,
        "note": (
            "한글 2022 GUI에서 글자겹침(overlap)·쪽수(page_count)·"
            "표격자(table_grid)·그림크기(image_size)를 보고 "
            "hangul_gui.png 를 이 폴더에 둔 뒤 checklist 값을 true 로 바꾼다. "
            "pytest PASS 와 rhwp PDF 는 L005 가 아니다."
        ),
    }
    path = folder / "l005_checklist.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def record_l005_pixel_review(
    evidence_dir: str | Path,
    *,
    document: str | Path,
    checklist: dict[str, bool],
    screenshot: str | Path,
) -> dict[str, Any]:
    """스크린샷과 체크리스트를 증거 폴더에 기록한다.

    반환 상태는 ``l005_pixel_review_status`` 와 같다. 파일을 써도 Linux 는
    BLOCKED 이고, 네 항목이 모두 true 이고 스크린샷이 있을 때만 Windows+한글에서 PASS.
    """
    folder = Path(evidence_dir)
    folder.mkdir(parents=True, exist_ok=True)
    shot = Path(screenshot)
    suffix = shot.suffix.lower() if shot.suffix.lower() in _L005_SHOT_SUFFIXES else ".png"
    dest_name = f"hangul_gui{suffix}"
    target = folder / dest_name
    if shot.is_file() and shot.stat().st_size > 0 and shot.suffix.lower() in _L005_SHOT_SUFFIXES:
        if shot.resolve() != target.resolve():
            shutil.copyfile(shot, target)
        stored = dest_name
    else:
        stored = ""
    payload = {
        "lesson": "L005",
        "document": str(document),
        "checklist": {key: checklist.get(key) is True for key in L005_CHECKLIST},
        "screenshot": stored,
        "pytest_pass_counts": False,
        "note": (
            "한글 GUI에서 읽은 네 항목과 스크린샷. pytest PASS 는 이 기록을 대신하지 않는다."
        ),
    }
    (folder / "l005_checklist.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return l005_pixel_review_status(folder)


def l005_pixel_review_status(
    evidence_dir: str | Path | None = None,
) -> dict[str, Any]:
    """L005: pytest·로직 리뷰는 검증이 아니다. 한글 GUI 픽셀 증거가 필요하다.

    Linux 는 증거 폴더가 있어도 BLOCKED. Windows 에서 PASS 는 한글 GUI 가 있고
    체크리스트 4항이 true 이며 비어 있지 않은 스크린샷 파일이 있을 때만.
    """
    base = _l005_base()
    if sys.platform != "win32":
        base["status"] = "BLOCKED"
        base["reason"] = "BLOCKED: no Hangul GUI on this platform (evidence ignored)"
        return base
    if not hangul_gui_available():
        base["status"] = "NEEDS_HANGUL_GUI"
        base["reason"] = "NEEDS_HANGUL_GUI: Windows but Hangul GUI was not detected"
        return base
    if evidence_dir is None:
        base["status"] = "REVIEW_REQUIRED"
        base["reason"] = "REVIEW_REQUIRED: Hangul GUI available; screenshot and checklist not recorded"
        return base
    ok, detail = _l005_packet_ok(Path(evidence_dir))
    if not ok:
        base["status"] = "REVIEW_REQUIRED"
        base["reason"] = f"REVIEW_REQUIRED: {detail}"
        return base
    base["status"] = "PASS"
    base["reason"] = "Hangul GUI checklist and screenshot exist"
    base["screenshot"] = detail
    base["evidence_dir"] = str(Path(evidence_dir))
    return base
