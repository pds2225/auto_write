"""folder_analyzer.py — 공고 폴더 통째 분석(공고문 + 양식 목록).

사용자에게는 한국어 채팅용 요약만 제공한다. 선택적으로 ``.analysis/`` 에
기계용 JSON 을 저장한다(사용자가 직접 볼 필요 없음).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .announcement_analyzer import AnnouncementReport, analyze_announcement
from .cross_form_autofill import (
    _FORM_GLOB_PATTERNS,
    _NON_FORM_NAME_KEYWORDS,
    _SUPPORTED_EXTS,
    is_skipped_non_form,
)
from .form_analyzer import FormReport, analyze_form

_ANNOUNCEMENT_NAME_KEYWORDS: tuple[str, ...] = (
    "공고", "공고문", "모집", "안내", "모집공고",
)

_SKIP_DIRS = frozenset({".analysis", "filled", "filled_out", "__pycache__"})


@dataclass
class FolderFormSummary:
    path: str
    name: str
    question_count: int = 0
    required_count: int = 0
    psst_count: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class FolderAnalysisReport:
    folder: str
    announcement: Optional[AnnouncementReport] = None
    announcement_path: str = ""
    forms: list[FolderFormSummary] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "announcement_path": self.announcement_path,
            "announcement": self.announcement.as_dict() if self.announcement else None,
            "forms": [
                {
                    "path": f.path,
                    "name": f.name,
                    "question_count": f.question_count,
                    "required_count": f.required_count,
                    "psst_count": f.psst_count,
                    "notes": f.notes,
                }
                for f in self.forms
            ],
            "skipped": self.skipped,
            "notes": self.notes,
        }


def _name_has_keyword(name: str, keywords: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(kw.lower() in lowered for kw in keywords)


def is_announcement_file(path: Path) -> bool:
    """파일명으로 공고문 후보인지 판별한다."""
    if path.suffix.lower() not in {".docx", ".hwp", ".hwpx", ".pdf", ".txt"}:
        return False
    return _name_has_keyword(path.stem, _ANNOUNCEMENT_NAME_KEYWORDS)


def classify_folder_files(folder: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """폴더 최상위 파일을 공고문 / 양식 / 기타로 분류한다."""
    announcements: list[Path] = []
    forms: list[Path] = []
    other: list[Path] = []
    seen: set[str] = set()

    for pattern in _FORM_GLOB_PATTERNS + ("*.pdf", "*.txt"):
        for path in sorted(folder.glob(pattern)):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            if path.parent.name in _SKIP_DIRS or path.name.startswith("."):
                continue
            if path.suffix.lower() not in _SUPPORTED_EXTS | {".pdf", ".txt"}:
                other.append(path)
                continue
            if is_announcement_file(path):
                announcements.append(path)
            elif is_skipped_non_form(path):
                other.append(path)
            else:
                forms.append(path)
    return announcements, forms, other


def _pick_best_announcement(candidates: list[Path]) -> Path | None:
    if not candidates:
        return None

    def score(p: Path) -> tuple[int, int, float]:
        name = p.stem.lower()
        kw = sum(1 for k in _ANNOUNCEMENT_NAME_KEYWORDS if k in name)
        prefer = 1 if "공고문" in name or "모집" in name else 0
        return prefer, kw, p.stat().st_mtime

    return max(candidates, key=score)


def analyze_folder(
    folder: str | Path,
    *,
    openai_service: Any = None,
    save_json: bool = True,
) -> FolderAnalysisReport:
    """공고 폴더의 공고문 1개 + 양식들을 분석한다."""
    root = Path(folder)
    if not root.is_dir():
        raise FileNotFoundError(f"폴더가 없습니다: {root}")

    report = FolderAnalysisReport(folder=str(root))
    ann_paths, form_paths, other = classify_folder_files(root)
    report.skipped.extend(str(p) for p in other)

    best_ann = _pick_best_announcement(ann_paths)
    if best_ann:
        report.announcement_path = str(best_ann)
        report.announcement = analyze_announcement(
            best_ann, openai_service=openai_service)
    elif ann_paths:
        report.notes.append("공고문 후보는 있으나 분석에 실패했습니다.")
    else:
        report.notes.append("공고문 파일을 찾지 못했습니다(이름에 '공고'·'모집' 포함 여부 확인).")

    for fp in form_paths:
        summary = FolderFormSummary(path=str(fp), name=fp.name)
        try:
            fr = analyze_form(fp)
            summary.question_count = fr.question_count
            summary.required_count = fr.required_question_count
            summary.psst_count = sum(1 for v in fr.psst_present.values() if v)
            if fr.analysis_notes:
                summary.notes.extend(fr.analysis_notes[:2])
        except Exception as exc:  # noqa: BLE001 — 한 양식 실패가 전체를 막지 않음
            summary.notes.append(str(exc))
        report.forms.append(summary)

    if save_json:
        out_dir = root / ".analysis"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "folder_analysis.json"
        out_file.write_text(
            json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return report


def _fmt_list(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    return str(value) if value else ""


def format_folder_summary_korean(report: FolderAnalysisReport) -> str:
    """채팅에 붙여넣기 좋은 한국어 요약."""
    lines: list[str] = []
    folder_name = Path(report.folder).name
    lines.append(f"📁 공고 폴더: {folder_name}")

    ann = report.announcement
    if ann:
        ki = ann.key_info or {}
        if ki.get("deadline"):
            lines.append(f"■ 마감: {_fmt_list(ki['deadline'])}")
        elig = ki.get("eligibility") or ki.get("support_target")
        if elig:
            lines.append(f"■ 지원자격: {_fmt_list(elig)[:200]}")
        docs = ki.get("required_documents")
        if docs:
            lines.append(f"■ 제출서류: {_fmt_list(docs)[:300]}")
        if ann.criteria:
            crit = ", ".join(
                f"{c['name']} {c['max_score']}점" for c in ann.criteria[:6])
            tail = f" 외 {len(ann.criteria) - 6}개" if len(ann.criteria) > 6 else ""
            lines.append(f"■ 평가(총 {ann.total_max_score}점): {crit}{tail}")
        elif ann.total_max_score:
            lines.append(f"■ 평가: 총 {ann.total_max_score}점")
        if ki.get("funding_amount"):
            lines.append(f"■ 지원규모: {_fmt_list(ki['funding_amount'])[:120]}")
    elif report.announcement_path:
        lines.append("■ 공고: 분석했으나 핵심 정보를 못 찾았습니다")
    else:
        lines.append("■ 공고: 공고문 파일 없음")

    if report.forms:
        lines.append(f"■ 양식 {len(report.forms)}개")
        for f in report.forms:
            detail = f"작성항목 {f.question_count}개"
            if f.required_count:
                detail += f" (필수 {f.required_count})"
            if f.psst_count >= 4:
                detail += " · PSST 4영역"
            elif f.psst_count:
                detail += f" · PSST {f.psst_count}영역"
            lines.append(f"  · {f.name} — {detail}")
    else:
        lines.append("■ 양식: 신청서·참가서류 파일을 찾지 못했습니다")

    if report.notes:
        for n in report.notes[:3]:
            lines.append(f"※ {n}")

    return "\n".join(lines)
