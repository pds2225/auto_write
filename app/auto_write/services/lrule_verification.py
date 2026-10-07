"""L-rule guard verification.

A mechanized rule is VERIFIED only when every guard test resolved from
``guard_ref`` has been executed and passed for the current git HEAD.
Path existence and a non-empty ``guard_ref`` are not a pass.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


VERIFIED = "VERIFIED"
FAILING = "FAILING"
UNVERIFIED = "UNVERIFIED"
NOT_RUN = "NOT_RUN"
MISSING_GUARD = "MISSING_GUARD"
ENV_SKIPPED = "ENV_SKIPPED"
HUMAN_RULE = "HUMAN_RULE"
GAP = "GAP"
DEAD_RULE = "DEAD_RULE"

_SUCCESS_STATUSES = {VERIFIED}

_GUARD_ITEM_RE = re.compile(
    r"(?<![\w/])"
    r"(?:(?P<path>(?:app/)?tests)/)?"
    r"(?P<file>test_[A-Za-z0-9_]+\.py)"
    r"(?:(?P<braces>::\{[^}]+\})"
    r"|(?P<nodes>::test_[A-Za-z0-9_]+(?![A-Za-z0-9_.])"
    r"(?:\s*[·,/]\s*(?:::)?test_[A-Za-z0-9_]+(?![A-Za-z0-9_.]))*))?"
    r"(?P<line>:\d+~?)?"
)
_BARE_TEST_RE = re.compile(r"(?<![\w.])(test_[A-Za-z0-9_]+)(?!\.py)(?![\w])")
_TEST_NAME_RE = re.compile(r"test_[A-Za-z0-9_]+")

_ENV_MARKERS = (
    "win32com",
    "no module named 'win32",
    'no module named "win32',
    "hwpframe",
    "hangul",
    "한글",
    "only supported on windows",
    "windows only",
    "windows 실",
    "not on windows",
    "sys.platform",
    "rhwp",
    "sample form is not in this workspace",
    "샘플 없음",
    "gitignor",
)


@dataclass
class TestSymbol:
    file: str
    name: str
    nodeid: str
    start: int
    end: int


@dataclass
class ResolvedGuard:
    whole_files: list[str] = field(default_factory=list)
    specific: list[tuple[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def files(self) -> list[str]:
        found = list(self.whole_files)
        found.extend(path for path, _name in self.specific)
        deduped: list[str] = []
        for item in found:
            if item not in deduped:
                deduped.append(item)
        return deduped

    @property
    def has_targets(self) -> bool:
        return bool(self.whole_files or self.specific)


@dataclass
class GuardIndex:
    repo: Path
    symbols: list[TestSymbol] = field(default_factory=list)
    by_name: dict[str, list[TestSymbol]] = field(default_factory=dict)
    by_file: dict[str, list[TestSymbol]] = field(default_factory=dict)
    _token: tuple[int, int] | None = None

    def ensure(self) -> None:
        token = self._scan_token()
        if token == self._token:
            return
        self._build()
        self._token = token

    def _scan_token(self) -> tuple[int, int]:
        root = self.repo / "app" / "tests"
        if not root.is_dir():
            return (0, 0)
        count = 0
        newest = 0
        for path in root.rglob("test_*.py"):
            if not path.is_file():
                continue
            count += 1
            try:
                newest = max(newest, path.stat().st_mtime_ns)
            except OSError:
                continue
        return (count, newest)

    def _build(self) -> None:
        symbols: list[TestSymbol] = []
        root = self.repo / "app" / "tests"
        if root.is_dir():
            for path in sorted(root.rglob("test_*.py")):
                if path.is_file():
                    symbols.extend(_symbols_in_file(self.repo, path))
        by_name: dict[str, list[TestSymbol]] = {}
        by_file: dict[str, list[TestSymbol]] = {}
        for symbol in symbols:
            by_name.setdefault(symbol.name, []).append(symbol)
            by_file.setdefault(symbol.file, []).append(symbol)
        self.symbols = symbols
        self.by_name = by_name
        self.by_file = by_file


def _symbols_in_file(repo: Path, path: Path) -> list[TestSymbol]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeError):
        return []
    rel = path.relative_to(repo).as_posix()
    found: list[TestSymbol] = []

    def walk(node: ast.AST, class_stack: list[str]) -> None:
        body = getattr(node, "body", [])
        for child in body:
            if isinstance(child, ast.ClassDef):
                walk(child, class_stack + [child.name])
                continue
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not child.name.startswith("test_"):
                continue
            start = child.lineno
            if child.decorator_list:
                start = min(start, child.decorator_list[0].lineno)
            end = getattr(child, "end_lineno", None) or child.lineno
            qual = class_stack + [child.name]
            nodeid = "::".join([rel, *qual])
            found.append(TestSymbol(file=rel, name=child.name, nodeid=nodeid, start=start, end=end))

    walk(tree, [])
    return found


def locate_test_file(repo: Path, path_prefix: str | None, filename: str) -> tuple[str | None, str]:
    attempts: list[str] = []
    if path_prefix:
        attempts.append(f"{path_prefix}/{filename}")
        if path_prefix == "tests":
            attempts.append(f"app/tests/{filename}")
    else:
        attempts.append(f"app/tests/{filename}")
        attempts.append(f"tests/{filename}")
    ordered: list[str] = []
    for item in attempts:
        if item not in ordered:
            ordered.append(item)
    for rel in ordered:
        if (repo / rel).is_file():
            return rel, rel
    return None, (ordered[0] if ordered else f"app/tests/{filename}")


def _names_from_selector(blob: str) -> list[str]:
    names: list[str] = []
    for part in re.split(r"[\s,·/]+", blob.strip()):
        part = part.strip()
        if part.startswith("::"):
            part = part[2:]
        if re.fullmatch(r"test_[A-Za-z0-9_]+", part) and part not in names:
            names.append(part)
    return names


def resolve_guard(guard_ref: str, repo: Path, index: GuardIndex) -> ResolvedGuard:
    """Turn a free-form guard_ref into test files, test names, and missing refs."""
    index.ensure()
    text = str(guard_ref or "")
    resolved = ResolvedGuard()
    whole: list[str] = []
    specific: dict[str, list[str]] = {}
    used_names: set[str] = set()
    seen_missing: set[str] = set()

    def add_missing(message: str) -> None:
        if message not in seen_missing:
            seen_missing.add(message)
            resolved.missing.append(message)

    def add_specific(file: str, name: str) -> None:
        bucket = specific.setdefault(file, [])
        if name not in bucket:
            bucket.append(name)
        used_names.add(name)

    for match in _GUARD_ITEM_RE.finditer(text):
        filename = match.group("file")
        rel, attempted = locate_test_file(repo, match.group("path"), filename)
        if rel is None:
            add_missing(f"없는 테스트 파일: {attempted}")
            continue
        braces = match.group("braces")
        nodes = match.group("nodes")
        line = match.group("line")
        if braces:
            for name in _names_from_selector(braces[2:].strip("{}")):
                add_specific(rel, name)
            continue
        if nodes:
            for name in _names_from_selector(nodes):
                add_specific(rel, name)
            continue
        if line:
            lineno = int(line[1:].rstrip("~"))
            symbol = _symbol_at_line(index, rel, lineno)
            if symbol is None:
                add_missing(f"줄 번호에 테스트 없음: {rel}:{lineno}")
            else:
                add_specific(rel, symbol.name)
            continue
        if rel not in whole:
            whole.append(rel)

    for bare in _BARE_TEST_RE.findall(text):
        if bare in used_names:
            continue
        matches = index.by_name.get(bare, [])
        mentioned = set(whole) | set(specific)
        if mentioned:
            narrowed = [item for item in matches if item.file in mentioned]
            if narrowed:
                matches = narrowed
        files = []
        for item in matches:
            if item.file not in files:
                files.append(item.file)
        if len(files) == 1:
            add_specific(files[0], bare)
            continue
        if len(files) > 1:
            add_missing(f"테스트 이름 불명확: {bare} → {', '.join(files)}")
            continue
        add_missing(f"없는 테스트 함수: {bare}")

    for file, names in specific.items():
        known = {item.name for item in index.by_file.get(file, [])}
        kept: list[str] = []
        for name in names:
            if name not in known:
                add_missing(f"없는 테스트 노드: {file}::{name}")
                continue
            kept.append(name)
        if file in whole:
            continue
        for name in kept:
            resolved.specific.append((file, name))

    for file in whole:
        if file not in index.by_file or not index.by_file[file]:
            add_missing(f"수집된 테스트 함수 없음: {file}")
            continue
        resolved.whole_files.append(file)
    return resolved


def _symbol_at_line(index: GuardIndex, file: str, lineno: int) -> TestSymbol | None:
    containing = [
        item for item in index.by_file.get(file, []) if item.start <= lineno <= item.end
    ]
    if not containing:
        return None
    containing.sort(key=lambda item: (item.end - item.start, item.start))
    return containing[0]


def file_stats(repo: Path, files: list[str]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for rel in sorted(set(files)):
        path = repo / rel
        if not path.is_file():
            continue
        st = path.stat()
        stats[rel] = {"mtime_ns": int(st.st_mtime_ns), "size": int(st.st_size)}
    return stats


_IMPORT_ENV_MARKERS = (
    "modulenotfounderror",
    "importerror",
    "no module named",
)


def _call_phase_normal_failure(when: str, message: str) -> bool:
    """호출 단계의 AssertionError·일반 실패는 환경 문제가 아니다.

    longrepr 에 rhwp·한글 같은 키워드가 있어도 call 단계 실패를 env_error 로
    올리지 않는다. import/수집 오류는 여기서 제외해 기존 env 판정을 유지한다.
    """
    if (when or "").strip().lower() != "call":
        return False
    lowered = (message or "").lower()
    if any(token in lowered for token in _IMPORT_ENV_MARKERS):
        return False
    return True


def is_environment_blocker(message: str, *, when: str = "") -> bool:
    if _call_phase_normal_failure(when, message):
        return False
    text = message or ""
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in _ENV_MARKERS):
        return True
    if "filenotfounderror" in lowered and (".hwpx" in lowered or ".hwp" in lowered):
        if any(token in lowered for token in ("data/", "data\\", "sample", "gitignor")):
            return True
    return False


def status_from_outcomes(*, missing: list[str], nodes: list[dict[str, Any]]) -> str:
    """Derive a rule status from one verification run. VERIFIED requires every node passed."""
    real_fail = [node for node in nodes if node.get("outcome") in {"failed", "error"}]
    blocked = [node for node in nodes if node.get("outcome") in {"skipped", "env_error"}]
    if real_fail:
        return FAILING
    if missing or not nodes:
        return MISSING_GUARD
    if blocked:
        return ENV_SKIPPED
    if all(node.get("outcome") == "passed" for node in nodes):
        return VERIFIED
    return UNVERIFIED


def reason_for(status: str, *, missing: list[str], nodes: list[dict[str, Any]], head: str = "") -> str:
    if status == VERIFIED:
        return f"현재 HEAD {head[:10]}에서 가드 테스트 {len(nodes)}개가 모두 통과했습니다."
    if status == FAILING:
        bad = [node for node in nodes if node.get("outcome") in {"failed", "error"}]
        parts = []
        for node in bad[:6]:
            message = str(node.get("message") or "").strip().replace("\n", " ")
            parts.append(f"{node.get('nodeid')}: {message[:180]}".rstrip(": "))
        extra = ""
        if missing:
            extra = " 없는 참조: " + "; ".join(missing[:4])
        return f"실패 {len(bad)}건. " + " | ".join(parts) + extra
    if status == MISSING_GUARD:
        detail = "; ".join(missing[:8]) or "가드 테스트 노드가 없습니다."
        return f"가드 테스트 참조를 확인하지 못했습니다. {detail}"
    if status == ENV_SKIPPED:
        blocked = [node for node in nodes if node.get("outcome") in {"skipped", "env_error"}]
        parts = []
        for node in blocked[:6]:
            message = str(node.get("message") or "").strip().replace("\n", " ")
            parts.append(f"{node.get('nodeid')}: {message[:160]}".rstrip(": "))
        return "환경 때문에 통과로 볼 수 없습니다. " + " | ".join(parts)
    if status == NOT_RUN:
        return "현재 HEAD에서 아직 가드 테스트를 실행하지 않았습니다."
    if status == UNVERIFIED:
        return "저장된 검증 결과가 현재 HEAD 또는 테스트 파일과 달라 검증됨으로 표시하지 않습니다."
    if status == HUMAN_RULE:
        return "사람 판단 규칙입니다. 자동 검증 대상이 아닙니다."
    if status == GAP:
        return "기계화 공백(gap)입니다."
    if status == DEAD_RULE:
        return "guard_ref 가 비어 있습니다."
    return status


def _record_fresh(record: dict[str, Any] | None, *, head: str, guard_ref: str, stats: dict[str, Any]) -> bool:
    if not record or not head:
        return False
    if str(record.get("head") or "") != head:
        return False
    if str(record.get("guard_ref") or "") != guard_ref:
        return False
    cached_files = record.get("files")
    if not isinstance(cached_files, dict) or cached_files != stats:
        return False
    return True


def _nodes_of(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not record:
        return []
    nodes = record.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [node for node in nodes if isinstance(node, dict)]


def _missing_of(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return []
    missing = record.get("missing")
    if not isinstance(missing, list):
        return []
    return [str(item) for item in missing if str(item).strip()]


def build_wiring(
    rule: dict[str, Any],
    *,
    code: str,
    repo: Path,
    cache_rules: dict[str, Any],
    head: str,
    index: GuardIndex,
    include_tests: bool = False,
) -> dict[str, Any]:
    """Status shown on the console. Never VERIFIED without a fresh all-pass record."""
    category = str(rule.get("category", "")).strip()
    guard_ref = str(rule.get("guard_ref", "")).strip()
    record = cache_rules.get(code) if isinstance(cache_rules.get(code), dict) else None
    base = {
        "guard_declared": bool(guard_ref),
        "registry": True,
        "head": head,
        "stale": False,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0,
        "missing": [],
        "tests": [],
    }
    if category == "judgment":
        return _finish(base, HUMAN_RULE, reason_for(HUMAN_RULE, missing=[], nodes=[]), include_tests)
    if category == "gap":
        return _finish(base, GAP, reason_for(GAP, missing=[], nodes=[]), include_tests)
    if not guard_ref:
        return _finish(base, DEAD_RULE, reason_for(DEAD_RULE, missing=[], nodes=[]), include_tests)

    resolved = resolve_guard(guard_ref, repo, index)
    stats = file_stats(repo, resolved.files)
    fresh = _record_fresh(record, head=head, guard_ref=guard_ref, stats=stats)
    cached_nodes = _nodes_of(record) if fresh else []
    cached_missing = _missing_of(record) if fresh else []
    proven = status_from_outcomes(missing=cached_missing, nodes=cached_nodes) if fresh else None
    record_error = str(record.get("error") or "").strip() if fresh and record else ""

    if fresh and proven == FAILING:
        status = FAILING
        missing = cached_missing
        nodes = cached_nodes
    elif fresh and record_error:
        status = UNVERIFIED
        missing = cached_missing
        nodes = cached_nodes
        base["stale"] = False
        base["missing"] = missing
        base["tests"] = nodes
        counts = _count_nodes(nodes)
        base.update(counts)
        if not include_tests:
            base["tests"] = []
        reason = reason_for(UNVERIFIED, missing=missing, nodes=nodes, head=head)
        return _finish(base, UNVERIFIED, f"{reason} {record_error}".strip(), include_tests)
    elif resolved.missing:
        status = MISSING_GUARD
        missing = resolved.missing
        nodes = cached_nodes
    elif not record:
        status = NOT_RUN
        missing = []
        nodes = []
    elif not fresh:
        status = UNVERIFIED
        missing = []
        nodes = _nodes_of(record)
        base["stale"] = True
    else:
        status = proven or UNVERIFIED
        missing = cached_missing
        nodes = cached_nodes
        if status == VERIFIED and not _pass_proof(nodes, missing):
            status = UNVERIFIED

    if status == VERIFIED and (not fresh or not _pass_proof(nodes, missing)):
        status = UNVERIFIED
        base["stale"] = not fresh

    base["missing"] = missing
    base["tests"] = nodes if include_tests or status != NOT_RUN else []
    if not include_tests and status == NOT_RUN:
        base["tests"] = []
    counts = _count_nodes(nodes if status != NOT_RUN else [])
    base.update(counts)
    if not include_tests:
        base["tests"] = []
    return _finish(base, status, reason_for(status, missing=missing, nodes=nodes, head=head), include_tests)


def _pass_proof(nodes: list[dict[str, Any]], missing: list[str]) -> bool:
    return bool(nodes) and not missing and all(node.get("outcome") == "passed" for node in nodes)


def _count_nodes(nodes: list[dict[str, Any]]) -> dict[str, int]:
    passed = sum(1 for node in nodes if node.get("outcome") == "passed")
    failed = sum(1 for node in nodes if node.get("outcome") in {"failed", "error"})
    skipped = sum(1 for node in nodes if node.get("outcome") in {"skipped", "env_error"})
    return {"passed": passed, "failed": failed, "skipped": skipped, "total": len(nodes)}


def _finish(base: dict[str, Any], status: str, reason: str, include_tests: bool) -> dict[str, Any]:
    base["status"] = status
    base["overall"] = status
    base["reason"] = reason
    if not include_tests:
        base["tests"] = []
    return base


def git_head(repo: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _pytest_argv() -> list[str]:
    return [sys.executable, "-m", "pytest"]


def _pythonpath(repo: Path) -> str:
    app_dir = Path(__file__).resolve().parents[2]
    current = os.environ.get("PYTHONPATH", "")
    parts = [str(app_dir)]
    if current:
        parts.append(current)
    return os.pathsep.join(parts)


def canonical_nodeid(nodeid: str) -> str:
    """Keep pytest's ``\\uXXXX`` parameter escapes. Only normalize the file path."""
    text = (nodeid or "").strip()
    if "::" not in text:
        return text.replace("\\", "/")
    file, rest = text.split("::", 1)
    return file.replace("\\", "/") + "::" + rest


def parent_nodeid(nodeid: str) -> str:
    """Function id without ``[param]``. Pytest runs every parameter of that test."""
    text = canonical_nodeid(nodeid)
    if "::" not in text:
        return text
    file, rest = text.split("::", 1)
    parts = rest.split("::")
    parts[-1] = parts[-1].split("[", 1)[0]
    return file + "::" + "::".join(parts)


def execution_targets(targets: list[str]) -> list[str]:
    parents: list[str] = []
    seen: set[str] = set()
    for target in targets:
        parent = parent_nodeid(target)
        if parent and parent not in seen:
            seen.add(parent)
            parents.append(parent)
    return parents


def collect_pytest_nodes(repo: Path, files: list[str], *, timeout: int = 300) -> tuple[dict[str, list[str]], str]:
    if not files:
        return {}, ""
    report_dir = Path(tempfile.mkdtemp(prefix="lrule-collect-"))
    collect_path = report_dir / "nodes.txt"
    cmd = [
        *_pytest_argv(),
        "--rootdir",
        str(repo),
        "--confcutdir",
        str(repo),
        "-p",
        "auto_write.services.lrule_verification",
        "--collect-only",
        "-q",
        *files,
    ]
    env = {
        **os.environ,
        "PYTHONPATH": _pythonpath(repo),
        "PYTHONIOENCODING": "utf-8",
        "LRULE_VERIFY_COLLECT": str(collect_path),
    }
    try:
        try:
            proc = subprocess.run(
                cmd,
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {}, "pytest collect timeout"
        except OSError as exc:
            return {}, f"pytest collect could not start: {type(exc).__name__}: {exc}"
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
        grouped: dict[str, list[str]] = {file: [] for file in files}
        if collect_path.is_file():
            repo_prefix = str(repo).replace("\\", "/") + "/"
            for line in collect_path.read_text(encoding="utf-8", errors="replace").splitlines():
                nodeid = canonical_nodeid(line)
                if ".py::" not in nodeid:
                    continue
                file = nodeid.split("::", 1)[0]
                if file.startswith(repo_prefix):
                    file = file[len(repo_prefix) :]
                    nodeid = file + "::" + nodeid.split("::", 1)[1]
                grouped.setdefault(file, []).append(nodeid)
        error = ""
        if proc.returncode not in {0, 5} and not any(grouped.values()):
            error = output.strip()[-2000:] or f"pytest collect exit {proc.returncode}"
        elif proc.returncode not in {0, 5}:
            error = output.strip()[-2000:]
        return grouped, error
    finally:
        shutil.rmtree(report_dir, ignore_errors=True)


def _map_outcome(raw: str, message: str, *, when: str = "") -> str:
    if raw in {"passed", "xpassed"}:
        return "passed"
    if raw == "skipped":
        return "skipped"
    if raw in {"failed", "error", "xfailed"}:
        return "env_error" if is_environment_blocker(message, when=when) else "failed"
    return "failed"


def fold_reports(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    rank = {"failed": 5, "error": 5, "xfailed": 4, "skipped": 3, "xpassed": 2, "passed": 1}
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        nodeid = canonical_nodeid(str(row.get("nodeid") or ""))
        if not nodeid:
            continue
        raw = str(row.get("outcome") or "")
        message = str(row.get("message") or "")
        mapped = _map_outcome(raw, message, when=str(row.get("when") or ""))
        previous = best.get(nodeid)
        if previous is not None and rank.get(raw, 0) < rank.get(str(previous.get("_raw")), 0):
            continue
        best[nodeid] = {"nodeid": nodeid, "outcome": mapped, "message": message[:1200], "_raw": raw}
    return {
        nodeid: {"nodeid": nodeid, "outcome": item["outcome"], "message": item["message"]}
        for nodeid, item in best.items()
    }


def execute_pytest(repo: Path, targets: list[str], *, timeout: int = 1800) -> tuple[dict[str, dict[str, str]], str, int]:
    if not targets:
        return {}, "", 0
    report_dir = Path(tempfile.mkdtemp(prefix="lrule-verify-"))
    report_path = report_dir / "report.jsonl"
    cmd = [
        *_pytest_argv(),
        "--rootdir",
        str(repo),
        "--confcutdir",
        str(repo),
        "-p",
        "auto_write.services.lrule_verification",
        "-q",
        "--tb=line",
        *execution_targets(targets),
    ]
    env = {**os.environ, "PYTHONPATH": _pythonpath(repo), "LRULE_VERIFY_REPORT": str(report_path)}
    try:
        try:
            proc = subprocess.run(
                cmd,
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = _timeout_text(exc)
            partial = fold_reports(_read_jsonl(report_path))
            return partial, f"pytest timeout after {timeout}s\n{output}".strip(), 124
        except OSError as exc:
            return {}, f"pytest could not start: {type(exc).__name__}: {exc}", 127
        rows = _read_jsonl(report_path)
        folded = fold_reports(rows)
        output = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
        note = ""
        if not folded and proc.returncode not in {0, 5}:
            note = output[-2000:] or f"pytest exit {proc.returncode}"
        return folded, note, proc.returncode
    finally:
        shutil.rmtree(report_dir, ignore_errors=True)


def _timeout_text(exc: subprocess.TimeoutExpired) -> str:
    chunks = []
    for value in (exc.stdout, exc.stderr):
        if isinstance(value, bytes):
            chunks.append(value.decode("utf-8", errors="replace"))
        elif value:
            chunks.append(str(value))
    return "\n".join(chunks).strip()[-2000:]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


_REPORT_FH: Any = None


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    path = os.environ.get("LRULE_VERIFY_COLLECT", "").strip()
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        for item in items:
            handle.write(canonical_nodeid(str(getattr(item, "nodeid", "") or "")) + "\n")


def pytest_configure(config: Any) -> None:
    global _REPORT_FH
    path = os.environ.get("LRULE_VERIFY_REPORT", "").strip()
    if not path:
        return
    _REPORT_FH = open(path, "a", encoding="utf-8")


def pytest_unconfigure(config: Any) -> None:
    global _REPORT_FH
    if _REPORT_FH is not None:
        _REPORT_FH.close()
        _REPORT_FH = None


def pytest_runtest_logreport(report: Any) -> None:
    if _REPORT_FH is None:
        return
    failed = bool(getattr(report, "failed", False))
    skipped = bool(getattr(report, "skipped", False))
    if report.when != "call" and not failed and not skipped:
        return
    raw = str(getattr(report, "outcome", "") or "")
    if getattr(report, "wasxfail", None):
        raw = "xfailed" if raw == "skipped" else "xpassed"
    message = ""
    if raw not in {"passed", "xpassed"}:
        message = str(getattr(report, "longrepr", "") or "")[:1200]
    payload = {
        "nodeid": str(getattr(report, "nodeid", "") or ""),
        "when": str(getattr(report, "when", "") or ""),
        "outcome": raw,
        "message": message,
    }
    _REPORT_FH.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _REPORT_FH.flush()


def _node_name(nodeid: str) -> str:
    tail = nodeid.split("::")[-1]
    return tail.split("[", 1)[0]


def expand_targets(
    resolved: ResolvedGuard,
    collected: dict[str, list[str]],
    collect_error: str,
) -> tuple[list[str], list[str]]:
    nodeids: list[str] = []
    missing = list(resolved.missing)
    seen = set(nodeids)

    def add(nodeid: str) -> None:
        if nodeid not in seen:
            seen.add(nodeid)
            nodeids.append(nodeid)

    for file in resolved.whole_files:
        found = collected.get(file) or []
        if not found:
            detail = collect_error or "pytest가 테스트를 수집하지 못했습니다."
            missing.append(f"수집된 테스트 없음: {file} ({detail[:240]})")
            continue
        for nodeid in found:
            add(nodeid)
    for file, name in resolved.specific:
        matches = [
            nodeid
            for nodeid in (collected.get(file) or [])
            if nodeid.startswith(file + "::") and _node_name(nodeid) == name
        ]
        if not matches:
            missing.append(f"없는 테스트 노드: {file}::{name}")
            continue
        for nodeid in matches:
            add(nodeid)
    return nodeids, missing


Collector = Callable[[Path, list[str]], tuple[dict[str, list[str]], str]]
Executor = Callable[[Path, list[str]], tuple[dict[str, dict[str, str]], str, int]]


def verify_lessons(
    lessons: list[dict[str, Any]],
    *,
    repo: Path,
    index: GuardIndex,
    head: str,
    codes: set[str] | None,
    rule_code_fn: Callable[[dict[str, Any]], str],
    collect: Collector = collect_pytest_nodes,
    execute: Executor = execute_pytest,
) -> dict[str, dict[str, Any]]:
    """Run guard tests for mechanized lessons and return cache records keyed by rule code."""
    if not head:
        raise RuntimeError("git HEAD를 확인할 수 없어 VERIFIED로 기록하지 않습니다.")
    selected: list[tuple[str, dict[str, Any], ResolvedGuard]] = []
    for rule in lessons:
        if str(rule.get("category", "")).strip() != "mechanized":
            continue
        code = rule_code_fn(rule)
        if codes is not None and code not in codes:
            continue
        selected.append((code, rule, resolve_guard(str(rule.get("guard_ref", "")), repo, index)))

    files: list[str] = []
    for _code, _rule, resolved in selected:
        for file in resolved.files:
            if file not in files:
                files.append(file)
    collected, collect_error = collect(repo, files) if files else ({}, "")
    ran_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    records: dict[str, dict[str, Any]] = {}
    pending: list[tuple[str, dict[str, Any], list[str], list[str]]] = []
    all_nodeids: list[str] = []

    for code, rule, resolved in selected:
        guard_ref = str(rule.get("guard_ref", "")).strip()
        nodeids, missing = expand_targets(resolved, collected, collect_error)
        if not nodeids:
            nodes: list[dict[str, str]] = []
            if collect_error and resolved.has_targets and is_environment_blocker(collect_error):
                nodes = [
                    {"nodeid": f"{file}::COLLECTION", "outcome": "env_error", "message": collect_error[:1200]}
                    for file in resolved.files
                ]
            elif collect_error and resolved.has_targets and not missing:
                nodes = [
                    {"nodeid": f"{file}::COLLECTION", "outcome": "failed", "message": collect_error[:1200]}
                    for file in resolved.files
                ]
            records[code] = _record(
                head=head,
                guard_ref=guard_ref,
                repo=repo,
                files=resolved.files,
                missing=missing or ["가드 테스트 노드가 없습니다."],
                nodes=nodes,
                ran_at=ran_at,
                error="",
            )
            continue
        pending.append((code, rule, nodeids, missing))
        for nodeid in nodeids:
            if nodeid not in all_nodeids:
                all_nodeids.append(nodeid)

    outcomes, run_error, returncode = execute(repo, all_nodeids) if all_nodeids else ({}, "", 0)
    invocation_error = bool(run_error) and not outcomes and returncode != 124
    for code, rule, nodeids, missing in pending:
        guard_ref = str(rule.get("guard_ref", "")).strip()
        nodes: list[dict[str, str]] = []
        absent = list(missing)
        for nodeid in nodeids:
            found = outcomes.get(canonical_nodeid(nodeid))
            if found is None:
                if returncode == 124 or invocation_error:
                    continue
                if run_error:
                    nodes.append({"nodeid": nodeid, "outcome": "failed", "message": run_error[:1200]})
                else:
                    absent.append(f"결과 없음: {nodeid}")
                continue
            nodes.append(found)
        error = ""
        if returncode == 124:
            error = "pytest timeout"
        elif invocation_error:
            error = run_error[:1200]
        records[code] = _record(
            head=head,
            guard_ref=guard_ref,
            repo=repo,
            files=sorted({nodeid.split("::", 1)[0] for nodeid in nodeids}),
            missing=absent,
            nodes=nodes,
            ran_at=ran_at,
            error=error,
        )
    return records


def _record(
    *,
    head: str,
    guard_ref: str,
    repo: Path,
    files: list[str],
    missing: list[str],
    nodes: list[dict[str, Any]],
    ran_at: str,
    error: str,
) -> dict[str, Any]:
    dedup_missing: list[str] = []
    for item in missing:
        if item not in dedup_missing:
            dedup_missing.append(item)
    return {
        "head": head,
        "guard_ref": guard_ref,
        "files": file_stats(repo, files),
        "missing": dedup_missing,
        "nodes": [
            {
                "nodeid": str(node.get("nodeid") or ""),
                "outcome": str(node.get("outcome") or ""),
                "message": str(node.get("message") or "")[:1200],
            }
            for node in nodes
        ],
        "ran_at": ran_at,
        "error": error,
    }


def is_success_status(status: str) -> bool:
    return status in _SUCCESS_STATUSES
