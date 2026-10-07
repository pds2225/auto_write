"""Wave D·E 규약 잠금 — 변환/COM 은 BLOCKED 정직, 에이전트 규약은 기계 검사.

L003 kill spy 는 test_lockdown_wave_bc.py. L005 픽셀·L050 생성은 mechanized 금지.
L067 는 .gitignore 가드(기존) + 실행 스크립트에 ``git add -A`` 명령 금지.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

from auto_write.services.doc_quality_ops import run_all
from auto_write.services.submission_gates import (
    l005_pixel_review_status,
    missing_pdf_pair,
    try_generate_sibling_pdf,
)

_REPO = Path(__file__).resolve().parents[2]
_COVERAGE = _REPO / "app" / "tests" / "lessons_coverage.json"
_PLAN = _REPO / "docs" / "LESSONS_LOCKDOWN_WAVES.md"
_AGENTS = _REPO / "AGENTS.md"

_GIT_ADD_ALL = re.compile(
    r"(?:^|[^\w-])git\s+add\s+(?:-A|--all)\b"
    r"""|(?:\[["']git["']\s*,\s*["']add["']\s*,\s*["'](?:-A|--all)["'])""",
    re.IGNORECASE,
)
_ALLOW_MARKERS = ("금지", "forbid", "do not", "never", "not git add")
_SCAN_GLOBS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "scripts/*",
    "app/scripts/*",
    "*.bat",
    "*.ps1",
    "*.sh",
    ".claude/hooks/*",
    "tools/injector/*.bat",
    "tools/injector/*.sh",
)


def _coverage() -> dict:
    return json.loads(_COVERAGE.read_text(encoding="utf-8"))


def _lesson(code: str) -> dict:
    prefix = code + " |"
    for row in _coverage()["lessons"]:
        if str(row["id"]).startswith(prefix):
            return row
    raise AssertionError(f"coverage JSON 에 {code} 없음")


def _strip_line_comment(path: Path, line: str) -> str:
    sfx = path.suffix.lower()
    stripped = line.lstrip()
    if sfx in {".py", ".sh", ".yml", ".yaml", ".js"} and stripped.startswith("#"):
        return ""
    if sfx == ".ps1" and stripped.startswith("#"):
        return ""
    if sfx == ".bat" and (
        stripped.lower().startswith("rem ") or stripped.startswith("::")
    ):
        return ""
    return line


def _executable_hits() -> list[str]:
    hits: list[str] = []
    seen: set[Path] = set()
    for pat in _SCAN_GLOBS:
        for path in _REPO.glob(pat):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            if "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, raw in enumerate(text.splitlines(), 1):
                code = _strip_line_comment(path, raw)
                if not code.strip():
                    continue
                lowered = code.lower()
                if any(m in lowered or m in code for m in _ALLOW_MARKERS):
                    continue
                if _GIT_ADD_ALL.search(code):
                    rel = path.relative_to(_REPO)
                    hits.append(f"{rel}:{i}: {raw.strip()}")
    return hits


def test_l005_stays_judgment_and_pixel_review_blocked_here():
    row = _lesson("L005")
    assert row["category"] == "judgment"
    status = l005_pixel_review_status()
    assert status["logic_review_is_verification"] is False
    if sys.platform != "win32":
        assert status["status"] == "BLOCKED"


def test_l050_stays_gap_and_generate_blocked_without_rhwp(tmp_path: Path):
    row = _lesson("L050")
    assert row["category"] == "gap"
    final = tmp_path / "신청서.hwpx"
    final.write_bytes(b"PK")
    assert missing_pdf_pair(final) is True
    gen = try_generate_sibling_pdf(final)
    assert gen.generated is False
    assert gen.blocked is True
    assert "BLOCKED" in gen.reason
    assert not (tmp_path / "신청서.pdf").exists()
    draft = tmp_path / "신청서_DRAFT.hwpx"
    draft.write_bytes(b"PK")
    skip = try_generate_sibling_pdf(draft)
    assert skip.skipped is True
    assert skip.generated is False
    (tmp_path / "신청서.pdf").write_bytes(b"%PDF")
    existed = try_generate_sibling_pdf(final)
    assert existed.skipped is True
    assert existed.generated is False
    assert existed.blocked is False


def test_l008_run_all_does_not_force_font_hierarchy():
    """L008 위계는 judgment. run_all 기본은 전문서 폰트 크기 강제 정규화를 켜지 않는다."""
    row = _lesson("L008")
    assert row["category"] == "judgment"
    default = inspect.signature(run_all).parameters["normalize_fonts"].default
    assert default is False


def test_l017_stays_mechanized_notebooklm():
    row = _lesson("L017")
    assert row["category"] == "mechanized"
    assert "image_apply" in row["guard_ref"]


def test_l003_stays_mechanized():
    row = _lesson("L003")
    assert row["category"] == "mechanized"
    assert "kill_hangul_processes" in row["guard_ref"]


def test_l067_no_git_add_all_in_executable_scripts():
    hits = _executable_hits()
    assert hits == [], "실행 스크립트/CI 에 git add -A 명령이 있다(L067):\n" + "\n".join(
        hits
    )


def test_l067_gitignore_guard_still_listed():
    row = _lesson("L067")
    assert row["category"] == "mechanized"
    assert "test_gitignore_protects_session_artifacts.py" in row["guard_ref"]


def test_wave_de_plan_has_convention_table_and_no_ask():
    text = _PLAN.read_text(encoding="utf-8")
    assert "승인 요청 금지" in text
    assert "닫힘 ≠ 머지" in text or "닫힘은 머지가 아니다" in text
    assert "L005" in text and "BLOCKED" in text
    assert "L050" in text
    assert "git add -A" in text
    assert "AGENTS.md" in text and "요청 원문" in text
    assert "## Wave D" in text or "## Wave D·E" in text


def test_agents_section7_skill_hook_still_present():
    text = _AGENTS.read_text(encoding="utf-8")
    assert "## 7. 스킬 훅" in text
    assert "요청 원문" in text


def test_coverage_counts_unchanged_by_de_convention():
    counts = _coverage()["counts"]
    assert counts["mechanized"] == 66
    assert counts["gap"] == 1
    assert counts["judgment"] == 84
    assert counts["total"] == 151
    assert _lesson("L050")["id"].startswith("L050")
