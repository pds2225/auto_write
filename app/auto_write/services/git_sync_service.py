from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


class GitSyncError(RuntimeError):
    pass


@dataclass
class GitSyncSnapshot:
    repository: str
    branch: str
    base_branch: str
    local_sha: str
    remote_sha: str
    base_remote_sha: str
    ahead: int
    behind: int
    dirty_count: int
    status: str
    last_error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class GitSyncService:
    """Safe local-git bridge used by the web operator console.

    GitHub remains the source of truth. The service never force-pushes and never
    discards a dirty working tree.
    """

    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[3])
        self.remote = os.getenv("AUTO_WRITE_GIT_REMOTE", "origin")
        self.base_branch = os.getenv("AUTO_WRITE_GIT_BASE_BRANCH", "master")
        self.repository = os.getenv("AUTO_WRITE_GITHUB_REPOSITORY", "pds2225/auto_write")
        self.write_mode = os.getenv("AUTO_WRITE_GIT_WRITE_MODE", "branch-pr").strip().lower()

    def _run(self, *args: str, check: bool = True, timeout: int = 60) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if check and proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "git command failed").strip()
            raise GitSyncError(message[:1200])
        return (proc.stdout or "").strip()

    def _ref_exists(self, ref: str) -> bool:
        return subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=self.repo_root,
            capture_output=True,
            timeout=15,
        ).returncode == 0

    def fetch(self) -> None:
        self._run("fetch", "--prune", self.remote, timeout=120)

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def local_sha(self) -> str:
        return self._run("rev-parse", "HEAD")

    def remote_sha(self, branch: str | None = None) -> str:
        branch = branch or self.current_branch()
        ref = f"{self.remote}/{branch}"
        return self._run("rev-parse", ref, check=False) if self._ref_exists(ref) else ""

    def base_remote_sha(self) -> str:
        ref = f"{self.remote}/{self.base_branch}"
        return self._run("rev-parse", ref, check=False) if self._ref_exists(ref) else ""

    def dirty_paths(self) -> list[str]:
        raw = self._run("status", "--porcelain", check=False)
        return [line for line in raw.splitlines() if line.strip()]

    def snapshot(self, *, fetch: bool = False) -> GitSyncSnapshot:
        last_error = ""
        if fetch:
            try:
                self.fetch()
            except Exception as exc:
                last_error = str(exc)
        try:
            branch = self.current_branch()
            local = self.local_sha()
            remote = self.remote_sha(branch)
            base_remote = self.base_remote_sha()
            dirty = self.dirty_paths()
            ahead = behind = 0
            if remote:
                counts = self._run("rev-list", "--left-right", "--count", f"{local}...{remote}", check=False)
                parts = counts.replace("\t", " ").split()
                if len(parts) >= 2:
                    ahead, behind = int(parts[0]), int(parts[1])
            if last_error:
                status = "FETCH_ERROR"
            elif dirty:
                status = "LOCAL_CHANGES"
            elif not remote:
                status = "NO_REMOTE_BRANCH"
            elif ahead and behind:
                status = "CONFLICT"
            elif behind:
                status = "REMOTE_AHEAD"
            elif ahead:
                status = "LOCAL_AHEAD"
            else:
                status = "SYNCED"
            return GitSyncSnapshot(
                repository=self.repository,
                branch=branch,
                base_branch=self.base_branch,
                local_sha=local,
                remote_sha=remote,
                base_remote_sha=base_remote,
                ahead=ahead,
                behind=behind,
                dirty_count=len(dirty),
                status=status,
                last_error=last_error,
            )
        except Exception as exc:
            return GitSyncSnapshot(
                repository=self.repository,
                branch="",
                base_branch=self.base_branch,
                local_sha="",
                remote_sha="",
                base_remote_sha="",
                ahead=0,
                behind=0,
                dirty_count=0,
                status="GIT_ERROR",
                last_error=str(exc)[:1200],
            )

    def sync_from_remote(self) -> GitSyncSnapshot:
        self.fetch()
        snap = self.snapshot(fetch=False)
        if snap.dirty_count:
            raise GitSyncError("로컬 변경사항이 있어 자동 동기화를 중단했습니다.")
        if snap.status == "CONFLICT":
            raise GitSyncError("로컬과 원격이 서로 갈라져 있어 fast-forward 할 수 없습니다.")
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{snap.branch}", timeout=120)
        return self.snapshot(fetch=False)

    def return_to_base(self) -> GitSyncSnapshot:
        """Return from a web change branch to the configured base branch safely."""
        if self.dirty_paths():
            raise GitSyncError("로컬 변경사항이 있어 기준 브랜치로 전환할 수 없습니다.")
        self.fetch()
        if self.current_branch() != self.base_branch:
            self._run("switch", self.base_branch)
        snap = self.snapshot(fetch=False)
        if snap.dirty_count:
            raise GitSyncError("기준 브랜치 전환 후 작업 트리가 깨끗하지 않습니다.")
        if snap.status == "CONFLICT":
            raise GitSyncError("기준 브랜치가 원격과 diverged 상태입니다.")
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{self.base_branch}", timeout=120)
        return self.snapshot(fetch=False)

    def assert_write_base(self, expected_base_remote_sha: str) -> GitSyncSnapshot:
        self.fetch()
        snap = self.snapshot(fetch=False)
        if snap.dirty_count:
            raise GitSyncError("작업 트리가 깨끗하지 않습니다. 기존 로컬 변경을 먼저 정리하세요.")
        if snap.branch != self.base_branch:
            raise GitSyncError(
                f"규칙 수정은 기준 브랜치 {self.base_branch}에서 시작해야 합니다. 현재: {snap.branch}"
            )
        if not snap.remote_sha or snap.local_sha != snap.remote_sha:
            raise GitSyncError("로컬 기준 브랜치와 원격 HEAD가 일치하지 않습니다. 먼저 GitHub 최신상태를 가져오세요.")
        if expected_base_remote_sha and snap.remote_sha != expected_base_remote_sha:
            raise GitSyncError("REMOTE_CHANGED: 편집을 시작한 뒤 원격 HEAD가 변경되었습니다.")
        return snap

    def _new_rule_branch(self) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"web/lrule-{stamp}"

    def commit_and_push(
        self,
        paths: Iterable[str | Path],
        *,
        message: str,
        expected_base_remote_sha: str,
    ) -> dict:
        """Commit already-written files and push without force.

        Caller must invoke assert_write_base() before modifying files.
        """
        path_args = [str(Path(p).as_posix()) for p in paths]
        if not path_args:
            raise GitSyncError("커밋할 파일이 없습니다.")
        current = self.snapshot(fetch=False)
        if current.branch != self.base_branch:
            raise GitSyncError("규칙 변경 커밋 직전에 기준 브랜치가 바뀌었습니다.")
        self.fetch()
        latest_base = self.base_remote_sha()
        if expected_base_remote_sha and latest_base != expected_base_remote_sha:
            raise GitSyncError("REMOTE_CHANGED: 저장 직전 원격 기준 브랜치가 변경되었습니다.")

        diff = self._run("diff", "--", *path_args, check=False)
        if not diff.strip():
            raise GitSyncError("실제 파일 변경사항이 없습니다.")

        branch = self.base_branch
        if self.write_mode != "direct":
            branch = self._new_rule_branch()
            self._run("switch", "-c", branch)

        self._run("add", "--", *path_args)
        self._run("commit", "-m", message)
        commit_sha = self.local_sha()
        self._run("push", "-u", self.remote, branch, timeout=180)

        pr_url = ""
        pr_error = ""
        if self.write_mode != "direct" and shutil.which("gh"):
            title = message[:120]
            body = (
                "auto_write 운영 콘솔에서 생성된 L 규칙 변경입니다.\n\n"
                "- 강제 push 없음\n"
                "- 원격 기준 SHA 충돌 검사 완료\n"
                "- 관련 registry 테스트 통과 후 생성"
            )
            proc = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--repo", self.repository,
                    "--base", self.base_branch,
                    "--head", branch,
                    "--title", title,
                    "--body", body,
                ],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            if proc.returncode == 0:
                pr_url = (proc.stdout or "").strip().splitlines()[-1]
            else:
                pr_error = (proc.stderr or proc.stdout or "").strip()[:800]

        pushed_snapshot = self.snapshot(fetch=True).as_dict()
        local_return_error = ""
        final_snapshot = pushed_snapshot
        if self.write_mode != "direct":
            try:
                final_snapshot = self.return_to_base().as_dict()
            except Exception as exc:
                local_return_error = str(exc)[:800]

        return {
            "branch": branch,
            "commit_sha": commit_sha,
            "pr_url": pr_url,
            "pr_error": pr_error,
            "local_return_error": local_return_error,
            "diff": diff,
            "snapshot": final_snapshot,
        }

    def rule_history(self, rule_code: str, registry_path: str, limit: int = 12) -> list[dict]:
        fmt = "%H%x1f%ad%x1f%s"
        raw = self._run(
            "log",
            "--all",
            f"-{max(1, min(limit, 50))}",
            "--date=iso-strict",
            f"--format={fmt}",
            "-S",
            rule_code,
            "--",
            registry_path,
            check=False,
        )
        rows = []
        for line in raw.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3:
                rows.append({"sha": parts[0], "date": parts[1], "subject": parts[2]})
        return rows

    def show_file(self, commitish: str, path: str) -> str:
        if not commitish or any(ch not in "0123456789abcdefABCDEF^~" for ch in commitish):
            raise GitSyncError("허용되지 않은 commit 식별자입니다.")
        return self._run("show", f"{commitish}:{path}", timeout=30)
