# -*- coding: utf-8 -*-
"""글씨 겹침 우회 금지 — 편집 코드가 가짜 hp:linesegarray 를 심으면 실패.

한 줄 강제 캐시(vertpos=0 등)를 XML 에 다시 넣으면 한글이 새 글씨를 옛 좌표에
겹쳐 그린다. 엔진은 캐시를 지운다(L002). 스크립트가 다시 만들면 뿌리가 빠지지 않는다.
이 테스트는 SubElement(..., linesegarray) 생성을 저장소에서 금지한다.
"""
from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
_CREATE_RE = re.compile(
    r"SubElement\s*\(\s*[^)]*?(?:_q\(\s*['\"]linesegarray['\"]\s*\)|"
    r"['\"][^'\"]*linesegarray[^'\"]*['\"])",
    re.DOTALL,
)


def test_no_production_code_synthesizes_linesegarray() -> None:
    hits: list[str] = []
    for path in _APP.rglob("*.py"):
        rel = path.relative_to(_APP).as_posix()
        if rel.startswith("tests/") or "/tests/" in rel:
            continue
        text = path.read_text(encoding="utf-8")
        if _CREATE_RE.search(text):
            hits.append(rel)
    assert hits == [], (
        "가짜 linesegarray 생성은 글씨 겹침을 재발시킨다. "
        "텍스트를 바꾼 뒤에는 _invalidate_lineseg/_set_cell_text 만 쓰라:\n  "
        + "\n  ".join(hits)
    )
