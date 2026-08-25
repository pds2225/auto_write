"""Local PC remote control: checkout required, no overwrite, no real worker in tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from auto_write.services.local_pc_remote import (
    RemoteControlError,
    plan_remote_control,
    start_remote_control,
)
from auto_write.services.repo_clone import CloneError, require_existing_checkout
from local_pc_remote import main as remote_main

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


def _seed_repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True, capture_output=True)
    _git(seed, "config", "user.email", "rc-test@example.com")
    _git(seed, "config", "user.name", "Remote Control Test")
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "branch", "-M", "main")
    _git(seed, "push", "-u", "origin", "main")
    dest = tmp_path / "auto_write"
    subprocess.run(["git", "clone", "-b", "main", str(remote), str(dest)], check=True, capture_output=True)
    return dest


def test_require_existing_checkout_missing(tmp_path: Path):
    missing = tmp_path / "nope"
    with pytest.raises(CloneError, match="저장소 폴더가 없습니다"):
        require_existing_checkout(missing)


def test_plan_requires_checkout(tmp_path: Path):
    with pytest.raises(RemoteControlError, match="저장소 폴더가 없습니다"):
        plan_remote_control(tmp_path / "missing")


def test_plan_prefers_cursor_agent(tmp_path: Path, monkeypatch):
    dest = _seed_repo(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: "/fake/agent" if name == "agent" else None)
    plan = plan_remote_control(dest, url=str(tmp_path / "remote.git"))
    assert plan.backend == "cursor_worker"
    assert plan.command[0] == "/fake/agent"
    assert plan.command[1:4] == ["worker", "start", "--name"]
    assert "--worker-dir" in plan.command
    assert dest.resolve().as_posix() in {Path(plan.command[-1]).as_posix(), plan.command[-1]}
    assert "--force" not in plan.command


def test_plan_falls_back_to_claude(tmp_path: Path, monkeypatch):
    dest = _seed_repo(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: "/fake/claude" if name == "claude" else None)
    plan = plan_remote_control(dest, url=str(tmp_path / "remote.git"))
    assert plan.backend == "claude_remote_control"
    assert plan.command == ["/fake/claude", "remote-control", "--name", "auto_write"]


def test_plan_errors_when_no_backend(tmp_path: Path, monkeypatch):
    dest = _seed_repo(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RemoteControlError, match="agent"):
        plan_remote_control(dest, url=str(tmp_path / "remote.git"))


@pytest.mark.skipif(os.name == "nt", reason="non-Windows refusal only")
def test_start_refuses_non_windows_by_default(tmp_path: Path, monkeypatch):
    dest = _seed_repo(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: "/fake/agent" if name == "agent" else None)
    called = []
    with pytest.raises(RemoteControlError, match="Windows PC"):
        start_remote_control(dest, url=str(tmp_path / "remote.git"), runner=lambda *a, **k: called.append((a, k)))
    assert called == []


def test_start_launches_without_waiting(tmp_path: Path, monkeypatch):
    dest = _seed_repo(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: "/fake/agent" if name == "agent" else None)
    calls = []

    def fake_runner(command, cwd=None):
        calls.append((list(command), str(cwd)))
        return None

    plan = start_remote_control(
        dest,
        url=str(tmp_path / "remote.git"),
        allow_non_windows=True,
        wait=False,
        runner=fake_runner,
    )
    assert plan.backend == "cursor_worker"
    assert len(calls) == 1
    assert calls[0][0][1:3] == ["worker", "start"]
    assert Path(calls[0][1]).resolve() == dest.resolve()


def test_cli_json_plan(tmp_path: Path, monkeypatch, capsys):
    dest = _seed_repo(tmp_path)
    monkeypatch.setattr(shutil, "which", lambda name: "/fake/agent" if name == "agent" else None)
    assert remote_main(["--dest", str(dest), "--url", str(tmp_path / "remote.git"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["started"] is False
    assert payload["backend"] == "cursor_worker"
