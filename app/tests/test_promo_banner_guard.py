"""promo_banner_guard.js — 배너 후크가 매 프롬프트에 안 떠들고, 16:9 거짓완료만 잡는지."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_HOOK = _REPO / ".claude" / "hooks" / "promo_banner_guard.js"
_SETTINGS = _REPO / ".claude" / "settings.json"


def _run(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(_REPO),
        check=False,
    )


def _png(path: Path, size: tuple[int, int]) -> None:
    from PIL import Image

    Image.new("RGB", size, (255, 255, 255)).save(path)


def test_hook_file_registered() -> None:
    assert _HOOK.is_file()
    settings = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    blob = json.dumps(settings)
    assert "promo_banner_guard.js" in blob
    assert "GenerateImage" in blob


def test_unrelated_prompt_is_silent() -> None:
    proc = _run(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "사업계획서 품질 점수만 보여줘",
        }
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_banner_prompt_injects_skill() -> None:
    proc = _run(
        {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "K-네비 배너 영문으로 바꾸고 16:9 만들어줘",
        }
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert "promo-banner-localize" in ctx
    assert "1536" in ctx
    assert data["continue"] is True


@pytest.mark.parametrize(
    "prompt",
    [
        "케이내비 한글 버전도 똑같이",
        "왼쪽 상단 숫자 빼줘",
        "16대9버전 만들어줘 한글 영어 둘다",
    ],
)
def test_keyword_variants_fire(prompt: str) -> None:
    proc = _run({"hook_event_name": "UserPromptSubmit", "prompt": prompt})
    assert proc.returncode == 0
    assert "promo-banner-localize" in proc.stdout


def test_generateimage_32_is_not_sixteen_nine(tmp_path: Path) -> None:
    png = tmp_path / "fake_16x9.png"
    _png(png, (1536, 1024))
    proc = _run(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "GenerateImage",
            "tool_input": {"aspect_ratio": "16:9", "filename": str(png)},
            "cwd": str(tmp_path),
        }
    )
    assert proc.returncode == 0
    ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "1536" in ctx
    assert "1920" in ctx
    assert "완료로 보고하지 마라" in ctx


def test_true_sixteen_nine_is_silent(tmp_path: Path) -> None:
    png = tmp_path / "ok.png"
    _png(png, (1920, 1080))
    proc = _run(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "GenerateImage",
            "tool_input": {"aspect_ratio": "16:9", "filename": str(png)},
        }
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
