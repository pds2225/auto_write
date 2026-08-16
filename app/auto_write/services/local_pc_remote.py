"""Plan and start local-PC remote control for auto_write.

This cloud agent cannot reach D:\\auto_write. The Windows PC must run
``remote_control.bat`` (or this module with ``--start``) so Cursor My Machines
or Claude Code Remote Control can attach to that checkout.

Never force-push, never delete the checkout, never bind the operator console
to a public interface.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from auto_write.services.repo_clone import (
    DEFAULT_CLONE_URL,
    DEFAULT_WINDOWS_DEST,
    CloneError,
    default_dest,
    require_existing_checkout,
)

WORKER_NAME = "auto-write-pc"
CLAUDE_SESSION_NAME = "auto_write"
CURSOR_INSTALL = "irm 'https://cursor.com/install?win32=true' | iex"
CLAUDE_HINT = "Claude Code를 설치한 뒤 D:\\auto_write 에서 claude remote-control"


class RemoteControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemotePlan:
    dest: str
    url: str
    sha: str
    branch: str
    backend: str
    command: list[str]
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


def _resolve_dest(dest: Path | str | None) -> Path:
    if dest is not None:
        return Path(dest)
    try:
        return default_dest()
    except CloneError as exc:
        raise RemoteControlError(
            "로컬 PC 경로를 --dest 로 지정하세요. Windows 기본값은 D:\\auto_write 입니다."
        ) from exc


def _which_backend() -> tuple[str, str]:
    agent = shutil.which("agent")
    if agent:
        return "cursor_worker", agent
    claude = shutil.which("claude")
    if claude:
        return "claude_remote_control", claude
    raise RemoteControlError(
        "로컬 PC에 Cursor CLI(agent) 또는 Claude Code(claude)가 없습니다. "
        f"Cursor 설치(PowerShell): {CURSOR_INSTALL}  그다음 agent login. "
        f"{CLAUDE_HINT}"
    )


def plan_remote_control(
    dest: Path | str | None = None,
    url: str = DEFAULT_CLONE_URL,
) -> RemotePlan:
    target = _resolve_dest(dest)
    try:
        checkout = require_existing_checkout(target, url=url)
    except CloneError as exc:
        raise RemoteControlError(str(exc)) from exc

    backend, executable = _which_backend()
    dest_path = checkout.dest
    if backend == "cursor_worker":
        command = [
            executable,
            "worker",
            "start",
            "--name",
            WORKER_NAME,
            "--worker-dir",
            dest_path,
        ]
        message = (
            f"Cursor My Machines 워커를 시작합니다: {WORKER_NAME} @ {dest_path}. "
            "이 창을 닫지 마세요. 연결 후 cursor.com/agents 에서 이 PC를 고르면 됩니다."
        )
    else:
        command = [executable, "remote-control", "--name", CLAUDE_SESSION_NAME]
        message = (
            f"Claude Code Remote Control을 시작합니다: {dest_path}. "
            "표시된 URL/QR로 접속하세요. 이 창을 닫지 마세요."
        )
    return RemotePlan(
        dest=dest_path,
        url=checkout.url,
        sha=checkout.sha,
        branch=checkout.branch,
        backend=backend,
        command=command,
        message=message,
    )


def start_remote_control(
    dest: Path | str | None = None,
    url: str = DEFAULT_CLONE_URL,
    *,
    allow_non_windows: bool = False,
    wait: bool = True,
    runner=None,
) -> RemotePlan:
    if os.name != "nt" and not allow_non_windows:
        raise RemoteControlError(
            "로컬 PC 리모트 컨트롤은 Windows PC에서 remote_control.bat 을 실행해야 합니다. "
            "이 클라우드 환경은 D:\\auto_write 에 접속할 수 없습니다."
        )
    plan = plan_remote_control(dest, url=url)
    if wait:
        subprocess.run(plan.command, cwd=plan.dest, check=False)
    else:
        launch = runner or subprocess.Popen
        launch(plan.command, cwd=plan.dest)
    return plan
