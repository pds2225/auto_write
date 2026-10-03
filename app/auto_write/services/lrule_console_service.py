from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_write.services.lrule_verification import (
    ENV_SKIPPED,
    FAILING,
    MISSING_GUARD,
    NOT_RUN,
    UNVERIFIED,
    VERIFIED,
    GuardIndex,
    build_wiring,
    git_head,
    verify_lessons,
)


_RULE_CODE_RE = re.compile(r"\bL\d{3}\b", re.IGNORECASE)


@dataclass
class RuleTestResult:
    ok: bool
    command: str
    output: str
    returncode: int

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "command": self.command,
            "output": self.output,
            "returncode": self.returncode,
        }


class LRuleConsoleService:
    """Read/edit the canonical lessons registry used by LRuleEnforcer."""

    REGISTRY_RELATIVE = Path("app/tests/lessons_coverage.json")
    EDITABLE_FIELDS = (
        "summary",
        "mechanizable",
        "category",
        "guard_ref",
        "gap_desc",
        "impact",
        "domain",
    )

    def __init__(self, repo_root: str | Path | None = None, cache_path: str | Path | None = None):
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[3])
        self.registry_path = self.repo_root / self.REGISTRY_RELATIVE
        self.cache_path = Path(
            cache_path or (self.repo_root / "results" / "operator" / "lrule_verification_cache.json")
        )
        self._index = GuardIndex(self.repo_root)
        self._cache_lock = threading.Lock()
        self._job_lock = threading.Lock()
        self._job = {"running": False, "scope": "", "error": "", "message": ""}

    @staticmethod
    def rule_code(rule: dict[str, Any]) -> str:
        match = _RULE_CODE_RE.search(str(rule.get("id", "")))
        return match.group(0).upper() if match else str(rule.get("id", "")).strip()

    @staticmethod
    def rule_label(rule: dict[str, Any]) -> str:
        raw = str(rule.get("id", ""))
        parts = [p.strip() for p in raw.split("|")]
        return parts[-1] if len(parts) > 1 else str(rule.get("summary", ""))[:60]

    def load(self) -> dict[str, Any]:
        with self.registry_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("lessons"), list):
            raise ValueError("L 규칙 registry 형식이 올바르지 않습니다.")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self._recount(data)
        temp = self.registry_path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        json.loads(temp.read_text(encoding="utf-8"))
        temp.replace(self.registry_path)

    @staticmethod
    def _recount(data: dict[str, Any]) -> None:
        counts = {"mechanized": 0, "gap": 0, "judgment": 0, "total": 0}
        for rule in data.get("lessons", []):
            category = str(rule.get("category", "")).strip()
            if category in counts:
                counts[category] += 1
            counts["total"] += 1
        data["counts"] = counts

    def list_rules(
        self,
        *,
        query: str = "",
        domain: str = "",
        category: str = "",
        impact: str = "",
    ) -> list[dict[str, Any]]:
        data = self.load()
        q = query.strip().lower()
        rows: list[dict[str, Any]] = []
        for raw in data["lessons"]:
            rule = deepcopy(raw)
            code = self.rule_code(rule)
            label = self.rule_label(rule)
            searchable = " ".join(
                [
                    code,
                    str(rule.get("id", "")),
                    str(rule.get("summary", "")),
                    str(rule.get("guard_ref", "")),
                    str(rule.get("gap_desc", "")),
                ]
            ).lower()
            if q and q not in searchable:
                continue
            if domain and str(rule.get("domain", "")) != domain:
                continue
            if category and str(rule.get("category", "")) != category:
                continue
            if impact and str(rule.get("impact", "")) != impact:
                continue
            rule["_code"] = code
            rule["_label"] = label
            rows.append(rule)
        self._attach_wiring(rows, include_tests=False)
        return rows

    def get_rule(self, code: str) -> dict[str, Any]:
        normalized = code.upper().strip()
        for rule in self.load()["lessons"]:
            if self.rule_code(rule) == normalized:
                out = deepcopy(rule)
                out["_code"] = normalized
                out["_label"] = self.rule_label(out)
                out["_wiring"] = self.inspect_wiring(out)
                out["_references"] = self.find_references(normalized)
                return out
        raise KeyError(f"L 규칙을 찾을 수 없습니다: {normalized}")

    def update_rule(self, code: str, updates: dict[str, str]) -> tuple[dict, str]:
        data = self.load()
        before_text = self.registry_path.read_text(encoding="utf-8")
        normalized = code.upper().strip()
        found = False
        for rule in data["lessons"]:
            if self.rule_code(rule) != normalized:
                continue
            found = True
            for field in self.EDITABLE_FIELDS:
                if field in updates:
                    rule[field] = str(updates[field]).strip()
            break
        if not found:
            raise KeyError(f"L 규칙을 찾을 수 없습니다: {normalized}")
        self._write(data)
        return self.get_rule(normalized), before_text

    def restore_text(self, text: str) -> None:
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get("lessons"), list):
            raise ValueError("복구할 registry가 올바르지 않습니다.")
        self._write(data)

    def restore_rule_from_registry_text(self, code: str, historical_text: str) -> tuple[dict, str]:
        historical = json.loads(historical_text)
        target = None
        for rule in historical.get("lessons", []):
            if self.rule_code(rule) == code.upper().strip():
                target = deepcopy(rule)
                break
        if target is None:
            raise KeyError(f"과거 버전에 {code} 규칙이 없습니다.")

        current = self.load()
        before_text = self.registry_path.read_text(encoding="utf-8")
        for index, rule in enumerate(current["lessons"]):
            if self.rule_code(rule) == code.upper().strip():
                current["lessons"][index] = target
                self._write(current)
                return self.get_rule(code), before_text
        raise KeyError(f"현재 registry에 {code} 규칙이 없습니다.")

    def run_registry_tests(self) -> RuleTestResult:
        tests = [
            "app/tests/test_lesson_registry_integrity.py",
            "app/tests/test_lrule_enforcer.py",
        ]
        if shutil.which("py"):
            cmd = ["py", "-3.11", "-m", "pytest", *tests, "-q"]
        else:
            python_exe = shutil.which("python") or "python"
            cmd = [python_exe, "-m", "pytest", *tests, "-q"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            def _text(value: object) -> str:
                if isinstance(value, bytes):
                    return value.decode("utf-8", errors="replace")
                return str(value) if value else ""

            output = "\n".join(
                part for part in [_text(exc.stdout), _text(exc.stderr)] if part
            ).strip()
            timeout_note = "registry tests timed out after 180 seconds"
            return RuleTestResult(
                ok=False,
                command=" ".join(cmd),
                output=f"{timeout_note}\n{output}".strip(),
                returncode=124,
            )
        except OSError as exc:
            return RuleTestResult(
                ok=False,
                command=" ".join(cmd),
                output=f"registry tests could not start: {type(exc).__name__}: {exc}",
                returncode=127,
            )
        output = "\n".join(part for part in [proc.stdout, proc.stderr] if part).strip()
        return RuleTestResult(
            ok=proc.returncode == 0,
            command=" ".join(cmd),
            output=output[-12000:],
            returncode=proc.returncode,
        )

    def _cache_rules(self) -> dict[str, Any]:
        data = self._read_cache()
        rules = data.get("rules")
        return rules if isinstance(rules, dict) else {}

    def _read_cache(self) -> dict[str, Any]:
        if not self.cache_path.is_file():
            return {"version": 1, "rules": {}}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "rules": {}}
        if not isinstance(data, dict):
            return {"version": 1, "rules": {}}
        if not isinstance(data.get("rules"), dict):
            data["rules"] = {}
        return data

    def _write_cache(self, data: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.cache_path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        json.loads(temp.read_text(encoding="utf-8"))
        temp.replace(self.cache_path)

    def _attach_wiring(self, rows: list[dict[str, Any]], *, include_tests: bool) -> None:
        cache_rules = self._cache_rules()
        head = git_head(self.repo_root)
        for rule in rows:
            rule["_wiring"] = build_wiring(
                rule,
                code=str(rule.get("_code") or self.rule_code(rule)),
                repo=self.repo_root,
                cache_rules=cache_rules,
                head=head,
                index=self._index,
                include_tests=include_tests,
            )

    def light_wiring(self, rule: dict[str, Any]) -> dict[str, Any]:
        """List-page status. Reads the verification cache and does not run pytest."""
        code = str(rule.get("_code") or self.rule_code(rule))
        return build_wiring(
            rule,
            code=code,
            repo=self.repo_root,
            cache_rules=self._cache_rules(),
            head=git_head(self.repo_root),
            index=self._index,
            include_tests=False,
        )

    def _paths_from_guard(self, guard_ref: str) -> list[str]:
        candidates = re.findall(r"(?:app|scripts|docs)/[A-Za-z0-9_./\-]+(?:\.py|\.md|\.json)?", guard_ref)
        cleaned = []
        for raw in candidates:
            path = raw.rstrip(".,);:")
            if path not in cleaned:
                cleaned.append(path)
        return cleaned

    def inspect_wiring(self, rule: dict[str, Any]) -> dict[str, Any]:
        guard_ref = str(rule.get("guard_ref", "")).strip()
        paths = self._paths_from_guard(guard_ref)
        path_checks = [{"path": p, "exists": (self.repo_root / p).exists()} for p in paths]
        test_declared = "test_" in guard_ref.lower()
        missing = [row["path"] for row in path_checks if not row["exists"]]
        code = str(rule.get("_code") or self.rule_code(rule))
        wiring = build_wiring(
            rule,
            code=code,
            repo=self.repo_root,
            cache_rules=self._cache_rules(),
            head=git_head(self.repo_root),
            index=self._index,
            include_tests=True,
        )
        wiring.update(
            {
                "registry": "CONNECTED",
                "lrule_enforcer": "CONNECTED",
                "test_declared": test_declared,
                "path_checks": path_checks,
                "missing_paths": missing,
                "note": (
                    "VERIFIED 는 현재 HEAD에서 이 규칙의 가드 테스트가 실행되어 모두 통과한 경우만입니다. "
                    "경로가 있다고 검증된 것이 아닙니다."
                ),
            }
        )
        return wiring

    def find_references(self, code: str, limit: int = 40) -> list[dict[str, Any]]:
        normalized = code.upper().strip()
        roots = [
            self.repo_root / "app",
            self.repo_root / ".claude",
            self.repo_root / "docs",
        ]
        skip_parts = {".git", "__pycache__", "results", "node_modules", ".venv", "venv"}
        allowed = {".py", ".json", ".md", ".txt", ".yaml", ".yml"}
        found: list[dict[str, Any]] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if len(found) >= limit:
                    return found
                if not path.is_file() or path.suffix.lower() not in allowed:
                    continue
                if any(part in skip_parts for part in path.parts):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if normalized in line.upper():
                        found.append(
                            {
                                "path": str(path.relative_to(self.repo_root)).replace("\\", "/"),
                                "line": line_no,
                                "snippet": line.strip()[:220],
                            }
                        )
                        if len(found) >= limit:
                            return found
        return found

    def summary(self) -> dict[str, Any]:
        data = self.load()
        rules = data["lessons"]
        domains = sorted({str(r.get("domain", "")) for r in rules if r.get("domain")})
        categories = sorted({str(r.get("category", "")) for r in rules if r.get("category")})
        impacts = sorted({str(r.get("impact", "")) for r in rules if r.get("impact")})
        cache_rules = self._cache_rules()
        head = git_head(self.repo_root)
        light = [
            build_wiring(
                rule,
                code=self.rule_code(rule),
                repo=self.repo_root,
                cache_rules=cache_rules,
                head=head,
                index=self._index,
                include_tests=False,
            )["status"]
            for rule in rules
        ]
        return {
            "counts": data.get("counts", {}),
            "domains": domains,
            "categories": categories,
            "impacts": impacts,
            "dead": light.count("DEAD_RULE"),
            "gaps": light.count("GAP"),
            "human": light.count("HUMAN_RULE"),
            "verified": light.count(VERIFIED),
            "failing": light.count(FAILING),
            "not_run": light.count(NOT_RUN),
            "stale": light.count(UNVERIFIED),
            "unverified": light.count(NOT_RUN) + light.count(UNVERIFIED),
            "missing_guard": light.count(MISSING_GUARD),
            "env_skipped": light.count(ENV_SKIPPED),
            "head": head,
            "job": self.job_snapshot(),
            "registry_path": str(self.REGISTRY_RELATIVE).replace("\\", "/"),
        }

    def job_snapshot(self) -> dict[str, Any]:
        with self._job_lock:
            return dict(self._job)

    def verify_status(self) -> dict[str, Any]:
        """폴링용 상태. job_snapshot 과 summary 의 head·건수를 합친다."""
        job = self.job_snapshot()
        summary = self.summary()
        return {
            "running": bool(job.get("running")),
            "scope": str(job.get("scope") or ""),
            "error": str(job.get("error") or ""),
            "message": str(job.get("message") or ""),
            "head": str(summary.get("head") or ""),
            "counts": {
                "verified": int(summary.get("verified") or 0),
                "failing": int(summary.get("failing") or 0),
                "not_run": int(summary.get("not_run") or 0),
                "unverified": int(summary.get("unverified") or 0),
                "missing_guard": int(summary.get("missing_guard") or 0),
                "env_skipped": int(summary.get("env_skipped") or 0),
                "human": int(summary.get("human") or 0),
                "gaps": int(summary.get("gaps") or 0),
                "dead": int(summary.get("dead") or 0),
            },
        }

    def start_verify(self, codes: list[str] | None = None) -> str:
        """Start guard pytest in the background. The list page does not run tests itself."""
        normalized = [code.upper().strip() for code in codes] if codes else None
        if normalized:
            known = {self.rule_code(rule): rule for rule in self.load()["lessons"]}
            missing = [code for code in normalized if code not in known]
            if missing:
                return f"L 규칙을 찾을 수 없습니다: {', '.join(missing)}"
            non_mechanized = [
                code for code in normalized if str(known[code].get("category", "")) != "mechanized"
            ]
            if non_mechanized and len(non_mechanized) == len(normalized):
                return "선택한 규칙은 기계화 가드가 아니라 테스트를 실행하지 않습니다."
        with self._job_lock:
            if self._job.get("running"):
                return "이미 가드 검증이 실행 중입니다. 잠시 후 새로고침하세요."
            self._job = {
                "running": True,
                "scope": ",".join(normalized) if normalized else "all",
                "error": "",
                "message": "가드 테스트 검증 실행 중",
                "started_at": time.time(),
            }

        def _run() -> None:
            message = ""
            error = ""
            try:
                summary = self.verify_rules(normalized)
                message = (
                    "검증 완료 "
                    f"VERIFIED {summary.get('verified', 0)} / "
                    f"FAILING {summary.get('failing', 0)} / "
                    f"MISSING_GUARD {summary.get('missing_guard', 0)} / "
                    f"ENV_SKIPPED {summary.get('env_skipped', 0)} / "
                    f"UNVERIFIED {summary.get('unverified', 0)}"
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            with self._job_lock:
                self._job = {
                    "running": False,
                    "scope": ",".join(normalized) if normalized else "all",
                    "error": error,
                    "message": message,
                }

        threading.Thread(target=_run, name="lrule-verify", daemon=True).start()
        return "가드 테스트 검증을 시작했습니다. 완료 후 새로고침하면 현재 HEAD 기준 상태가 반영됩니다."

    def verify_rules(self, codes: list[str] | None = None) -> dict[str, Any]:
        """Execute guard tests and cache results for this git HEAD. Does not edit the registry."""
        head = git_head(self.repo_root)
        lessons = self.load()["lessons"]
        wanted = {code.upper().strip() for code in codes} if codes else None
        records = verify_lessons(
            lessons,
            repo=self.repo_root,
            index=self._index,
            head=head,
            codes=wanted,
            rule_code_fn=self.rule_code,
        )
        with self._cache_lock:
            data = self._read_cache()
            data["version"] = 1
            data["head"] = head
            stored = data.setdefault("rules", {})
            stored.update(records)
            self._write_cache(data)
        counts = {"verified": 0, "failing": 0, "missing_guard": 0, "env_skipped": 0, "unverified": 0}
        problems: list[dict[str, str]] = []
        cache_rules = self._cache_rules()
        for rule in lessons:
            code = self.rule_code(rule)
            if code not in records:
                continue
            wiring = build_wiring(
                rule,
                code=code,
                repo=self.repo_root,
                cache_rules=cache_rules,
                head=head,
                index=self._index,
                include_tests=True,
            )
            status = str(wiring["status"])
            if status == VERIFIED:
                counts["verified"] += 1
            elif status == FAILING:
                counts["failing"] += 1
            elif status == MISSING_GUARD:
                counts["missing_guard"] += 1
            elif status == ENV_SKIPPED:
                counts["env_skipped"] += 1
            else:
                counts["unverified"] += 1
            if status in {FAILING, MISSING_GUARD, ENV_SKIPPED, UNVERIFIED}:
                problems.append({"code": code, "status": status, "reason": str(wiring.get("reason", ""))})
        counts["problems"] = problems
        counts["head"] = head
        return counts
