# -*- coding: utf-8 -*-
"""Scan 1-1 body blue runs (HY헤드라인M 20pt #0000FF) before edit."""
from __future__ import annotations

import json
import sys

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

HWP = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
    r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
)

data = json.loads(unhwp.parse(HWP).json)
content = data["sections"][0]["content"]

state = {"in_11": False}


def walk_paras(paras, loc: str) -> str | None:
    for pi, para in enumerate(paras or []):
        if not isinstance(para, dict):
            continue
        runs = para.get("content", [])
        full = "".join(
            (r.get("Text") or {}).get("text", "")
            for r in runs
            if isinstance(r, dict) and "Text" in r
        ).strip()
        if full.startswith("1-1."):
            state["in_11"] = True
            print(f"=== ENTER 1-1 @ {loc}/P{pi}: {full[:80]}")
        if full.startswith("1-2."):
            print(f"=== EXIT before 1-2 @ {loc}/P{pi}: {full[:80]}")
            state["in_11"] = False
            return "stop"
        if not state["in_11"]:
            continue
        for ri, run in enumerate(runs):
            if not isinstance(run, dict) or "Text" not in run:
                continue
            t = run["Text"]
            text = (t.get("text") or "").strip()
            st = t.get("style") or {}
            font = st.get("font_name", "?")
            size = st.get("font_size", 0)
            color = str(st.get("color", "?"))
            if "0000FF" in color.upper() or "2E74B5" in color.upper():
                print(
                    f"{loc}/P{pi}/R{ri} | {font} {size}pt {color} | {text[:120]!r}"
                )
    return None


for i, item in enumerate(content):
    if not isinstance(item, dict):
        continue
    if "Table" in item:
        table = item["Table"]
        for ri, row in enumerate(table.get("rows", [])):
            for ci, cell in enumerate(row.get("cells", [])):
                if walk_paras(cell.get("content", []), f"T{i}/R{ri}/C{ci}") == "stop":
                    raise SystemExit(0)
    else:
        # top-level paragraph-like
        if walk_paras([item], f"TOP{i}") == "stop":
            break
