"""origin URL 기반 canonical repo 이름."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote


class RepoNameError(ValueError):
    """origin 없음·모호·파싱 실패 시 fail-closed."""


_SSH_RE = re.compile(r"^(?:ssh://)?git@([^:]+):(.+)$")
_GIT_SUFFIX = re.compile(r"\.git$", re.IGNORECASE)


def parse_repo_name_from_origin_url(origin_url: str) -> str:
    """git remote origin URL → 저장소 basename(.git 제거)."""
    raw = (origin_url or "").strip()
    if not raw:
        raise RepoNameError("origin URL이 비어 있습니다.")

    path_part = ""
    ssh = _SSH_RE.match(raw)
    if ssh:
        path_part = ssh.group(2)
    else:
        parsed = urlparse(raw)
        if parsed.scheme and parsed.path:
            path_part = parsed.path
        else:
            # scp-like without git@ already handled; try last path segment
            path_part = raw.replace("\\", "/")

    path_part = unquote(path_part).rstrip("/")
    if not path_part:
        raise RepoNameError(f"origin URL에서 경로를 파싱할 수 없습니다: {origin_url!r}")

    name = path_part.split("/")[-1]
    name = _GIT_SUFFIX.sub("", name).strip()
    if not name or "/" in name or "\\" in name:
        raise RepoNameError(f"origin URL에서 repo 이름을 확정할 수 없습니다: {origin_url!r}")
    return name


def get_origin_url(cwd: Path | None = None) -> str:
    root = Path(cwd) if cwd else Path.cwd()
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise RepoNameError(f"git 실행 실패: {exc}") from exc
    if proc.returncode != 0:
        raise RepoNameError("origin remote가 없거나 조회에 실패했습니다.")
    urls = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not urls:
        raise RepoNameError("origin URL이 비어 있습니다.")
    if len(urls) > 1:
        raise RepoNameError("origin URL 후보가 둘 이상입니다.")
    return urls[0]


def canonical_repo_name(cwd: Path | None = None) -> tuple[str, str]:
    """(repo_name, origin_url). worktree 폴더명이 아니라 origin basename."""
    origin = get_origin_url(cwd)
    return parse_repo_name_from_origin_url(origin), origin
