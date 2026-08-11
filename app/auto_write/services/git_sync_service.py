from __future__ import annotations

import json
import os
import re
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
    """Safe Git bridge for the local operator console.

    Rules enforced here:
    - GitHub is the source of truth.
    - Web rule edits never push directly to the base branch.
    - No force push.
    - A single ``web/lrule-*`` review branch is reused until its PR is merged.
    - Remote base movement is merged into the active review branch with a normal
      merge commit; conflicts are surfaced instead of overwritten.
    - Only the canonical L-rule registry can be committed by this service.
    """

    WEB_RULE_PREFIX = "web/lrule-"
    MANAGED_RULE_PATH = "app/tests/lessons_coverage.json"
    _RULE_CODE_RE = re.compile(r"\bL\d{3}\b", re.IGNORECASE)

    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[3])
        self.remote = os.getenv("AUTO_WRITE_GIT_REMOTE", "origin")
        self.base_branch = os.getenv("AUTO_WRITE_GIT_BASE_BRANCH", "master")
        self.repository = os.getenv("AUTO_WRITE_GITHUB_REPOSITORY", "pds2225/auto_write")
        self.managed_paths = {self.MANAGED_RULE_PATH}

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

    def _changed_names(self) -> set[str]:
        names = set(self._run("diff", "--name-only", check=False).splitlines())
        names.update(self._run("diff", "--cached", "--name-only", check=False).splitlines())
        names.update(self._run("ls-files", "--others", "--exclude-standard", check=False).splitlines())
        return {name.replace("\\", "/").strip() for name in names if name.strip()}

    def _restore_managed_paths(self, paths: Iterable[str]) -> None:
        safe = [path for path in paths if path in self.managed_paths]
        if safe:
            self._run("restore", "--source=HEAD", "--staged", "--worktree", "--", *safe, check=False)

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

    def _managed_content_matches_base(self, feature_sha: str, base_sha: str) -> bool:
        if not feature_sha or not base_sha:
            return False
        for path in sorted(self.managed_paths):
            proc = subprocess.run(
                ["git", "diff", "--quiet", feature_sha, base_sha, "--", path],
                cwd=self.repo_root,
                capture_output=True,
                timeout=20,
            )
            if proc.returncode != 0:
                return False
        return True

    def _feature_pr_merged(self, branch: str) -> bool:
        if not shutil.which("gh"):
            return False
        proc = subprocess.run(
            [
                "gh", "pr", "view", branch,
                "--repo", self.repository,
                "--json", "state,mergedAt",
                "--jq", '(.state == "MERGED") or (.mergedAt != null)',
            ],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        )
        return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"

    def _feature_is_merged(self, branch: str) -> bool:
        if branch == self.base_branch or not branch.startswith(self.WEB_RULE_PREFIX):
            return False
        local = self.local_sha()
        base_remote = self.base_remote_sha()
        return (
            self._is_ancestor(local, base_remote)
            or self._feature_pr_merged(branch)
            or self._managed_content_matches_base(local, base_remote)
        )

    def _switch_to_base_after_merge(self) -> bool:
        branch = self.current_branch()
        if not self._feature_is_merged(branch):
            return False
        self._run("switch", self.base_branch)
        snap = self.snapshot(fetch=False)
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{self.base_branch}", timeout=120)
        elif snap.status in {"CONFLICT", "LOCAL_AHEAD"}:
            raise GitSyncError("기준 브랜치가 원격과 안전하게 fast-forward 할 수 없는 상태입니다.")
        return True

    def _merge_latest_base_into_feature(self, branch: str) -> None:
        if self._is_ancestor(self.base_remote_sha(), self.local_sha()):
            return
        base_ref = f"{self.remote}/{self.base_branch}"
        proc = subprocess.run(
            ["git", "merge", "--no-edit", base_ref],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if proc.returncode != 0:
            self._run("merge", "--abort", check=False)
            message = (proc.stderr or proc.stdout or "merge conflict").strip()
            raise GitSyncError(f"REMOTE_CONFLICT: 최신 master를 L 규칙 브랜치에 병합하지 못했습니다. {message[:900]}")
        new_sha = self.local_sha()
        self._run("push", self.remote, branch, timeout=180)
        self.fetch()
        if self.remote_sha(branch) != new_sha:
            raise GitSyncError("PUSH_VERIFY_FAILED: master 동기화 merge commit이 원격 feature branch와 일치하지 않습니다.")

    def sync_from_remote(self) -> GitSyncSnapshot:
        self.fetch()
        if self._changed_names():
            raise GitSyncError("로컬 변경사항이 있어 자동 동기화를 중단했습니다. 먼저 저장 또는 복구하세요.")

        if self._switch_to_base_after_merge():
            return self.snapshot(fetch=False)

        snap = self.snapshot(fetch=False)
        if snap.branch == self.base_branch:
            if snap.status == "CONFLICT":
                raise GitSyncError("로컬과 원격 master가 서로 갈라져 있어 fast-forward 할 수 없습니다.")
            if snap.status == "REMOTE_AHEAD":
                self._run("merge", "--ff-only", f"{self.remote}/{self.base_branch}", timeout=120)
            elif snap.status == "LOCAL_AHEAD":
                raise GitSyncError("로컬 master가 원격보다 앞서 있습니다. base 직접 push는 금지입니다.")
            return self.snapshot(fetch=False)

        if not snap.branch.startswith(self.WEB_RULE_PREFIX):
            raise GitSyncError(f"관리 대상이 아닌 브랜치에서는 자동 동기화하지 않습니다: {snap.branch}")
        if snap.status == "CONFLICT":
            raise GitSyncError("활성 L 규칙 브랜치와 원격 feature branch가 diverged 상태입니다.")
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{snap.branch}", timeout=120)
        elif snap.status == "LOCAL_AHEAD":
            raise GitSyncError("활성 L 규칙 브랜치에 미전송 commit이 있습니다. 자동으로 덮어쓰지 않습니다.")

        self._merge_latest_base_into_feature(snap.branch)
        return self.snapshot(fetch=False)

    def return_to_base(self) -> GitSyncSnapshot:
        self.fetch()
        if self._changed_names():
            raise GitSyncError("로컬 변경사항이 있어 기준 브랜치로 전환할 수 없습니다.")
        branch = self.current_branch()
        if branch != self.base_branch:
            if not branch.startswith(self.WEB_RULE_PREFIX):
                raise GitSyncError(f"관리 대상이 아닌 브랜치에서는 자동 전환하지 않습니다: {branch}")
            if not self._feature_is_merged(branch):
                raise GitSyncError("현재 L 규칙 PR이 아직 원격 기준 브랜치에 병합되지 않았습니다.")
            self._run("switch", self.base_branch)
        snap = self.snapshot(fetch=False)
        if snap.status == "REMOTE_AHEAD":
            self._run("merge", "--ff-only", f"{self.remote}/{self.base_branch}", timeout=120)
        elif snap.status in {"CONFLICT", "LOCAL_AHEAD"}:
            raise GitSyncError("기준 브랜치가 원격과 안전하게 fast-forward 할 수 없는 상태입니다.")
        return self.snapshot(fetch=False)

    def assert_write_base(self, expected_base_remote_sha: str) -> GitSyncSnapshot:
        self.fetch()
        changed = self._changed_names()
        unrelated = sorted(changed - self.managed_paths)
        if unrelated:
            raise GitSyncError(f"규칙 외 로컬 변경이 있어 편집을 시작할 수 없습니다: {unrelated[0]}")

        snap = self.snapshot(fetch=False)
        if expected_base_remote_sha and snap.base_remote_sha != expected_base_remote_sha:
            raise GitSyncError("REMOTE_CHANGED: 편집을 시작한 뒤 원격 기준 브랜치가 변경되었습니다.")

        if snap.branch == self.base_branch:
            if not snap.remote_sha or snap.local_sha != snap.remote_sha:
                raise GitSyncError("로컬 master와 원격 master가 일치하지 않습니다. 먼저 GitHub 최신상태를 가져오세요.")
            return snap

        if snap.branch.startswith(self.WEB_RULE_PREFIX):
            if not snap.remote_sha or snap.local_sha != snap.remote_sha:
                raise GitSyncError("활성 L 규칙 브랜치와 원격 feature branch가 일치하지 않습니다. 먼저 GitHub 최신상태를 가져오세요.")
            if not self._is_ancestor(snap.base_remote_sha, snap.local_sha):
                raise GitSyncError("BASE_OUTDATED: 원격 master가 진행되었습니다. GitHub 최신상태 가져오기로 feature branch를 갱신하세요.")
            return snap

        raise GitSyncError(
            f"규칙 수정은 {self.base_branch} 또는 활성 {self.WEB_RULE_PREFIX}* 브랜치에서만 가능합니다. 현재: {snap.branch}"
        )

    def _new_rule_branch(self) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return f"{self.WEB_RULE_PREFIX}{stamp}"

    def _rollback_failed_local_commit(
        self,
        *,
        original_branch: str,
        original_sha: str,
        branch: str,
        created_branch: bool,
    ) -> None:
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
                    "- base 직접 push/force push 없음\n"
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
        path_args = [str(Path(path).as_posix()) for path in paths]
        if not path_args:
            raise GitSyncError("커밋할 파일이 없습니다.")
        if not set(path_args).issubset(self.managed_paths):
            raise GitSyncError("웹 Git 쓰기는 canonical L 규칙 registry에만 허용됩니다.")

        # Fetch failures are retryable. Preserve the validated on-disk edit so a
        # later retry can continue without re-entering the form.
        self.fetch()
        current = self.snapshot(fetch=False)
        if expected_base_remote_sha and current.base_remote_sha != expected_base_remote_sha:
            self._restore_managed_paths(path_args)
            raise GitSyncError("REMOTE_CHANGED: 저장 직전 원격 master가 변경되어 registry를 현재 branch 값으로 복구했습니다.")

        changed = self._changed_names()
        unrelated = sorted(changed - set(path_args))
        if unrelated:
            raise GitSyncError(f"규칙 파일 외 로컬 변경이 감지되어 commit을 중단했습니다: {unrelated[0]}")

        if current.branch == self.base_branch:
            if not current.remote_sha or current.local_sha != current.remote_sha:
                self._restore_managed_paths(path_args)
                raise GitSyncError("REMOTE_CHANGED: 저장 직전 로컬 master와 원격 master가 달라져 registry를 복구했습니다.")
        elif current.branch.startswith(self.WEB_RULE_PREFIX):
            if not current.remote_sha or current.local_sha != current.remote_sha:
                self._restore_managed_paths(path_args)
                raise GitSyncError("REMOTE_CHANGED: 활성 L 규칙 브랜치와 원격 feature branch가 달라져 registry를 복구했습니다.")
            if not self._is_ancestor(current.base_remote_sha, current.local_sha):
                self._restore_managed_paths(path_args)
                raise GitSyncError("BASE_OUTDATED: 최신 master를 먼저 동기화해야 합니다. registry는 현재 feature branch 값으로 복구했습니다.")
        else:
            self._restore_managed_paths(path_args)
            raise GitSyncError(f"현재 브랜치에서는 규칙 commit을 만들 수 없습니다: {current.branch}")

        diff = self._run("diff", "--", *path_args, check=False)
        if not diff.strip():
            raise GitSyncError("실제 파일 변경사항이 없습니다.")

        original_branch = current.branch
        original_sha = current.local_sha
        branch = original_branch
        created_branch = False
        if original_branch == self.base_branch:
            branch = self._new_rule_branch()
            self._run("switch", "-c", branch)
            created_branch = True

        commit_sha = ""
        try:
            self._run("add", "--", *path_args)
            self._run("commit", "-m", message)
            commit_sha = self.local_sha()
            try:
                self._run("push", "-u", self.remote, branch, timeout=180)
            except Exception as push_exc:
                try:
                    self.fetch()
                except Exception:
                    pass
                if self.remote_sha(branch) != commit_sha:
                    raise push_exc
            self.fetch()
            if self.remote_sha(branch) != commit_sha:
                raise GitSyncError("PUSH_VERIFY_FAILED: 원격 feature branch SHA가 방금 만든 commit과 일치하지 않습니다.")
        except Exception:
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

    @classmethod
    def _rule_from_registry_text(cls, text: str, rule_code: str) -> dict | None:
        try:
            data = json.loads(text)
        except Exception:
            return None
        target = rule_code.upper().strip()
        for rule in data.get("lessons", []):
            match = cls._RULE_CODE_RE.search(str(rule.get("id", "")))
            if match and match.group(0).upper() == target:
                return rule
        return None

    def rule_history(self, rule_code: str, registry_path: str, limit: int = 12) -> list[dict]:
        """Return commits that actually changed this rule's value."""
        fmt = "%H%x1f%ad%x1f%s"
        raw = self._run(
            "log", "-200", "--date=iso-strict", f"--format={fmt}", "--", registry_path,
            check=False,
        )
        commits: list[tuple[str, str, str]] = []
        for line in raw.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3:
                commits.append((parts[0], parts[1], parts[2]))

        changed: list[dict] = []
        previous_signature: str | None = None
        for sha, date, subject in reversed(commits):
            text = self._run("show", f"{sha}:{registry_path}", check=False, timeout=30)
            rule = self._rule_from_registry_text(text, rule_code)
            signature = (
                "<missing>"
                if rule is None
                else json.dumps(rule, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            if signature != previous_signature:
                if rule is not None:
                    changed.append({"sha": sha, "date": date, "subject": subject})
                previous_signature = signature
        return list(reversed(changed[-max(1, min(limit, 50)) :]))

    def show_file(self, commitish: str, path: str) -> str:
        if not commitish or any(ch not in "0123456789abcdefABCDEF^~" for ch in commitish):
            raise GitSyncError("허용되지 않은 commit 식별자입니다.")
        return self._run("show", f"{commitish}:{path}", timeout=30)
