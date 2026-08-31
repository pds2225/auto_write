"""L105 — SKILL.md YAML frontmatter 를 엄격 파싱한다.

``description: [한글] …`` 은 흐름 시퀀스로 파싱되는 깨진 YAML 이다.
관대한 스플리터가 숨기지 못하게 ``yaml.safe_load`` 로 검증한다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_BROKEN_DESC_RE = re.compile(r"(?m)^description:\s*\[")


def split_frontmatter(text: str) -> tuple[str, str]:
    raw = (text or "").lstrip("\ufeff")
    if not raw.startswith("---"):
        raise ValueError("SKILL.md 에 YAML frontmatter 가 없습니다")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter 종결 --- 가 없습니다")
    return parts[1], parts[2]


def parse_skill_frontmatter(text: str) -> dict[str, Any]:
    import yaml

    fm, _body = split_frontmatter(text)
    if _BROKEN_DESC_RE.search(fm):
        raise ValueError(
            "L105: description: [한글] … 은 깨진 YAML 이다 — 스칼라(>-)를 써라"
        )
    data = yaml.safe_load(fm)
    if not isinstance(data, dict):
        raise ValueError("frontmatter 가 매핑이 아닙니다")
    desc = data.get("description")
    if isinstance(desc, list):
        raise ValueError("L105: description 이 시퀀스로 파싱됨 — [한글] 훅 금지")
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError("description 은 비어 있지 않은 문자열이어야 합니다")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name 이 없습니다")
    return data


def iter_skill_md(repo_root: str | Path) -> list[Path]:
    root = Path(repo_root) / ".claude" / "skills"
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*/SKILL.md") if p.is_file())


def collect_skill_frontmatter_errors(repo_root: str | Path) -> list[str]:
    root = Path(repo_root)
    errors: list[str] = []
    for path in iter_skill_md(root):
        try:
            parse_skill_frontmatter(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
    return errors
