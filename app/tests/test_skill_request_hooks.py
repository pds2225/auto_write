"""스킬 훅 = 요청 원문. 자동 미발동이면 효용 감소 (AGENTS.md §7)."""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SKILL = _REPO / ".claude" / "skills" / "tech-framing-provenance" / "SKILL.md"
_AGENTS = _REPO / "AGENTS.md"
_CLAUDE = _REPO / "CLAUDE.md"


def _frontmatter(text: str) -> str:
    parts = text.split("---", 2)
    assert len(parts) >= 3, "SKILL.md 에 YAML frontmatter 가 없다"
    return parts[1]


def test_agents_skill_hook_rule_present() -> None:
    text = _AGENTS.read_text(encoding="utf-8")
    assert "## 7. 스킬 훅" in text
    assert "요청 원문" in text
    assert "자동으로" in text
    assert "효용" in text


def test_claude_md_points_to_skill_hook_rule() -> None:
    text = _CLAUDE.read_text(encoding="utf-8")
    assert "요청 원문" in text
    assert "AGENTS.md" in text
    assert "효용" in text


def test_tech_framing_skill_uses_original_request_as_hook() -> None:
    """이 스킬을 만들게 한 요청 원문이 description 훅 최우선이어야 한다."""
    raw = _SKILL.read_text(encoding="utf-8")
    fm = _frontmatter(raw)
    for needle in (
        "star experation",
        "어디서 가져온거지",
        "위성항법",
        "반드시 사용",
    ):
        assert needle in fm, f"description 훅에 요청 원문 {needle!r} 없음"
    # 스킬명만 있고 원문이 뒤에 묻히면 실패 — 원문이 description 앞쪽에 온다.
    assert fm.lower().find("star experation") < fm.lower().find("gnss 출처")
