"""test_hub_entrypoints.py — 허브 입구·라우팅 자산 존재 가드.

배경 (2026-08-11 허브·중복 정리)
--------------------------------
입구가 두 겹이다:

  · 에이전트: bizdoc-hub 스킬 + /bizdoc 커맨드
  · CLI: app/auto_write_hub.py

CLAUDE.md / bizdoc-hub 가 ``bizplan-orchestrator`` 를 가리키는데 스킬 파일이
없으면 라우팅이 끊긴다. 이 테스트는 **문서가 가리키는 입구가 실제로 존재**하는지
고정한다. 세부는 ``docs/BIZDOC_HUB_MAP.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SKILLS = _REPO / ".claude" / "skills"
_COMMANDS = _REPO / ".claude" / "commands"
_APP = _REPO / "app"

# (상대경로, 설명) — 허브 맵 SSOT 와 동기. 새 입구를 문서에 넣으면 여기도 추가.
_REQUIRED_SKILLS = (
    "bizdoc-hub/SKILL.md",
    "bizplan-orchestrator/SKILL.md",
    "announcement-form-analysis/SKILL.md",
    "cross-form-submission/SKILL.md",
    "document-quality-orchestrator/SKILL.md",
    "docx-hwp-conversion/SKILL.md",
    "hwpx-doctor/SKILL.md",
    "tech-framing-provenance/SKILL.md",
    "session-resume/SKILL.md",
    "user-bizdoc-playbook/SKILL.md",
    "user-applications-memory/SKILL.md",
    "ir-storyboard-pptx/SKILL.md",
)
_REQUIRED_COMMANDS = (
    "bizdoc.md",
    "improve-doc-quality.md",
    "auto-write-autopilot.md",
    "auto-write-bizplan.md",
    "auto-write-analyze.md",
)
_REQUIRED_FILES = (
    "docs/BIZDOC_HUB_MAP.md",
    "RESUME.md",
    "app/auto_write_hub.py",
    "docs/clients/dobonevi_card.md",
    "docs/clients/user_applications.md",
)


def _has_claude() -> bool:
    return _SKILLS.is_dir() and _COMMANDS.is_dir()


@pytest.mark.skipif(not _has_claude(), reason="repo .claude 없음")
def test_hub_skills_present() -> None:
    missing = [p for p in _REQUIRED_SKILLS if not (_SKILLS / p).is_file()]
    assert not missing, f"허브 라우팅 스킬 누락: {missing}"


@pytest.mark.skipif(not _has_claude(), reason="repo .claude 없음")
def test_hub_commands_present() -> None:
    missing = [p for p in _REQUIRED_COMMANDS if not (_COMMANDS / p).is_file()]
    assert not missing, f"허브 관련 커맨드 누락: {missing}"


def test_hub_map_and_cli_present() -> None:
    missing = [p for p in _REQUIRED_FILES if not (_REPO / p).is_file()]
    assert not missing, f"허브 맵/CLI/RESUME/카드/원장 누락: {missing}"


@pytest.mark.skipif(not _has_claude(), reason="repo .claude 없음")
def test_applications_memory_skill_forbids_google_docs() -> None:
    """수확 스킬은 정리본 Docs를 만들지 말라고 못 박아야 한다."""
    text = (_SKILLS / "user-applications-memory" / "SKILL.md").read_text(encoding="utf-8")
    assert "Google Docs" in text
    assert "채팅" in text
    assert "user_applications.md" in text


def test_auto_write_hub_subcommands() -> None:
    """CLI 허브는 env/diagnose/fill 세 하위명령이 문서 계약."""
    text = (_APP / "auto_write_hub.py").read_text(encoding="utf-8")
    for name in ('"env"', '"diagnose"', '"fill"'):
        assert name in text, f"auto_write_hub.py 에 {name} 서브커맨드 정의 없음"


@pytest.mark.skipif(not _has_claude(), reason="repo .claude 없음")
def test_stale_archived_names_not_in_hub_map() -> None:
    """허브 맵에 아카이브된 커맨드명을 '쓸 것'으로 다시 적지 않는다."""
    map_text = (_REPO / "docs" / "BIZDOC_HUB_MAP.md").read_text(encoding="utf-8")
    # 아카이브 절(§4) 언급은 허용 — 라우팅 구간에 죽은 이름을 권장하면 안 된다.
    before_archive, _, archive_and_after = map_text.partition("## 4. 아카이브됨")
    for dead in ("/auto-write-quality", "/auto-write-finalize"):
        assert dead not in before_archive, (
            f"BIZDOC_HUB_MAP 라우팅 구간에 아카이브 커맨드 {dead} 가 살아 있음"
        )
    assert "아카이브" in archive_and_after or "auto-write-quality" in archive_and_after
