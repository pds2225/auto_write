# -*- coding: utf-8 -*-
"""글씨 겹침 우회 금지 — 편집 코드가 가짜 hp:linesegarray 를 심으면 실패.

한 줄 강제 캐시(vertpos=0 등)를 XML 에 다시 넣으면 한글이 새 글씨를 옛 좌표에
겹쳐 그린다. 엔진은 캐시를 지운다(L002). 스크립트가 다시 만들면 뿌리가 빠지지 않는다.
이 테스트는 SubElement / etree.Element / 문자열 XML 로 linesegarray 를 만드는
우회를 저장소 생산 코드에서 금지한다.
"""
from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]

# 생성만 금지. iter(_q("linesegarray")) / 주석 / 제거 코드는 허용.
_SYNTH_RES = (
    re.compile(
        r"SubElement\s*\(\s*[^)]*?(?:_q\(\s*['\"]linesegarray['\"]\s*\)|"
        r"['\"][^'\"]*linesegarray[^'\"]*['\"])",
        re.DOTALL,
    ),
    re.compile(
        r"(?:etree\.)?Element\s*\(\s*(?:_q\(\s*['\"]linesegarray['\"]\s*\)|"
        r"['\"][^'\"]*linesegarray[^'\"]*['\"])",
    ),
    re.compile(
        r"""fromstring\s*\(\s*[fFrRbB]*['\"][^'\"]*<(?:hp:)?linesegarray""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""[fF]['\"][^'\"]*<(?:hp:)?linesegarray""",
        re.IGNORECASE,
    ),
)


def test_synth_patterns_catch_element_and_xml_literal() -> None:
    assert _SYNTH_RES[0].search('etree.SubElement(p, _q("linesegarray"))')
    assert _SYNTH_RES[1].search('etree.Element(_q("linesegarray"))')
    assert _SYNTH_RES[2].search('etree.fromstring("<hp:linesegarray/>")')
    assert _SYNTH_RES[3].search('xml = f"<hp:linesegarray></hp:linesegarray>"')
    joined = "\n".join(p.pattern for p in _SYNTH_RES)
    assert "iter" not in joined
    sample_iter = 'for ls in root.iter(_q("linesegarray")):'
    assert not any(rx.search(sample_iter) for rx in _SYNTH_RES)


def test_no_production_code_synthesizes_linesegarray() -> None:
    hits: list[str] = []
    for path in _APP.rglob("*.py"):
        rel = path.relative_to(_APP).as_posix()
        if rel.startswith("tests/") or "/tests/" in rel:
            continue
        text = path.read_text(encoding="utf-8")
        if any(rx.search(text) for rx in _SYNTH_RES):
            hits.append(rel)
    assert hits == [], (
        "가짜 linesegarray 생성은 글씨 겹침을 재발시킨다. "
        "텍스트를 바꾼 뒤에는 _invalidate_lineseg/_set_cell_text 만 쓰라:\n  "
        + "\n  ".join(hits)
    )
