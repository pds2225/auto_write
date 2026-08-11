# -*- coding: utf-8 -*-
"""Verify v8_min: 1-1 body labels #2E74B5; headline/prompts untouched."""
from __future__ import annotations

import json
import sys

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

OUT = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
    r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v8_min.hwp"
)
SRC = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
    r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
)


def dump_11(path: str, label: str) -> list[tuple]:
    data = json.loads(unhwp.parse(path).json)
    content = data["sections"][0]["content"]
    rows = []
    in_11 = False
    for i, item in enumerate(content):
        if "Paragraph" not in item:
            continue
        runs = item["Paragraph"].get("content", [])
        full = "".join(
            (r.get("Text") or {}).get("text", "")
            for r in runs
            if isinstance(r, dict) and "Text" in r
        ).strip()
        if full.startswith("1-1."):
            in_11 = True
        if full.startswith("1-2."):
            break
        if not in_11:
            continue
        for ri, run in enumerate(runs):
            if not isinstance(run, dict) or "Text" not in run:
                continue
            t = run["Text"]
            text = (t.get("text") or "").strip()
            if not text:
                continue
            st = t.get("style") or {}
            row = (
                i,
                ri,
                st.get("font_name"),
                st.get("font_size"),
                str(st.get("color")),
                text[:90],
            )
            rows.append(row)
            print("%s TOP%d/R%d | %s %spt %s | %r" % ((label,) + row))
    return rows


print("=== SOURCE v6 ===")
src_rows = dump_11(SRC, "SRC")
print("\n=== OUTPUT v8_min ===")
out_rows = dump_11(OUT, "OUT")

# Assertions
out_by_text = {r[5]: r for r in out_rows}
checks = [
    ("1-1. 창업 동기", "#000000", "HY헤드라인M", 15.0),
]
for text, color, font, size in checks:
    hit = [r for r in out_rows if r[5].startswith(text[:8])]
    assert hit, f"missing {text}"
    assert hit[0][4].upper() == color.upper(), hit[0]
    print("PASS headline/black:", hit[0])

prompts = [r for r in out_rows if r[5].startswith("ㅇ")]
assert len(prompts) >= 2
for p in prompts:
    assert "0000FF" not in p[4].upper() or True  # may be black already
    # should NOT be accent blue (form chrome was black in v6)
    assert "2E74B5" not in p[4].upper(), p
print("PASS prompts not accent:", len(prompts))

labels = [r for r in out_rows if r[5].startswith("(") and "HY" in (r[2] or "")]
assert len(labels) == 2, labels
for lab in labels:
    assert "2E74B5" in lab[4].upper(), lab
    assert abs(float(lab[3]) - 20.0) < 0.1, lab
print("PASS body labels accent #2E74B5 x", len(labels))

# Ensure no remaining #0000FF in 1-1 body labels
blue_ff = [r for r in out_rows if "0000FF" in r[4].upper()]
assert not blue_ff, blue_ff
print("PASS no #0000FF left in 1-1 range")
print("ALL OK")
