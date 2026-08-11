# -*- coding: utf-8 -*-
"""L-rule evidence dump for Lusalka v6 HWP (report-only)."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

PATH = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
    r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
)


def walk(obj, acc):
    if isinstance(obj, dict):
        if "Text" in obj and isinstance(obj["Text"], dict):
            t = obj["Text"]
            text = t.get("text") or ""
            style = t.get("style") or {}
            if text:
                acc.append(
                    {
                        "text": text,
                        "font": style.get("font_name"),
                        "size": style.get("font_size"),
                        "color": style.get("color"),
                        "bold": style.get("bold"),
                    }
                )
        for v in obj.values():
            walk(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, acc)


def main() -> None:
    data = json.loads(unhwp.parse(PATH).json)
    runs = []
    for sec in data.get("sections", []):
        walk(sec, runs)

    full = "".join(r["text"] for r in runs)
    print("=== META ===")
    print(f"sections={len(data.get('sections', []))} runs={len(runs)} chars={len(full)}")

    # Colors
    colors = Counter((r["color"] or "None") for r in runs if r["text"].strip())
    print("\n=== COLORS (non-empty runs) ===")
    for c, n in colors.most_common():
        print(f"  {c}: {n}")

    non_black = [
        r
        for r in runs
        if r["text"].strip()
        and r["color"]
        and str(r["color"]).upper() not in ("#000000", "000000", "NONE", "NONE")
        and str(r["color"]).lower() not in ("auto", "none", "null")
    ]
    # filter truly non-black hex
    colored = []
    for r in runs:
        if not r["text"].strip():
            continue
        c = (r["color"] or "").upper().replace("#", "")
        if not c or c in ("000000", "NONE", "AUTO", "NULL"):
            continue
        if re.fullmatch(r"[0-9A-F]{6}", c) and c != "000000":
            colored.append(r)
    print(f"\n=== COLORED HEX RUNS (n={len(colored)}) sample ===")
    for r in colored[:40]:
        print(f"  {r['color']} {r['font']} {r['size']}pt | {r['text'][:80]!r}")
    if len(colored) > 40:
        print(f"  ... +{len(colored)-40} more")

    # Form chrome 1-1 / ㅇ
    print("\n=== FORM CHROME (1-x / leading ㅇ) ===")
    paras = []
    # rebuild para-ish by scanning section paragraphs if available
    content = data["sections"][0]["content"]
    for i, item in enumerate(content):
        if "Paragraph" not in item:
            continue
        para = item["Paragraph"]
        texts, styles = [], []
        for run in para.get("content", []):
            if "Text" not in run:
                continue
            t = run["Text"]
            tx = t.get("text") or ""
            if not tx:
                continue
            texts.append(tx)
            s = t.get("style") or {}
            styles.append(
                f"{s.get('font_name')} {s.get('font_size')}pt {s.get('color')}"
            )
        text = "".join(texts).strip()
        if not text:
            continue
        if re.match(r"^\d+-\d+\.", text) or text.startswith("ㅇ"):
            print(f"P{i}: {text[:90]}")
            print(f"     styles: {styles[:3]}")

    # Keywords / fields
    keys = [
        "사업자",
        "법인",
        "매출",
        "고용",
        "투자",
        "예비창업",
        "성명",
        "대표",
        "서명",
        "인)",
        "확인필요",
        "작성 필요",
        "[확인",
        "OOO",
        "○○",
        "010-",
        "루살카",
        "Lusalka",
        "체크",
        "□",
        "■",
        "☑",
        "모집분야",
        "키워드",
        "서약",
        "동의",
    ]
    print("\n=== KEYWORD HITS ===")
    for k in keys:
        n = full.count(k)
        if n:
            # context snippets
            idxs = [m.start() for m in re.finditer(re.escape(k), full)][:3]
            snips = []
            for idx in idxs:
                a, b = max(0, idx - 20), min(len(full), idx + 40)
                snips.append(full[a:b].replace("\n", " "))
            print(f"  {k!r}: {n} | {snips}")

    # Blue-looking filled body: HY + large pt
    print("\n=== HY / LARGE BODY RUNS (possible filled values) ===")
    hy = [
        r
        for r in runs
        if r["text"].strip()
        and r["font"]
        and ("HY" in r["font"] or "헤드라인" in r["font"])
    ]
    by_font = Counter(f"{r['font']} {r['size']}pt {r['color']}" for r in hy)
    for k, n in by_font.most_common(15):
        print(f"  {k}: {n}")

    print("\n=== SAMPLE BODY LINES starting with - ===")
    for i, item in enumerate(content):
        if "Paragraph" not in item:
            continue
        texts = []
        styles = []
        for run in item["Paragraph"].get("content", []):
            if "Text" not in run:
                continue
            t = run["Text"]
            tx = t.get("text") or ""
            if tx:
                texts.append(tx)
                s = t.get("style") or {}
                styles.append(
                    f"{s.get('font_name')} {s.get('font_size')}pt {s.get('color')}"
                )
        text = "".join(texts).strip()
        if text.startswith("-") or text.startswith("–") or text.startswith("—"):
            print(f"P{i}: {text[:100]}")
            print(f"     {styles[:3]}")

    # Dates / signature-ish
    print("\n=== DATE-LIKE ===")
    for m in re.finditer(r"20\d{2}\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]?\s*\d{0,2}", full):
        a, b = max(0, m.start() - 15), min(len(full), m.end() + 25)
        print(f"  {full[a:b]!r}")

    print("\n=== NAME-LIKE near 성명/대표 ===")
    for m in re.finditer(r".{0,10}(성명|대표자|대표)[^\n]{0,40}", full):
        print(f"  {m.group(0)!r}")


if __name__ == "__main__":
    main()
