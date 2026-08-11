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
    discards an unrelated dirty working tree.

    In ``branch-pr`` mode the console stays on the active ``web/lrule-*`` branch
    until that branch is merged into the configured base branch. This keeps the
    web UI and the pushed remote branch on the same L-rule version and also lets
    multiple rule edits accumulate in one review branch without manual checkout.
    """

    WEB_RULE_PREFIX = "web/lrule-"

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

    def _is_ancestor(self, ancestor: str, descendant: str) -> bool:
        if not ancestor or not descendant:
            return False
        return subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=self.repo_root,
            capture_output=True,
            timeout=15,
        ).returncode == 0

    def _merge_base(self, left: str, right: str) -> str:
        if not left or not right:
            return ""
        return self._run("merge-base", left, right, check=False)

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

    def _switch_to_base_if_feature_merged(self) -> bool:
        """Return to base only after the active web branch is contained in remote base."""
        branch = self.current_branch()
        if branch == self.base_branch or not branch.startswith(self.WEB_RULE_PREFIX):
            return False
        local = self.local_sha()
        base_remote = self.base_remote_sha()
        if not self._is_ancestor(local, base_remote):
            return False
        self._run("switch", self.base_branch)
        snap = self.snapshot(fetch=False)
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{self.base_branch}", timeout=120)
        elif snap.status in {"CONFLICT", "LOCAL_AHEAD"}:
            raise GitSyncError("기준 브랜치가 원격과 안전하게 fast-forward 할 수 없는 상태입니다.")
        return True

    def sync_from_remote(self) -> GitSyncSnapshot:
        self.fetch()
        if self.dirty_paths():
            raise GitSyncError("로컬 변경사항이 있어 자동 동기화를 중단했습니다.")

        # A merged rule-review branch can safely return to base; until merge, keep
        # the branch checked out so the web UI reflects the same content as remote.
        self._switch_to_base_if_feature_merged()

        snap = self.snapshot(fetch=False)
        if snap.status == "CONFLICT":
            raise GitSyncError("로컬과 원격이 서로 갈라져 있어 fast-forward 할 수 없습니다.")
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{snap.branch}", timeout=120)
        return self.snapshot(fetch=False)

    def return_to_base(self) -> GitSyncSnapshot:
        """Explicitly return to base only when the active feature is already merged."""
        self.fetch()
        if self.dirty_paths():
            raise GitSyncError("로컬 변경사항이 있어 기준 브랜치로 전환할 수 없습니다.")
        branch = self.current_branch()
        if branch != self.base_branch:
            if not branch.startswith(self.WEB_RULE_PREFIX):
                raise GitSyncError(f"관리 대상이 아닌 브랜치에서는 자동 전환하지 않습니다: {branch}")
            if not self._is_ancestor(self.local_sha(), self.base_remote_sha()):
                raise GitSyncError("현재 L 규칙 브랜치가 아직 원격 기준 브랜치에 병합되지 않았습니다.")
            self._run("switch", self.base_branch)
        snap = self.snapshot(fetch=False)
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{self.base_branch}", timeout=120)
        elif snap.status in {"CONFLICT", "LOCAL_AHEAD"}:
            raise GitSyncError("기준 브랜치가 원격과 안전하게 fast-forward 할 수 없는 상태입니다.")
        return self.snapshot(fetch=False)

    def assert_write_base(self, expected_base_remote_sha: str) -> GitSyncSnapshot:
        self.fetch()
        snap = self.snapshot(fetch=False)
        if snap.dirty_count:
            raise GitSyncError("작업 트리가 깨끗하지 않습니다. 기존 로컬 변경을 먼저 정리하세요.")
        if expected_base_remote_sha and snap.base_remote_sha != expected_base_remote_sha:
            raise GitSyncError("REMOTE_CHANGED: 편집을 시작한 뒤 원격 기준 브랜치가 변경되었습니다.")

        if snap.branch == self.base_branch:
            if not snap.remote_sha or snap.local_sha != snap.remote_sha:
                raise GitSyncError("로컬 기준 브랜치와 원격 HEAD가 일치하지 않습니다. 먼저 GitHub 최신상태를 가져오세요.")
            return snap

        if self.write_mode != "direct" and snap.branch.startswith(self.WEB_RULE_PREFIX):
            if not snap.remote_sha or snap.local_sha != snap.remote_sha:
                raise GitSyncError("활성 L 규칙 브랜치와 원격 브랜치가 일치하지 않습니다. 먼저 GitHub 최신상태를 가져오세요.")
            if self._merge_base(snap.local_sha, snap.base_remote_sha) != snap.base_remote_sha:
                raise GitSyncError("REMOTE_CHANGED: 활성 L 규칙 브랜치의 기준 master가 최신 원격 master와 다릅니다.")
            return snap

        raise GitSyncError(
            f"규칙 수정은 {self.base_branch} 또는 활성 {self.WEB_RULE_PREFIX}* 브랜치에서만 가능합니다. 현재: {snap.branch}"
        )

    def _new_rule_branch(self) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{self.WEB_RULE_PREFIX}{stamp}"

    def _rollback_failed_local_commit(
        self,
        *,
        original_branch: str,
        original_sha: str,
        branch: str,
        created_branch: bool,
    ) -> None:
        """Restore the tracked registry if commit/push did not reach remote."""
        try:
            if self.current_branch() != branch:
                self._run("switch", branch, check=False)
            self._run("reset", "--hard", original_sha, check=False)
            if created_branch:
                self._run("switch", original_branch, check=False)
                self._run("branch", "-D", branch, check=False)
        except Exception:
            pass

    def _pr_info(self, branch: str, *, create: bool) -> tuple[str, str]:
        if self.write_mode == "direct":
            return "", ""
        if not shutil.which("gh"):
            return "", "GitHub CLI(gh) 미설치 — 브랜치 push는 완료됐지만 PR 자동 생성은 생략했습니다."

        if create:
            cmd = [
                "gh", "pr", "create",
                "--repo", self.repository,
                "--base", self.base_branch,
                "--head", branch,
                "--title", f"web: L rule updates ({branch})",
                "--body",
                (
                    "auto_write 운영 콘솔에서 생성된 L 규칙 변경입니다.\n\n"
                    "- 강제 push 없음\n"
                    "- 원격 기준 SHA 충돌 검사 완료\n"
                    "- 관련 registry 테스트 통과 후 생성"
                ),
            ]
        else:
            cmd = [
                "gh", "pr", "view", branch,
                "--repo", self.repository,
                "--json", "url",
                "--jq", ".url",
            ]
        proc = subprocess.run(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        if proc.returncode == 0:
            lines = (proc.stdout or "").strip().splitlines()
            return (lines[-1] if lines else ""), ""
        return "", (proc.stderr or proc.stdout or "").strip()[:800]

    def commit_and_push(
        self,
        paths: Iterable[str | Path],
        *,
        message: str,
        expected_base_remote_sha: str,
    ) -> dict:
        """Commit already-written files and verify the remote ref after push.

        ``branch-pr`` mode creates one web-managed branch from base and keeps
        reusing it for later rule edits until the PR is merged. No force push.
        """
        path_args = [str(Path(p).as_posix()) for p in paths]
        if not path_args:
            raise GitSyncError("커밋할 파일이 없습니다.")

        self.fetch()
        current = self.snapshot(fetch=False)
        if expected_base_remote_sha and current.base_remote_sha != expected_base_remote_sha:
            raise GitSyncError("REMOTE_CHANGED: 저장 직전 원격 기준 브랜치가 변경되었습니다.")

        allowed_paths = {str(Path(p).as_posix()) for p in path_args}
        changed_names = set(self._run("diff", "--name-only", check=False).splitlines())
        changed_names.update(self._run("diff", "--cached", "--name-only", check=False).splitlines())
        changed_names.update(self._run("ls-files", "--others", "--exclude-standard", check=False).splitlines())
        for dirty_name in sorted(name.replace("\\", "/") for name in changed_names if name.strip()):
            if dirty_name not in allowed_paths:
                raise GitSyncError(f"규칙 파일 외 로컬 변경이 감지되어 commit을 중단했습니다: {dirty_name}")

        if current.branch == self.base_branch:
            if not current.remote_sha or current.local_sha != current.remote_sha:
                raise GitSyncError("저장 직전 로컬 master와 원격 master가 달라졌습니다.")
        elif self.write_mode != "direct" and current.branch.startswith(self.WEB_RULE_PREFIX):
            if not current.remote_sha or current.local_sha != current.remote_sha:
                raise GitSyncError("저장 직전 활성 L 규칙 브랜치와 원격 브랜치가 달라졌습니다.")
            if self._merge_base(current.local_sha, current.base_remote_sha) != current.base_remote_sha:
                raise GitSyncError("REMOTE_CHANGED: 활성 L 규칙 브랜치의 기준 master가 최신 원격 master와 다릅니다.")
        else:
            raise GitSyncError(f"현재 브랜치에서는 규칙 commit을 만들 수 없습니다: {current.branch}")

        original_branch = current.branch
        original_sha = current.local_sha
        diff = self._run("diff", "--", *path_args, check=False)
        if not diff.strip():
            raise GitSyncError("실제 파일 변경사항이 없습니다.")

        branch = original_branch
        created_branch = False
        commit_sha = ""
        if self.write_mode != "direct" and original_branch == self.base_branch:
            branch = self._new_rule_branch()
            self._run("switch", "-c", branch)
            created_branch = True
        elif self.write_mode == "direct" and original_branch != self.base_branch:
            raise GitSyncError("direct 모드는 기준 브랜치에서만 사용할 수 있습니다.")

        try:
            self._run("add", "--", *path_args)
            self._run("commit", "-m", message)
            commit_sha = self.local_sha()
            self._run("push", "-u", self.remote, branch, timeout=180)
            self.fetch()
            pushed_remote_sha = self.remote_sha(branch)
            if pushed_remote_sha != commit_sha:
                raise GitSyncError("PUSH_VERIFY_FAILED: 원격 브랜치 SHA가 방금 만든 commit과 일치하지 않습니다.")
        except Exception:
            # If the remote really has the commit, do not destroy the local matching
            # branch; otherwise return the working tree to the previous clean commit.
            remote_has_commit = False
            if commit_sha:
                try:
                    self.fetch()
                    remote_has_commit = self.remote_sha(branch) == commit_sha
                except Exception:
                    remote_has_commit = False
            if not remote_has_commit:
                self._rollback_failed_local_commit(
                    original_branch=original_branch,
                    original_sha=original_sha,
                    branch=branch,
                    created_branch=created_branch,
                )
            raise

        pr_url, pr_error = self._pr_info(branch, create=created_branch)
        return {
            "branch": branch,
            "commit_sha": commit_sha,
            "pr_url": pr_url,
            "pr_error": pr_error,
            "diff": diff,
            "snapshot": self.snapshot(fetch=False).as_dict(),
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
