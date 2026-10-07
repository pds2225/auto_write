from __future__ import annotations

import json
import re
import shutil
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[3])
        self.registry_path = self.repo_root / self.REGISTRY_RELATIVE

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
            rule["_wiring"] = self.light_wiring(rule)
            rows.append(rule)
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
        proc = subprocess.run(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        output = "\n".join(part for part in [proc.stdout, proc.stderr] if part).strip()
        return RuleTestResult(
            ok=proc.returncode == 0,
            command=" ".join(cmd),
            output=output[-12000:],
            returncode=proc.returncode,
        )

    def light_wiring(self, rule: dict[str, Any]) -> dict[str, Any]:
        category = str(rule.get("category", "")).strip()
        guard_ref = str(rule.get("guard_ref", "")).strip()
        if category == "judgment":
            status = "HUMAN_RULE"
        elif category == "gap":
            status = "GAP"
        elif not guard_ref:
            status = "DEAD_RULE"
        else:
            status = "DECLARED"
        return {
            "status": status,
            "guard_declared": bool(guard_ref),
            "registry": True,
        }

    def _paths_from_guard(self, guard_ref: str) -> list[str]:
        candidates = re.findall(r"(?:app|scripts|docs)/[A-Za-z0-9_./\-]+(?:\.py|\.md|\.json)?", guard_ref)
        cleaned = []
        for raw in candidates:
            path = raw.rstrip(".,);:")
            if path not in cleaned:
                cleaned.append(path)
        return cleaned

    def inspect_wiring(self, rule: dict[str, Any]) -> dict[str, Any]:
        category = str(rule.get("category", "")).strip()
        guard_ref = str(rule.get("guard_ref", "")).strip()
        paths = self._paths_from_guard(guard_ref)
        path_checks = [{"path": p, "exists": (self.repo_root / p).exists()} for p in paths]
        test_declared = "test_" in guard_ref.lower()
        missing = [row["path"] for row in path_checks if not row["exists"]]

        if category == "judgment":
            overall = "HUMAN_RULE"
        elif category == "gap":
            overall = "GAP"
        elif not guard_ref:
            overall = "DEAD_RULE"
        elif missing:
            overall = "PARTIALLY_CONNECTED"
        elif not test_declared:
            overall = "PARTIALLY_CONNECTED"
        else:
            overall = "DECLARED_CONNECTED"

        return {
            "overall": overall,
            "registry": "CONNECTED",
            "lrule_enforcer": "CONNECTED",
            "guard_declared": bool(guard_ref),
            "test_declared": test_declared,
            "path_checks": path_checks,
            "missing_paths": missing,
            "note": "CONNECTED 판정은 실제 registry 로딩을 뜻하며 guard runtime 호출은 별도 검증 대상입니다.",
        }

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
        light = [self.light_wiring(r)["status"] for r in rules]
        return {
            "counts": data.get("counts", {}),
            "domains": domains,
            "categories": categories,
            "impacts": impacts,
            "dead": light.count("DEAD_RULE"),
            "gaps": light.count("GAP"),
            "human": light.count("HUMAN_RULE"),
            "declared": light.count("DECLARED"),
            "registry_path": str(self.REGISTRY_RELATIVE).replace("\\", "/"),
        }
