# -*- coding: utf-8 -*-
"""Deeper L-rule probes: company blanks, checkboxes, bold labels, blank-form chrome."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

DIR = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
)
FILLED = DIR / "붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
BLANK = DIR / "붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식(0).hwp"


def full_text(path: Path) -> str:
    data = json.loads(unhwp.parse(str(path)).json)
    parts = []

    def walk(o):
        if isinstance(o, dict):
            if "Text" in o and isinstance(o["Text"], dict):
                parts.append(o["Text"].get("text") or "")
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for sec in data.get("sections", []):
        walk(sec)
    return "".join(parts)


def para_dump(path: Path, pred):
    data = json.loads(unhwp.parse(str(path)).json)
    content = data["sections"][0]["content"]
    out = []
    for i, item in enumerate(content):
        if "Paragraph" not in item:
            continue
        texts, styles = [], []
        for run in item["Paragraph"].get("content", []):
            if "Text" not in run:
                continue
            t = run["Text"]
            tx = t.get("text") or ""
            if not tx:
                continue
            texts.append(tx)
            s = t.get("style") or {}
            styles.append(
                {
                    "font": s.get("font_name"),
                    "size": s.get("font_size"),
                    "color": s.get("color"),
                    "bold": s.get("bold"),
                    "text": tx[:60],
                }
            )
        text = "".join(texts).strip()
        if pred(text):
            out.append((i, text, styles))
    return out


def main() -> None:
    ft = full_text(FILLED)
    print("=== APPLICATION TYPE / CHECKS ===")
    for pat in [
        r"신청형태.{0,40}",
        r"예비창업자.{0,20}",
        r"개인 및 법인사업자.{0,20}",
        r"신청대상.{0,80}",
        r"전공 분야.{0,60}",
        r"성별.{0,40}",
        r"연령대.{0,50}",
    ]:
        m = re.search(pat, ft)
        if m:
            print(f"  {m.group(0)!r}")

    print("\n=== III. 기업 정보 WINDOW ===")
    m = re.search(r"Ⅲ\. 기업 정보.{0,350}", ft)
    if m:
        print(m.group(0))
    else:
        m = re.search(r"기업 정보.{0,350}", ft)
        print(m.group(0) if m else "NOT FOUND")

    print("\n=== 매출/투자 WINDOW ===")
    for pat in [r"매출액.{0,120}", r"투자유치이력.{0,120}", r"기업명.{0,80}"]:
        m = re.search(pat, ft)
        if m:
            print(f"  {m.group(0)!r}")

    print("\n=== L080 BOLD on blue paren labels (sample) ===")
    for i, text, styles in para_dump(FILLED, lambda t: t.startswith("- ("))[:5]:
        print(f"P{i}: {text[:90]}")
        for s in styles[:3]:
            print(f"  bold={s['bold']} {s['font']} {s['size']} {s['color']} | {s['text']!r}")

    print("\n=== CHROME COMPARE blank(0) vs v6 (1-1 / first ㅇ) ===")
    for label, pred in [
        ("1-1", lambda t: t.startswith("1-1.")),
        ("ㅇ보유", lambda t: t.startswith("ㅇ") and "보유 역량" in t),
        ("1-2", lambda t: t.startswith("1-2.")),
    ]:
        b = para_dump(BLANK, pred)
        f = para_dump(FILLED, pred)
        print(f"-- {label} --")
        if b:
            print(f"  blank P{b[0][0]} styles: {[(s['font'], s['size'], s['color']) for s in b[0][2][:2]]}")
        else:
            print("  blank: MISSING")
        if f:
            print(f"  filled P{f[0][0]} styles: {[(s['font'], s['size'], s['color']) for s in f[0][2][:2]]}")
        else:
            print("  filled: MISSING")

    print("\n=== GUIDANCE / 작성요령 remnants ===")
    for k in ["작성요령", "작성방법", "삭제 후", "파란색", "예시입니다", "확인필요", "작성 필요", "OOO", "○○○"]:
        print(f"  {k}: {ft.count(k)}")

    print("\n=== SIGNATURE BLOCKS ===")
    for m in re.finditer(r".{0,30}(인).{0,40}", ft):
        s = m.group(0)
        if "서명" in s or "대표" in s or "기업" in s or "(인)" in s:
            print(f"  {s!r}")

    print("\n=== IMAGE / PIC presence (json keys) ===")
    raw = unhwp.parse(str(FILLED)).json
    print("  'Picture' in json:", "Picture" in raw or '"Picture"' in raw)
    print("  'Image' in json:", "Image" in raw or '"Image"' in raw)
    # count Pic-like
    for key in ["Picture", "Image", "GShapeObject", "Ole"]:
        print(f"  count {key}: {raw.count(key)}")


if __name__ == "__main__":
    main()
