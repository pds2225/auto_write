# -*- coding: utf-8 -*-
"""Lusalka L-rule FULL audit against resume-l-rules SKILL.md IDs. Report-only."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

PATH = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
    r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
)

# Known source facts (박다솜 / 루살카 맥락) — for fabrication & name-match checks
KNOWN_NAMES = {"박다솜", "루살카", "Lusalka", "lusalka"}
FAB_MARKERS = [
    "[확인필요]",
    "[작성 필요]",
    "확인필요",
    "작성필요",
    "TODO",
    "TBD",
    "○○○",
    "XXX",
    "예시",
    "샘플",
]
PLACEHOLDER_PAT = re.compile(r"_{3,}|\.{3,}|…+|□|☐|○{2,}|ㅇ{2,}|\[?\s*확인필요\s*\]?|\[?\s*작성\s*필요\s*\]?")
DATE_PAT = re.compile(r"20\d{2}\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]?\s*\d{0,2}")
CHECK_MARKS = set("■☑✓✔√●◆")
EMPTY_CHECKS = set("□☐○◯")


def walk_paras(content):
    for i, item in enumerate(content):
        if "Paragraph" not in item:
            continue
        para = item["Paragraph"]
        runs = para.get("content", [])
        texts, styles = [], []
        for run in runs:
            if "Text" not in run:
                continue
            t = run["Text"]
            texts.append(t.get("text", "") or "")
            styles.append(t.get("style") or {})
        yield i, "".join(texts), styles, para


def cell_text(cell) -> str:
    parts = []
    for p in cell.get("paragraphs", []) or cell.get("content", []) or []:
        if isinstance(p, dict):
            if "Paragraph" in p:
                for run in p["Paragraph"].get("content", []):
                    if "Text" in run:
                        parts.append(run["Text"].get("text", "") or "")
            elif "text" in p:
                parts.append(p.get("text", "") or "")
    return "".join(parts)


def extract_tables(data):
    tables = []
    # unhwp may put tables inside sections content as Table nodes
    for sec in data.get("sections", []):
        for item in sec.get("content", []):
            if "Table" in item:
                tables.append(item["Table"])
    return tables


def flatten_all_text(data) -> str:
    chunks = []
    for sec in data.get("sections", []):
        for i, text, styles, para in walk_paras(sec.get("content", [])):
            chunks.append(text)
        for t in extract_tables_deep(sec.get("content", [])):
            for row in t.get("rows", []) or []:
                for cell in row.get("cells", []) or []:
                    chunks.append(cell_text(cell) if isinstance(cell, dict) else str(cell))
    return "\n".join(chunks)


def extract_tables_deep(content, out=None):
    if out is None:
        out = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if "Table" in item:
            out.append(item["Table"])
        for v in item.values():
            if isinstance(v, dict):
                extract_tables_deep([v], out)
            elif isinstance(v, list):
                extract_tables_deep(v, out)
    return out


def style_key(s: dict) -> str:
    return f"{s.get('font_name')}|{s.get('font_size')}|{s.get('color')}|{s.get('bold')}"


def main():
    data = json.loads(unhwp.parse(PATH).json)
    sec0 = data["sections"][0]["content"]
    all_text = flatten_all_text(data)
    paras = list(walk_paras(sec0))
    tables = extract_tables_deep(sec0)

    # --- dump overview ---
    print("=== META ===")
    print(f"path={PATH}")
    print(f"sections={len(data.get('sections', []))}")
    print(f"paras={len(paras)} tables={len(tables)}")
    print(f"text_len={len(all_text)}")

    # Style inventory for L011
    style_counts = Counter()
    blue_runs = []
    for i, text, styles, _ in paras:
        for s in styles:
            style_counts[style_key(s)] += 1
            color = (s.get("color") or "").upper().replace("#", "")
            if color and color not in ("000000", "000000FF", "FF000000", "0", "BLACK"):
                # heuristic: non-black
                if color not in ("FFFFFF", "FFFFFFFF"):
                    if any(c in color for c in ("0000FF", "0000F", "FF00", "00F")) or (
                        len(color) >= 6 and color[4:6] in ("FF", "FE", "FD") and color[0:4] == "0000"
                    ):
                        blue_runs.append((i, text[:60], s))
                    # also catch rgb blue-ish
                    if re.search(r"0000[89A-F]{2}|0000FF", color, re.I):
                        blue_runs.append((i, text[:60], s))

    print("\n=== TOP STYLES ===")
    for k, c in style_counts.most_common(15):
        print(f"  {c:4d}  {k}")

    print(f"\n=== NONBLACK/BLUE-ISH RUNS (sample) count={len(blue_runs)} ===")
    for row in blue_runs[:20]:
        print(" ", row)

    # Checkboxes
    check_hits = []
    empty_hits = []
    for i, text, styles, _ in paras:
        for ch in text:
            if ch in CHECK_MARKS:
                check_hits.append((i, text.strip()[:100]))
            if ch in EMPTY_CHECKS:
                empty_hits.append((i, text.strip()[:100]))
    # also in tables
    for ti, t in enumerate(tables):
        for ri, row in enumerate(t.get("rows", []) or []):
            for ci, cell in enumerate(row.get("cells", []) or []):
                tx = cell_text(cell) if isinstance(cell, dict) else str(cell)
                if any(c in tx for c in CHECK_MARKS):
                    check_hits.append((f"T{ti}r{ri}c{ci}", tx.strip()[:100]))
                if any(c in tx for c in EMPTY_CHECKS):
                    empty_hits.append((f"T{ti}r{ri}c{ci}", tx.strip()[:100]))

    print(f"\n=== CHECKED ({len(check_hits)}) ===")
    for h in check_hits[:40]:
        print(" ", h)
    print(f"=== EMPTY_CHECKS ({len(empty_hits)}) ===")
    for h in empty_hits[:40]:
        print(" ", h)

    # Dates
    dates = DATE_PAT.findall(all_text)
    print(f"\n=== DATES ({len(dates)}) ===")
    for d in dates[:30]:
        print(" ", repr(d))

    # Placeholders / confirm markers
    ph = []
    for i, text, styles, _ in paras:
        if PLACEHOLDER_PAT.search(text) or any(m in text for m in FAB_MARKERS):
            ph.append((i, text.strip()[:120]))
    print(f"\n=== PLACEHOLDER/FAB MARKERS ({len(ph)}) ===")
    for row in ph[:50]:
        print(" ", row)

    # Name-ish fields: look for 성명/이름 near values
    print("\n=== NAME/LABEL CONTEXT ===")
    for i, text, styles, _ in paras:
        if any(k in text for k in ("성명", "이름", "대표자", "신청자", "작성자")):
            print(f"  P{i}: {text.strip()[:120]}")

    # Keywords / specialty
    print("\n=== KEYWORD/FIELD CONTEXT ===")
    for i, text, styles, _ in paras:
        if any(k in text for k in ("키워드", "전문", "분야", "모집", "예술", "창업")):
            if len(text.strip()) < 200:
                print(f"  P{i}: {text.strip()}")

    # Pledge / oath
    print("\n=== PLEDGE/OATH CONTEXT ===")
    for i, text, styles, _ in paras:
        if any(k in text for k in ("서약", "동의", "확인서", "개인정보", "준수", "서약서")):
            print(f"  P{i}: {text.strip()[:150]}")

    # Section headers for resume-like structure
    print("\n=== SECTION HEADS ===")
    for i, text, styles, _ in paras:
        t = text.strip()
        if re.match(r"^(\d+[-.]|\d+\.|■|□|ㅇ|○)", t) or t.startswith(("1.", "2.", "3.", "4.", "Ⅰ", "Ⅱ", "Ⅲ")):
            if len(t) < 80:
                print(f"  P{i}: {t}")

    # Self-description / motivation length
    print("\n=== LONG PARAS (>80 chars) sample ===")
    longs = [(i, text.strip()) for i, text, _, _ in paras if len(text.strip()) > 80]
    print(f"count={len(longs)}")
    for i, t in longs[:15]:
        print(f"  P{i} ({len(t)}): {t[:160]}")

    # Images / pics
    pics = 0
    for sec in data.get("sections", []):
        blob = json.dumps(sec, ensure_ascii=False)
        pics += blob.count("Picture") + blob.count("Image") + blob.count("OLE")
    print(f"\n=== PIC/IMAGE token count ≈ {pics} ===")

    # Table shapes
    print("\n=== TABLES ===")
    for ti, t in enumerate(tables):
        rows = t.get("rows", []) or []
        ncols = max((len(r.get("cells", []) or []) for r in rows), default=0)
        print(f"  T{ti}: rows={len(rows)} cols≈{ncols}")
        # first 3 row texts
        for ri, row in enumerate(rows[:4]):
            cells = []
            for cell in row.get("cells", []) or []:
                tx = (cell_text(cell) if isinstance(cell, dict) else str(cell)).strip().replace("\n", " ")
                cells.append(tx[:40])
            print(f"    r{ri}: {cells}")

    # Fabrication heuristics: large numbers, fake company patterns
    print("\n=== NUMERIC CLAIMS ===")
    for m in re.finditer(r"\d{1,3}(?:,\d{3})+|\d+\s*%|\d+\s*억|\d+\s*만\s*원|\d+\s*명|\d+\s*건", all_text):
        start = max(0, m.start() - 30)
        end = min(len(all_text), m.end() + 30)
        snippet = all_text[start:end].replace("\n", " ")
        print(f"  {snippet}")

    # Dump full text to side file for manual grep
    out = Path(__file__).with_name("tmp_lusalka_lrule_text_dump.txt")
    out.write_text(all_text, encoding="utf-8")
    print(f"\n=== DUMPED TEXT -> {out} ({len(all_text)} chars) ===")

    # Structure keys of unhwp root
    print("\n=== ROOT KEYS ===", list(data.keys()))
    if "header" in data:
        print("header keys", list(data["header"].keys()) if isinstance(data["header"], dict) else type(data["header"]))


if __name__ == "__main__":
    main()
