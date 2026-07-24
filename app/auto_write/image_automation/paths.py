"""이미지 자동화 run 경로·익명 파일명 헬퍼."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

SCHEMA_VERSION = "1.0"
DEFAULT_RESULTS_ROOT = Path("results") / "image_runs"
ANON_NAME_RE = re.compile(r"^[a-z0-9][\w.\-]{0,120}$", re.IGNORECASE)


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def short_hash(value: str, n: int = 8) -> str:
    return value[:n]


def anonymous_upload_name(repo_name: str, file_sha256: str) -> str:
    """NotebookLM 업로드용 익명 파일명: <repo>-<sha8>.pdf"""
    safe_repo = re.sub(r"[^A-Za-z0-9._-]+", "_", repo_name).strip("._-") or "repo"
    return f"{safe_repo}-{short_hash(file_sha256)}.pdf"


def run_root(run_id: str, results_root: Path | None = None) -> Path:
    root = Path(results_root) if results_root is not None else DEFAULT_RESULTS_ROOT
    return root / run_id


def ensure_run_dirs(run_id: str, results_root: Path | None = None) -> dict[str, Path]:
    base = run_root(run_id, results_root)
    dirs = {
        "root": base,
        "slides": base / "slides",
        "downloads": base / "downloads",
        "receipts": base / "receipts",
        "citations": base / "citations",
        "sidecar": base / "sidecar",
        "browser_profile": base / "browser_profile",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def is_safe_anon_name(name: str) -> bool:
    return bool(ANON_NAME_RE.match(name)) and ".." not in name and "/" not in name and "\\" not in name
