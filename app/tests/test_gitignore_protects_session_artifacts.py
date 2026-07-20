"""test_gitignore_protects_session_artifacts.py — 세션 아티팩트 커밋 유출 방지(L067).

배경 (L067)
-----------
워크트리에서 ``git add -A`` 로 커밋하면 OMC 훅이 만든 ``.omc/state/*`` 세션 파일이
PR 브랜치에 딸려 올라가는 사고가 있었다. 근본 방어는 **repo .gitignore 가 세션
아티팩트를 무시**하는 것 — 그러면 ``add -A`` 로도 스테이징되지 않는다.

이 테스트는 그 .gitignore 규칙이 사라지지 않도록 고정한다. 규칙이 삭제되면(부활
위험) 세션 파일이 다시 커밋될 수 있으므로 여기서 정직하게 실패한다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GITIGNORE = _REPO_ROOT / ".gitignore"

# add -A 로도 절대 스테이징되면 안 되는 세션 아티팩트 표본 경로.
_MUST_IGNORE = [
    ".omc/state/session.json",
    ".omc/notepad.md",
    ".claude/worktrees/foo/bar.txt",
]


@pytest.mark.skipif(not _GITIGNORE.is_file(), reason="repo .gitignore 없음(다른 머신/CI)")
def test_gitignore_has_session_artifact_rules() -> None:
    """.gitignore 에 세션 아티팩트(.omc/·.claude/worktrees/) 무시 규칙이 있어야 한다."""
    text = _GITIGNORE.read_text(encoding="utf-8")
    lines = {ln.strip() for ln in text.splitlines()}
    for rule in (".omc/", ".claude/worktrees/"):
        assert rule in lines, (
            f".gitignore 에 '{rule}' 무시 규칙이 사라졌다 — git add -A 시 세션 "
            "아티팩트가 커밋에 딸려 올라갈 수 있다(L067 재발)"
        )


@pytest.mark.skipif(shutil.which("git") is None, reason="git 미설치")
def test_session_artifacts_are_actually_ignored_by_git() -> None:
    """git check-ignore 로 세션 아티팩트가 실제로 무시되는지 권위 검증한다.

    .gitignore 텍스트만 보면 뒤에 오는 부정 규칙(!)이나 상위 규칙에 가려질 수
    있으므로, git 자체 판정으로 표본 경로가 전부 ignore 됨을 확인한다.
    """
    proc = subprocess.run(
        ["git", "check-ignore", *_MUST_IGNORE],
        cwd=str(_REPO_ROOT), capture_output=True, text=True,
    )
    if proc.returncode not in (0, 1):  # 0=일부 무시, 1=무시 없음; 그 외=환경오류
        pytest.skip(f"git check-ignore 실행 불가(rc={proc.returncode})")
    ignored = {ln.strip() for ln in proc.stdout.splitlines() if ln.strip()}
    not_ignored = [p for p in _MUST_IGNORE if p not in ignored]
    assert not not_ignored, (
        f"세션 아티팩트가 git 에서 무시되지 않음(커밋 유출 위험): {not_ignored}"
    )
