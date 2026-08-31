"""submission_gates — Wave B/C 제출·이력서 결정론 가드 (재구현 금지, 기존 엔진 배선).

L040 필수서식은 usage_acceptance.check_missing_required_documents 가 이미 있다.
여기 모듈은 그 검사에 안 들어 있던 파일명·폴더·양식출처·페이지 기준선·이력서 골격을
한곳에 모아 fill/submit/수용검사가 호출한다.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Iterable

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
