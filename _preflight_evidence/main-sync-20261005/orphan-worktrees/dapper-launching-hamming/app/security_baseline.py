from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


MAX_SCANNED_BYTES = 2 * 1024 * 1024
TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".cmd",
    ".css",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
SECRET_PATTERNS = {
    "SECRET_OPENAI_KEY": re.compile(r"\b" + "sk" + r"-[A-Za-z0-9_-]{20,}\b"),
    "SECRET_GOOGLE_KEY": re.compile(r"\b" + "AI" + r"za[0-9A-Za-z_-]{30,}\b"),
    "SECRET_GITHUB_TOKEN": re.compile(r"\b" + "gh" + r"[pousr]_[A-Za-z0-9]{30,}\b"),
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    path: str


def _normalized_path(path: str) -> str:
    normalized = str(PurePosixPath(str(path).replace("\\", "/")))
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def find_protected_path_rule(path: str) -> str | None:
    normalized = _normalized_path(path)
    lowered = normalized.lower()
    parts = PurePosixPath(lowered).parts
    name = PurePosixPath(lowered).name

    if name == ".env.example":
        return None
    if name == ".env" or name.startswith(".env."):
        return "PROTECTED_ENV_FILE"
    if parts and parts[0] in {"workspace", "results", "backup", "_workspace"}:
        return "PROTECTED_PROJECT_DATA"
    if any(part in {".browser-profile", "browser_profile", "user-data-dir"} for part in parts):
        return "PROTECTED_BROWSER_STATE"
    if name in {"cookies.json", "storage_state.json"}:
        return "PROTECTED_BROWSER_STATE"
    return None


def scan_text(path: str, text: str) -> list[Finding]:
    normalized = _normalized_path(path)
    return [
        Finding(rule_id=rule_id, path=normalized)
        for rule_id, pattern in SECRET_PATTERNS.items()
        if pattern.search(text)
    ]


def _tracked_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _should_scan_content(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name.lower() in {"dockerfile", "makefile"}


def scan_tracked_files(repo_root: Path) -> list[Finding]:
    root = repo_root.resolve()
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    for tracked_name in _tracked_files(root):
        normalized = _normalized_path(tracked_name)
        protected_rule = find_protected_path_rule(normalized)
        if protected_rule:
            key = (protected_rule, normalized)
            if key not in seen:
                findings.append(Finding(protected_rule, normalized))
                seen.add(key)

        path = root / Path(normalized)
        if not path.is_file() or not _should_scan_content(path):
            continue
        try:
            if path.stat().st_size > MAX_SCANNED_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for finding in scan_text(normalized, text):
            key = (finding.rule_id, finding.path)
            if key not in seen:
                findings.append(finding)
                seen.add(key)
    return sorted(findings, key=lambda item: (item.path, item.rule_id))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="추적 파일의 보호 경로와 고신뢰 Secret 패턴을 검사합니다."
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="검사할 Git 저장소")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        findings = scan_tracked_files(args.repo)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"[ERROR] SECURITY_SCAN_FAILED {type(exc).__name__}")
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id} {finding.path}")
        return 2
    print("[PASS] tracked files contain no protected data or high-confidence secrets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
