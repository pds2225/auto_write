"""PR·코드리뷰는 한국어. 요청 원문: v_up처럼 코드리뷰나 pr 한글로나오게해줘."""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PHRASE = "v_up처럼 코드리뷰나 pr 한글로나오게해줘"


def test_agents_requires_korean_pr_and_review() -> None:
    text = (_REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "## 9. PR·코드리뷰는 한국어" in text
    assert _PHRASE in text
    assert "PULL_REQUEST_TEMPLATE.md" in text
    assert "BUGBOT.md" in text


def test_claude_points_at_korean_pr_rule() -> None:
    text = (_REPO / "CLAUDE.md").read_text(encoding="utf-8")
    assert _PHRASE in text
    assert "AGENTS.md" in text
    assert "§9" in text


def test_bugbot_and_pr_template_are_korean() -> None:
    bugbot = (_REPO / ".cursor" / "BUGBOT.md").read_text(encoding="utf-8")
    template = (_REPO / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    assert _PHRASE in bugbot
    assert "한국어" in bugbot
    assert "## 요약" in template
    assert "## 변경" in template
    assert "## 확인" in template
    assert "한국어로 쓴다" in template
