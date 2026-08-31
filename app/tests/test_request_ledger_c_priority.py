"""원장 C 최우선. 사업명은 원장·파일에 저장. TASK에 named 신청서 작성 등록 금지."""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_LEDGER = _REPO / "docs" / "REQUEST_LEDGER.md"
_TASK = _REPO / "TASK.md"
_APPLICATIONS = _REPO / "docs" / "clients" / "user_applications.md"

_LIST_LINE = re.compile(r"^\[(?:x| |~)\]\s+(T-\d{8}-\d{2}|AW-\d{3})\s+\|\s+(.+)$", re.M)

# Named grant application jobs must not appear as new TASK LIST titles.
_NAMED_GRANT_TASK_PATTERNS = (
    re.compile(r"STAR[\s-]?Exploration", re.I),
    re.compile(r"스케일업\s*팁스"),
    re.compile(r"딥테크\s*팁스"),
    re.compile(r"\bTIPS\b"),
    re.compile(r"초격차"),
    re.compile(r"K-Global", re.I),
    re.compile(r"한난\s*온랩"),
    re.compile(r"소셜벤처\s*리그"),
    re.compile(r"KICKXUP", re.I),
)

# Pre-existing LIST rows allowed even if they mention grants indirectly.
_TASK_LIST_ALLOWLIST = frozenset(
    {
        "AW-001",
        "AW-002",
        "AW-003",
        "AW-004",
        "AW-005",
        "AW-006",
        "AW-007",
        "AW-008",
        "AW-009",
        "T-20260831-01",
        "T-20260816-03",
        "T-20260814-02",
    }
)


def test_ledger_c_comes_first_and_is_marked_most_important() -> None:
    text = _LEDGER.read_text(encoding="utf-8")
    assert "특정지원사업은 저장하지마" in text
    assert "원장 씨가 제일 중요" in text
    c = text.find("## C.")
    b = text.find("## B.")
    a = text.find("## A.")
    assert c != -1 and b != -1 and a != -1
    assert c < b < a, "절 순서는 C → B → A 여야 한다"
    assert "제일 중요" in text[c : c + 120]


def test_ledger_section_a_still_has_named_grants() -> None:
    text = _LEDGER.read_text(encoding="utf-8")
    a_start = text.find("## A.")
    assert a_start != -1
    section_a = text[a_start:]
    assert any(
        needle in section_a
        for needle in ("STAR-Exploration", "STAR Exploration", "스케일업", "KICKXUP")
    ), "원장 A에 named 지원사업이 최소 1건 있어야 한다"


def test_task_list_has_no_named_grant_application_jobs() -> None:
    task_text = _TASK.read_text(encoding="utf-8")
    offenders: list[str] = []
    for match in _LIST_LINE.finditer(task_text):
        task_id, title = match.group(1), match.group(2)
        if task_id in _TASK_LIST_ALLOWLIST:
            continue
        if any(p.search(title) for p in _NAMED_GRANT_TASK_PATTERNS):
            offenders.append(f"{task_id}: {title}")
    assert not offenders, "TASK LIST에 named 지원사업 신청서 작성 항목: " + "; ".join(
        offenders
    )


def test_user_applications_md_exists_and_is_substantive() -> None:
    assert _APPLICATIONS.is_file()
    text = _APPLICATIONS.read_text(encoding="utf-8")
    assert len(text.strip()) > 500
    assert "STAR" in text or "도보네비" in text
