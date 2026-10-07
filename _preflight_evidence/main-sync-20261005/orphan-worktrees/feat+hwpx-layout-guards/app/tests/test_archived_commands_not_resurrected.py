"""test_archived_commands_not_resurrected.py — 통폐합·아카이브된 커맨드 부활 방지.

배경 (2026-07-16 통폐합)
------------------------
중복 진입점이던 슬래시 커맨드 2개가 다른 커맨드에 흡수되어 아카이브(삭제)됐다:

  · ``/auto-write-quality``  → ``/improve-doc-quality`` 와 완전 중복이라 흡수
  · ``/auto-write-finalize`` → ``/auto-write-autopilot`` 로 흡수

아카이브 원본은 ``~/.claude/skills_archive/20260716-autowrite-consolidation/`` 에 보존.
문제는 **삭제만으로는 재생성을 못 막는다** — 다른 세션·자동개발이 옛 이름을 다시
만들면 "왜 이 커맨드가 또 있지" 하는 중복이 조용히 부활한다(사용자가 통폐합을 지시한
이유 자체가 소멸). 이 테스트가 그 부활을 기계적으로 막는다:

  ┌──────────────────────────────────────────────────────────────────┐
  │ 아카이브된 커맨드 파일은 repo 의 .claude/commands/ 에 다시                │
  │ 나타나면 안 된다. 나타나면 이 테스트가 정직하게 실패한다.               │
  └──────────────────────────────────────────────────────────────────┘

새로 아카이브하는 커맨드가 생기면 ``_ARCHIVED`` 에 (이름, 대체 경로)만 추가하면
그 커맨드도 자동으로 부활 감시 대상이 된다(단일 출처).

repo 밖(다른 머신·CI)에서 .claude/commands 가 없으면 조용히 skip 한다 — 이 가드는
repo-local 위생 불변식이라 대상 디렉터리가 있을 때만 의미가 있다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# app/tests/이_파일.py → parents[2] == repo 루트.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMANDS_DIR = _REPO_ROOT / ".claude" / "commands"

# (아카이브된 커맨드 파일명, 지금 대신 써야 하는 커맨드) — 부활 감시 단일 출처.
_ARCHIVED: dict[str, str] = {
    "auto-write-quality.md": "improve-doc-quality.md",
    "auto-write-finalize.md": "auto-write-autopilot.md",
}


def _has_commands_dir() -> bool:
    return _COMMANDS_DIR.is_dir()


@pytest.mark.skipif(not _has_commands_dir(), reason="repo .claude/commands 없음(다른 머신/CI)")
def test_archived_commands_not_resurrected() -> None:
    """아카이브된 커맨드가 .claude/commands/ 에 다시 나타나면 실패한다."""
    present = {p.name for p in _COMMANDS_DIR.glob("*.md")}
    resurrected = sorted(set(_ARCHIVED) & present)
    if resurrected:
        detail = "\n".join(
            f"  - {name} 는 2026-07-16 통폐합으로 아카이브됨 → 대신 {_ARCHIVED[name]} 사용"
            for name in resurrected
        )
        pytest.fail(
            "통폐합으로 아카이브된 커맨드가 부활했다(중복 진입점 재생성):\n"
            + detail
            + "\n아카이브 원본: ~/.claude/skills_archive/20260716-autowrite-consolidation/"
        )


@pytest.mark.skipif(not _has_commands_dir(), reason="repo .claude/commands 없음(다른 머신/CI)")
def test_replacement_commands_still_present() -> None:
    """부활을 막는 대신, 흡수처(대체 커맨드)는 반드시 살아 있어야 한다.

    대체 커맨드까지 사라지면 라우팅 목표가 없어져 '아카이브가 아니라 기능 소실'이
    된다 — 통폐합의 전제(기능은 대체처로 이관)를 이 양성 검사로 고정한다.
    """
    present = {p.name for p in _COMMANDS_DIR.glob("*.md")}
    missing_replacements = sorted(
        repl for repl in set(_ARCHIVED.values()) if repl not in present
    )
    assert not missing_replacements, (
        f"통폐합 대체 커맨드가 사라짐(기능 소실 위험): {missing_replacements} — "
        "이 커맨드들은 아카이브물의 기능을 이관받았으므로 유지돼야 한다"
    )
