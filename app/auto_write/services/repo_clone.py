"""Safe, idempotent git clone for auto_write.

Never overwrites an existing folder. If the destination is already this
repository, reports already_present instead of cloning again.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CLONE_URL = "https://github.com/pds2225/auto_write.git"
DEFAULT_WINDOWS_DEST = Path(r"D:\auto_write")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class CloneError(RuntimeError):
    pass


@dataclass(frozen=True)
class CloneResult:
    dest: str
    url: str
    sha: str
    branch: str
    action: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_github_url(url: str) -> str:
    raw = (url or "").strip()
    raw = re.sub(r"^git@github\.com:", "https://github.com/", raw, flags=re.I)
    raw = re.sub(r"^ssh://git@github\.com/", "https://github.com/", raw, flags=re.I)
    raw = re.sub(r"^https?://[^/@]+@github\.com/", "https://github.com/", raw, flags=re.I)
    raw = re.sub(r"^https?://github\.com/", "https://github.com/", raw, flags=re.I)
    raw = raw.rstrip("/")
    if raw.lower().endswith(".git"):
        raw = raw[:-4]
    return raw.lower()


def same_repository(left: str, right: str) -> bool:
    return normalize_github_url(left) == normalize_github_url(right)


def default_dest() -> Path:
    if Path("D:/").exists():
        return DEFAULT_WINDOWS_DEST
    raise CloneError("대상 폴더를 --dest 로 지정하세요. (Windows 기본값: D:\\auto_write)")


def _run_git(*args: str, cwd: Path | None = None, timeout: int = 60) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "git command failed").strip()
        raise CloneError(message[:1200])
    return (proc.stdout or "").strip()


def _is_git_repo(path: Path) -> bool:
    git_dir = path / ".git"
    return git_dir.is_dir() or git_dir.is_file()


def _origin_url(path: Path) -> str:
    return _run_git("remote", "get-url", "origin", cwd=path)


def _inspect_repo(path: Path, url: str) -> CloneResult:
    sha = _run_git("rev-parse", "HEAD", cwd=path)
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=path)
    return CloneResult(
        dest=str(path),
        url=url,
        sha=sha,
        branch=branch,
        action="already_present",
        message=f"이미 같은 저장소가 있습니다: {path}. 덮어쓰지 않았습니다.",
    )


def clone_repository(
    dest: Path | str | None = None,
    url: str = DEFAULT_CLONE_URL,
    *,
    branch: str | None = None,
) -> CloneResult:
    """Clone ``url`` into ``dest`` without deleting or overwriting files."""
    if shutil.which("git") is None:
        raise CloneError("Git이 설치되어 있지 않습니다. https://git-scm.com/download/win 에서 설치하세요.")

    target = Path(dest) if dest is not None else default_dest()
    target = target.expanduser()
    try:
        target = target.resolve()
    except OSError as exc:
        raise CloneError(f"대상 경로를 확인할 수 없습니다: {target}") from exc

    source = (url or DEFAULT_CLONE_URL).strip() or DEFAULT_CLONE_URL
    if branch:
        branch = branch.strip()
        if not branch or not _BRANCH_RE.match(branch) or branch.startswith("-"):
            raise CloneError(f"허용되지 않는 브랜치명입니다: {branch}")

    if target.exists():
        if not target.is_dir():
            raise CloneError(f"대상이 폴더가 아닙니다: {target}")
        if _is_git_repo(target):
            existing = _origin_url(target)
            if not same_repository(existing, source):
                raise CloneError(
                    f"다른 저장소가 이미 있습니다: {existing}. 덮어쓰지 않습니다."
                )
            return _inspect_repo(target, source)
        if any(target.iterdir()):
            raise CloneError(
                f"대상 폴더가 비어 있지 않습니다: {target}. 기존 파일을 지우거나 덮어쓰지 않습니다."
            )

    target.parent.mkdir(parents=True, exist_ok=True)
    clone_args = ["clone"]
    if branch:
        clone_args += ["--branch", branch]
    clone_args += ["--", source, str(target)]
    _run_git(*clone_args, timeout=300)
    sha = _run_git("rev-parse", "HEAD", cwd=target)
    head_branch = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=target)
    return CloneResult(
        dest=str(target),
        url=source,
        sha=sha,
        branch=head_branch,
        action="cloned",
        message=f"clone 완료: {target} ({head_branch} {sha[:8]})",
    )
