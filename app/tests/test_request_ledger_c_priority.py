"""원장 C 최우선. 사업명은 원장·파일에 유지. 신청서 작성을 TASK LIST에 등록하지 않음."""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_LEDGER = _REPO / "docs" / "REQUEST_LEDGER.md"
_TASK = _REPO / "TASK.md"
_APPLICATIONS = _REPO / "docs" / "clients" / "user_applications.md"
_SKILL = _REPO / ".claude" / "skills" / "user-applications-memory" / "SKILL.md"
_AGENTS = _REPO / "AGENTS.md"

_LIST_LINE = re.compile(r"^\[(?:x| |~)\]\s+(T-\d{8}-\d{2}|AW-\d{3})\s+\|\s+(.+)$", re.M)
_WRITE_JOB = re.compile(r"신청서\s*작성|신청서·제출|제안서\s*작성|지원서\s*작성")

# Named 공고. A LIST one-liner that is "this grant's 신청서 작성" is forbidden.
_NAMED_GRANT_TASK_PATTERNS = (
    re.compile(r"STAR[\s-]?Exploration", re.I),
    re.compile(r"한난\s*온랩"),
    re.compile(r"소셜벤처\s*리그"),
    re.compile(r"KICKXUP", re.I),
    re.compile(r"KICXUP", re.I),
    re.compile(r"1인\s*창조"),
    re.compile(r"수출바우처"),
    re.compile(r"울산\s*전문상담"),
)

# Policy TASK itself talks about 신청서 작성; it is not a grant-writing job.
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
        "T-20260814-02",
        "T-20260816-03",
        "T-20260831-01",
        "T-20260831-02",
    }
)


def _frontmatter(text: str) -> str:
    parts = text.split("---", 2)
    assert len(parts) >= 3, "SKILL.md 에 YAML frontmatter 가 없다"
    return parts[1]


def test_ledger_c_comes_first_and_is_marked_most_important() -> None:
    text = _LEDGER.read_text(encoding="utf-8")
    assert "특정지원사업은 저장하지마" in text
    assert "원장 씨가 제일 중요" in text
    assert "아예 제외하라는게아니라" in text
    assert "task에등록하지마라고" in text
    c = text.find("## C.")
    b = text.find("## B.")
    a = text.find("## A.")
    assert c != -1 and b != -1 and a != -1
    assert c < b < a, "절 순서는 C → B → A 여야 한다"
    assert "제일 중요" in text[c : c + 120]


def test_ledger_section_a_may_contain_named_grants() -> None:
    text = _LEDGER.read_text(encoding="utf-8")
    a_start = text.find("## A.")
    assert a_start != -1
    section_a = text[a_start:]
    for needle in ("STAR-Exploration", "한난 온랩", "KICKXUP"):
        assert needle in section_a, f"원장 A에 {needle} 이(가) 있어야 한다"


def test_user_applications_md_may_contain_named_grants() -> None:
    assert _APPLICATIONS.is_file()
    text = _APPLICATIONS.read_text(encoding="utf-8")
    assert len(text.strip()) > 500
    assert "STAR-Exploration" in text
    assert "KICXUP" in text
    assert "Google Docs" in text


def test_task_list_has_no_named_grant_application_jobs() -> None:
    """LIST one-liner 이 명명 공고 신청서 작성이면 실패. 원장 A 사업명은 허용."""
    list_block = _TASK.read_text(encoding="utf-8").split("# 1. REPOSITORY", 1)[0]
    offenders: list[str] = []
    for match in _LIST_LINE.finditer(list_block):
        task_id, title = match.group(1), match.group(2)
        if task_id in _TASK_LIST_ALLOWLIST:
            continue
        named = any(p.search(title) for p in _NAMED_GRANT_TASK_PATTERNS)
        writing = _WRITE_JOB.search(title) is not None
        if named and writing:
            offenders.append(f"{task_id}: {title}")
    assert not offenders, "TASK LIST에 named 공고 신청서 작성 항목: " + "; ".join(
        offenders
    )


def test_t20260831_02_list_matches_clarification() -> None:
    list_block = _TASK.read_text(encoding="utf-8").split("# 1. REPOSITORY", 1)[0]
    line = None
    for match in _LIST_LINE.finditer(list_block):
        if match.group(1) == "T-20260831-02":
            line = match.group(2)
            break
    assert line is not None, "T-20260831-02 LIST 행이 없다"
    assert "신청서 작성을 TASK에 등록 금지" in line
    assert "파일에서 사업명 삭제 아님" in line


def test_t20260831_02_8_1_keeps_original_and_clarification() -> None:
    text = _TASK.read_text(encoding="utf-8")
    start = text.find("## T-20260831-02")
    assert start != -1
    end = text.find("\n# 9.", start)
    block = text[start:end]
    assert "특정지원사업은 저장하지마" in block
    assert "원장 씨가 제일 중요" in block
    assert "원장·파일에 사업명 저장 금지" in block
    assert "아예 제외하라는게아니라 특정지원사업신청서 작성하는일을 task에등록하지마라고" in block
    orig = block.find("특정지원사업은 저장하지마")
    clar = block.find("아예 제외하라는게아니라")
    assert orig != -1 and clar != -1 and orig < clar


def test_applications_skill_hooks_original_and_clarification() -> None:
    raw = _SKILL.read_text(encoding="utf-8")
    fm = _frontmatter(raw)
    assert "특정지원사업은 저장하지마" in fm
    assert "원장 씨가 제일 중요" in fm
    assert "원장·파일에 사업명 저장 금지" in fm
    assert "아예 제외하라는게아니라" in fm
    assert "task에등록하지마라고" in fm
    assert fm.find("특정지원사업은 저장하지마") < fm.lower().find("google docs")
    assert fm.find("task에등록하지마라고") < fm.lower().find("google docs")


def test_agents_section7_includes_original_and_clarification() -> None:
    text = _AGENTS.read_text(encoding="utf-8")
    sec = text.split("## 7. 스킬 훅", 1)[1]
    assert "특정지원사업은 저장하지마" in sec
    assert "원장 씨가 제일 중요" in sec
    assert "원장·파일에 사업명 저장 금지" in sec
    assert "아예 제외하라는게아니라 특정지원사업신청서 작성하는일을 task에등록하지마라고" in sec
