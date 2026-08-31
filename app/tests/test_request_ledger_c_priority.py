"""원장 C가 최우선. 특정 지원사업 이름 표를 저장하지 않는다."""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_LEDGER = _REPO / "docs" / "REQUEST_LEDGER.md"
_SKILL = _REPO / ".claude" / "skills" / "user-applications-memory" / "SKILL.md"


def test_ledger_c_comes_first_and_is_marked_most_important() -> None:
    text = _LEDGER.read_text(encoding="utf-8")
    assert "특정지원사업은 저장하지마" in text
    assert "원장 씨가 제일 중요" in text
    c = text.find("## C.")
    b = text.find("## B.")
    a = text.find("## A.")
    assert c != -1 and b != -1 and a != -1
    assert c < b < a, "절 순서는 C → B → A 여야 한다"
    assert "제일 중요" in text[c : c + 80]


def test_ledger_does_not_store_named_grant_rows() -> None:
    text = _LEDGER.read_text(encoding="utf-8")
    for needle in (
        "STAR-Exploration",
        "소셜벤처 리그",
        "KICKXUP",
        "한난 온랩",
        "1인 창조",
        "K-네비 2026",
    ):
        assert needle not in text, f"원장에 특정 지원사업이 남아 있다: {needle}"


def test_applications_skill_hooks_original_request() -> None:
    raw = _SKILL.read_text(encoding="utf-8")
    fm = raw.split("---", 2)[1]
    assert "특정지원사업은 저장하지마" in fm
    assert "원장 씨가 제일 중요" in fm
    assert fm.find("특정지원사업은 저장하지마") < fm.lower().find("google docs")
