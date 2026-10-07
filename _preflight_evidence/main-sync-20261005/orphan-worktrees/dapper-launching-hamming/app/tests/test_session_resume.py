"""session-resume 스킬이 실제로 있고, 일회성 배너 스킬/후크는 없는지를 고정."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SKILL = _REPO / ".claude" / "skills" / "session-resume" / "SKILL.md"
_HOOK = _REPO / ".claude" / "hooks" / "session_resume_hook.js"
_SETTINGS = _REPO / ".claude" / "settings.json"
_CLAUDE = _REPO / "CLAUDE.md"


def _run(prompt: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(_HOOK)],
        input=json.dumps(
            {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
        ),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        check=False,
    )


def test_session_resume_skill_exists_where_claude_points() -> None:
    assert "session-resume" in _CLAUDE.read_text(encoding="utf-8")
    assert _SKILL.is_file()
    text = _SKILL.read_text(encoding="utf-8")
    assert "RESUME.md" in text
    assert "세션마무리" in text
    assert "일회성" in text


def test_one_off_banner_skill_was_withdrawn() -> None:
    assert not (_REPO / ".claude" / "skills" / "promo-banner-localize" / "SKILL.md").is_file()
    assert not (_REPO / ".claude" / "hooks" / "promo_banner_guard.js").is_file()
    settings = _SETTINGS.read_text(encoding="utf-8")
    assert "promo_banner_guard" not in settings
    assert "session_resume_hook.js" in settings


def test_close_prompt_injects_skill() -> None:
    proc = _run("세션마무리")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "session-resume" in data["hookSpecificOutput"]["additionalContext"]


def test_unrelated_prompt_is_silent() -> None:
    proc = _run("사업계획서 품질 점수만 보여줘")
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
