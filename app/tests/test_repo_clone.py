"""Safe git clone: overwrite 금지, 같은 저장소면 재사용."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from auto_write.services.repo_clone import (
    CloneError,
    clone_repository,
    normalize_github_url,
    same_repository,
)
from clone_repo import main as clone_main

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git executable required")


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return (proc.stdout or "").strip()


def _bare_and_seed(tmp_path: Path) -> tuple[Path, str]:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True, capture_output=True)
    _git(seed, "config", "user.email", "clone-test@example.com")
    _git(seed, "config", "user.name", "Clone Test")
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "branch", "-M", "main")
    _git(seed, "push", "-u", "origin", "main")
    sha = _git(seed, "rev-parse", "HEAD")
    return remote, sha


def test_normalize_github_url_strips_credentials_and_git_suffix():
    assert normalize_github_url(
        "https://x-access-token:secret@github.com/pds2225/auto_write.git"
    ) == "https://github.com/pds2225/auto_write"
    assert same_repository(
        "git@github.com:pds2225/auto_write.git",
        "https://github.com/pds2225/auto_write",
    )


def test_clone_into_new_folder(tmp_path: Path):
    remote, sha = _bare_and_seed(tmp_path)
    dest = tmp_path / "fresh"
    result = clone_repository(dest, url=str(remote), branch="main")
    assert result.action == "cloned"
    assert result.sha == sha
    assert result.branch == "main"
    assert (dest / "README.md").read_text(encoding="utf-8") == "seed\n"


def test_clone_into_empty_existing_folder(tmp_path: Path):
    remote, sha = _bare_and_seed(tmp_path)
    dest = tmp_path / "empty"
    dest.mkdir()
    result = clone_repository(dest, url=str(remote), branch="main")
    assert result.action == "cloned"
    assert result.sha == sha
    assert (dest / "README.md").is_file()


def test_clone_is_idempotent_for_same_repo(tmp_path: Path):
    remote, sha = _bare_and_seed(tmp_path)
    dest = tmp_path / "once"
    first = clone_repository(dest, url=str(remote), branch="main")
    marker = dest / "local_only.txt"
    marker.write_text("keep me\n", encoding="utf-8")
    second = clone_repository(dest, url=str(remote), branch="main")
    assert first.action == "cloned"
    assert second.action == "already_present"
    assert second.sha == sha
    assert marker.read_text(encoding="utf-8") == "keep me\n"


def test_clone_refuses_nonempty_non_git_folder(tmp_path: Path):
    remote, _ = _bare_and_seed(tmp_path)
    dest = tmp_path / "occupied"
    dest.mkdir()
    keep = dest / "notes.txt"
    keep.write_text("do not delete\n", encoding="utf-8")
    with pytest.raises(CloneError, match="비어 있지 않습니다"):
        clone_repository(dest, url=str(remote), branch="main")
    assert keep.read_text(encoding="utf-8") == "do not delete\n"


def test_clone_refuses_different_existing_repo(tmp_path: Path):
    remote, _ = _bare_and_seed(tmp_path)
    other_remote = tmp_path / "other.git"
    other_seed = tmp_path / "other_seed"
    subprocess.run(["git", "init", "--bare", str(other_remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(other_remote), str(other_seed)], check=True, capture_output=True)
    _git(other_seed, "config", "user.email", "clone-test@example.com")
    _git(other_seed, "config", "user.name", "Clone Test")
    (other_seed / "OTHER.md").write_text("other\n", encoding="utf-8")
    _git(other_seed, "add", "OTHER.md")
    _git(other_seed, "commit", "-m", "other")
    _git(other_seed, "branch", "-M", "main")
    _git(other_seed, "push", "-u", "origin", "main")

    dest = tmp_path / "mismatch"
    clone_repository(dest, url=str(other_remote), branch="main")
    with pytest.raises(CloneError, match="다른 저장소"):
        clone_repository(dest, url=str(remote), branch="main")
    assert (dest / "OTHER.md").is_file()


def test_clone_rejects_option_like_branch_name(tmp_path: Path):
    remote, _ = _bare_and_seed(tmp_path)
    with pytest.raises(CloneError, match="브랜치명"):
        clone_repository(tmp_path / "bad", url=str(remote), branch="--force")


def test_cli_json_clone_and_already_present(tmp_path: Path, capsys):
    remote, sha = _bare_and_seed(tmp_path)
    dest = tmp_path / "cli_dest"
    assert clone_main(["--dest", str(dest), "--url", str(remote), "--branch", "main", "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["ok"] is True
    assert first["action"] == "cloned"
    assert first["sha"] == sha

    assert clone_main(["--dest", str(dest), "--url", str(remote), "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["ok"] is True
    assert second["action"] == "already_present"


def test_cli_error_does_not_wipe_occupied_folder(tmp_path: Path, capsys):
    remote, _ = _bare_and_seed(tmp_path)
    dest = tmp_path / "keep"
    dest.mkdir()
    (dest / "stay.txt").write_text("stay\n", encoding="utf-8")
    assert clone_main(["--dest", str(dest), "--url", str(remote), "--json"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert (dest / "stay.txt").read_text(encoding="utf-8") == "stay\n"
