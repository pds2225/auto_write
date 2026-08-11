# -*- coding: utf-8 -*-
"""Full L-ID matrix for Lusalka vs resume-l-rules SKILL.md. Report-only."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

BASE = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
)
TARGET = BASE + r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
BLANK = BASE + r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식(0).hwp"

SKILL_IDS = [
    "L001", "L002", "L003", "L005", "L009", "L011", "L019", "L023", "L024", "L025",
    "L032", "L034", "L035", "L036", "L037", "L038", "L039", "L040", "L041", "L042",
    "L043", "L044", "L060", "L061", "L062",
]


def texts_in(obj, out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        if "Text" in obj and isinstance(obj["Text"], dict):
            out.append(obj["Text"])
        for v in obj.values():
            texts_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            texts_in(v, out)
    return out


def cell_plain(cell) -> str:
    return "".join((t.get("text") or "") for t in texts_in(cell))


def para_plain(para) -> str:
    return "".join((t.get("text") or "") for t in texts_in(para))


def para_styles(para):
    return [t.get("style") or {} for t in texts_in(para)]


def iter_paras(content):
    for i, item in enumerate(content):
        if isinstance(item, dict) and "Paragraph" in item:
            yield i, item["Paragraph"]


def find_tables(obj, acc=None):
    if acc is None:
        acc = []
    if isinstance(obj, dict):
        if "Table" in obj:
            acc.append(obj["Table"])
        for v in obj.values():
            find_tables(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            find_tables(v, acc)
    return acc


def dump_all_cells(data):
    rows = []
    for ti, t in enumerate(find_tables(data["sections"])):
        for ri, row in enumerate(t.get("rows") or []):
            for ci, cell in enumerate(row.get("cells") or []):
                tx = cell_plain(cell).strip()
                styles = [t.get("style") or {} for t in texts_in(cell)]
                rows.append((ti, ri, ci, tx, styles))
    return rows


def main():
    data = json.loads(unhwp.parse(TARGET).json)
    blank = json.loads(unhwp.parse(BLANK).json)
    sec = data["sections"][0]["content"]
    cells = dump_all_cells(data)
    blank_cells = dump_all_cells(blank)

    print("=== ALL NON-EMPTY TABLE CELLS ===")
    for ti, ri, ci, tx, styles in cells:
        if not tx:
            continue
        cols = [f"{s.get('font_name')} {s.get('font_size')} {s.get('color')}" for s in styles[:3]]
        print(f"T{ti}r{ri}c{ci}: {tx[:120]}")
        if any((s.get("color") or "").upper() not in ("#000000", "", "NONE") for s in styles):
            print(f"   STYLES: {cols}")

    print("\n=== CHECKBOX CELLS ===")
    for ti, ri, ci, tx, styles in cells:
        if "□" in tx or "■" in tx or "☑" in tx or "" in tx:
            print(f"T{ti}r{ri}c{ci}: {tx}")

    print("\n=== FORM CHROME (1-1 / ㅇ / 1-2) STYLES ===")
    for i, p in iter_paras(sec):
        tx = para_plain(p).strip()
        if tx.startswith(("1-1.", "1-2.", "ㅇ ")) or tx.startswith("ㅇ"):
            if any(k in tx for k in ("창업 동기", "보유 역량", "해결하고자", "사업 아이템", "아이템 개요")):
                st = [
                    f"{s.get('font_name')} {s.get('font_size')}pt {s.get('color')} bold={s.get('bold')}"
                    for s in para_styles(p)[:4]
                ]
                print(f"P{i}: {tx[:70]}")
                print(f"  {st}")

    print("\n=== BODY FILL STYLES (leading '-') ===")
    blue_body = 0
    black_body = 0
    for i, p in iter_paras(sec):
        tx = para_plain(p).strip()
        if not tx.startswith("-"):
            continue
        styles = para_styles(p)
        colors = {(s.get("color") or "").upper() for s in styles}
        fonts = {(s.get("font_name"), s.get("font_size")) for s in styles}
        if any("0000FF" in c for c in colors):
            blue_body += 1
        if colors <= {"#000000", ""} or colors == {"#000000"}:
            black_body += 1
        if i < 40:
            print(f"P{i}: colors={colors} fonts={fonts} text={tx[:50]}")
    print(f"SUMMARY body '-': blueish={blue_body} blackish={black_body}")

    # Blank form chrome vs filled for same labels
    print("\n=== BLANK vs FILLED: label style sample ===")
    def label_style_map(d):
        m = {}
        for i, p in iter_paras(d["sections"][0]["content"]):
            tx = para_plain(p).strip()
            if tx.startswith("1-1.") or tx.startswith("1-2.") or (
                tx.startswith("ㅇ") and ("보유" in tx or "해결" in tx or "아이템 개요" in tx)
            ):
                key = tx[:20]
                m[key] = [
                    f"{s.get('font_name')}|{s.get('font_size')}|{s.get('color')}"
                    for s in para_styles(p)[:2]
                ]
        return m

    bm = label_style_map(blank)
    fm = label_style_map(data)
    for k in sorted(set(bm) | set(fm)):
        print(f"  [{k}]")
        print(f"    blank: {bm.get(k)}")
        print(f"    fill : {fm.get(k)}")
        print(f"    same : {bm.get(k) == fm.get(k)}")

    # Signature / date near end
    print("\n=== TAIL PARAS (last 15) ===")
    paras = list(iter_paras(sec))
    for i, p in paras[-15:]:
        print(f"P{i}: {para_plain(p).strip()[:140]}")

    # Name field values
    print("\n=== NAME-ADJACENT ===")
    for ti, ri, ci, tx, styles in cells:
        if any(k in tx for k in ("성명", "함서영", "박다솜", "이름")):
            print(f"T{ti}r{ri}c{ci}: {tx}")

    # Empty value cells count in applicant/company tables
    print("\n=== EMPTY VALUE CELLS in T5/T6/T7 ===")
    for ti, ri, ci, tx, styles in cells:
        if ti in (5, 6, 7, 8, 9) and not tx:
            # show neighbor label if any
            pass
    # better: print row as label pairs
    for ti in (5, 6, 7, 9):
        print(f"-- T{ti} --")
        t = find_tables(data["sections"])[ti]
        for ri, row in enumerate(t.get("rows") or []):
            vals = [cell_plain(c).strip().replace("\n", " ")[:40] for c in row.get("cells") or []]
            print(f"  r{ri}: {vals}")

    # resources / images
    print("\n=== RESOURCES ===")
    print(type(data.get("resources")), list(data.get("resources") or [])[:5] if isinstance(data.get("resources"), list) else data.get("resources"))
    print("metadata", data.get("metadata"))

    # Compare body blue in blank
    print("\n=== BLANK body leading '-' styles ===")
    b_blue = 0
    for i, p in iter_paras(blank["sections"][0]["content"]):
        tx = para_plain(p).strip()
        if not tx.startswith("-") and "예" not in tx[:3]:
            continue
        styles = para_styles(p)
        colors = {(s.get("color") or "").upper() for s in styles}
        if any("0000FF" in c or "0000F" in c for c in colors):
            b_blue += 1
            if b_blue <= 5:
                print(f"  P{i} {colors} {tx[:60]}")
    print(f"blank blue-ish paras scanned approx={b_blue}")

    # Count blue paras in blank that look like example
    print("\n=== BLANK example-looking paras (blue) ===")
    n = 0
    for i, p in iter_paras(blank["sections"][0]["content"]):
        styles = para_styles(p)
        colors = {(s.get("color") or "").upper() for s in styles}
        if not any("0000FF" in c for c in colors):
            continue
        tx = para_plain(p).strip()
        n += 1
        if n <= 8:
            print(f"  P{i}: {tx[:80]}")
    print(f"blank blue paras total={n}")

    filled_blue = 0
    for i, p in iter_paras(sec):
        styles = para_styles(p)
        colors = {(s.get("color") or "").upper() for s in styles}
        if any("0000FF" in c for c in colors):
            filled_blue += 1
    print(f"filled blue paras total={filled_blue}")


if __name__ == "__main__":
    main()
