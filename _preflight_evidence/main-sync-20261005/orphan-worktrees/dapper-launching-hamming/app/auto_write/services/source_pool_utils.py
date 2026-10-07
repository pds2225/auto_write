# source_pool_utils.py — Source pool listing and ranking utilities
"""소스 풀 목록화·순위 유틸리티.

cross_form_autofill에서 추출한 CORE 유틸리티.
이력서·사업계획서 양쪽에서 사용되는 소스 파일 탐색·순위 함수.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

__all__ = [
    "list_source_pool",
    "rank_source_pool",
    "SourcePickScore",
    "SourcePickReport",
]

_FORM_GLOB_PATTERNS = ("*.docx", "*.hwp", "*.hwpx")
_SUPPORTED_EXTS = {".docx", ".hwp", ".hwpx"}

_DEFAULT_SOURCE_KEYWORDS: tuple[str, ...] = (
    "사업계획서", "사업계획", "신청서", "완성", "k-global", "kglobal", "star",
    "제출", "작성", "이력서", "경영지도", "박다솜",
)

_RESUME_BONUS_KEYWORD = "이력서"
_RESUME_PENALTY_KEYWORDS: tuple[str, ...] = ("신청서", "동의서", "추천서")


def _parse_yyyymmdd_from_name(name: str) -> Optional[int]:
    """파일명/stem 에서 YYYYMMDD 를 추출한다(없으면 None)."""
    for m in re.finditer(r"(\d{4})[.\-_]?(\d{2})[.\-_]?(\d{2})", name):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            return y * 10000 + mo * 100 + d
    for m in re.finditer(r"(?<!\d)(\d{8})(?!\d)", name):
        raw = m.group(1)
        y, mo, d = int(raw[:4]), int(raw[4:6]), int(raw[6:8])
        if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            return y * 10000 + mo * 100 + d
    return None


def _score_resume_filename(path: Path, *, prefer_resume: bool) -> tuple[int, int, int]:
    """이력서 소스 선택용 파일명 점수: (이력서보너스, YYYYMMDD, 감점)."""
    if not prefer_resume:
        return 0, 0, 0
    stem = path.stem
    bonus = 3 if _RESUME_BONUS_KEYWORD in stem else 0
    date_val = _parse_yyyymmdd_from_name(stem) or 0
    penalty = sum(1 for kw in _RESUME_PENALTY_KEYWORDS if kw in stem)
    return bonus, date_val, penalty


def _score_source_candidate(
    path: Path,
    keywords: tuple[str, ...],
    *,
    prefer_resume: bool = False,
) -> tuple[int, int, int, int, float]:
    """소스 후보 점수: (키워드적중, 이력서보너스, YYYYMMDD, 감점, mtime)."""
    hits = sum(1 for kw in keywords if kw.lower() in path.stem.lower())
    bonus, date_val, penalty = _score_resume_filename(path, prefer_resume=prefer_resume)
    return hits, bonus, date_val, penalty, path.stat().st_mtime


def _source_sort_key(
    dry_run: int,
    kw_hits: int,
    resume_bonus: int,
    date_val: int,
    penalty: int,
    mtime: float,
) -> tuple[int, int, int, int, int, float]:
    """dry-run -> 이력서보너스 -> 파일명날짜 -> 키워드 -> 감점 -> mtime."""
    return dry_run, resume_bonus, date_val, kw_hits, -penalty, mtime


@dataclass
class SourcePickScore:
    path: str
    dry_run: int = 0
    keyword_hits: int = 0
    resume_bonus: int = 0
    filename_date: int = 0
    penalty: int = 0
    mtime: float = 0.0

    @property
    def sort_key(self) -> tuple[int, int, int, int, int, float]:
        return _source_sort_key(
            self.dry_run, self.keyword_hits, self.resume_bonus,
            self.filename_date, self.penalty, self.mtime,
        )


@dataclass
class SourcePickReport:
    pool_dir: str
    recommended: str
    recursive: bool
    prefer_resume: bool
    target: str
    scores: list[SourcePickScore] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "pool_dir": self.pool_dir,
            "recommended": self.recommended,
            "recursive": self.recursive,
            "prefer_resume": self.prefer_resume,
            "target": self.target,
            "scores": [
                {
                    "path": s.path,
                    "dry_run": s.dry_run,
                    "keyword_hits": s.keyword_hits,
                    "resume_bonus": s.resume_bonus,
                    "filename_date": s.filename_date,
                    "penalty": s.penalty,
                    "mtime": s.mtime,
                }
                for s in self.scores
            ],
        }


def list_source_pool(pool_dir: str | Path, *, recursive: bool = False) -> list[Path]:
    """완성본 A 후보 폴더에서 지원 확장자 파일을 나열한다."""
    folder = Path(pool_dir)
    if not folder.is_dir():
        raise FileNotFoundError(f"소스 풀 폴더가 없습니다: {folder}")

    files: list[Path] = []
    seen: set[str] = set()
    glob_fn = folder.rglob if recursive else folder.glob
    for pattern in _FORM_GLOB_PATTERNS:
        for path in sorted(glob_fn(pattern)):
            if path.suffix.lower() not in _SUPPORTED_EXTS:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            files.append(path)
    return files


def rank_source_pool(
    pool_dir: str | Path,
    target: Path | None = None,
    keywords: tuple[str, ...] | None = None,
    *,
    recursive: bool = False,
    prefer_resume: bool = False,
    use_dry_run: bool = True,
) -> SourcePickReport:
    """소스 풀 후보를 점수순으로 정렬해 추천 1개와 breakdown을 반환한다."""
    keywords = keywords or _DEFAULT_SOURCE_KEYWORDS
    pool = Path(pool_dir)
    candidates = list_source_pool(pool, recursive=recursive)
    scores: list[SourcePickScore] = []

    for path in candidates:
        hits, bonus, date_val, penalty, mtime = _score_source_candidate(
            path, keywords, prefer_resume=prefer_resume,
        )
        dry_run = 0
        if use_dry_run and target and path.resolve() == target.resolve():
            dry_run = 1
        scores.append(SourcePickScore(
            path=str(path),
            dry_run=dry_run,
            keyword_hits=hits,
            resume_bonus=bonus,
            filename_date=date_val,
            penalty=penalty,
            mtime=mtime,
        ))

    scores.sort(key=lambda s: s.sort_key, reverse=True)
    recommended = scores[0].path if scores else ""

    return SourcePickReport(
        pool_dir=str(pool),
        recommended=recommended,
        recursive=recursive,
        prefer_resume=prefer_resume,
        target=str(target) if target else "",
        scores=scores,
    )
