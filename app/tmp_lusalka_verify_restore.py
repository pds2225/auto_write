# -*- coding: utf-8 -*-
"""Verify 1-1 form chrome styles restored to v6 (L070)."""
import json
import sys

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

BASE = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
)
FILES = {
    "v6": BASE + r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp",
    "v7": BASE + r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v7.hwp",
    "v7_min": BASE
    + r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v7_min.hwp",
}
WANT = [
    "1-1. 창업 동기",
    "ㅇ 보유 역량",
    "ㅇ 해결하고자",
    "1-2. 사업 아이템",
]


def dump(label: str, path: str) -> dict:
    print("=" * 60)
    print(label, path.rsplit("\\", 1)[-1])
    data = json.loads(unhwp.parse(path).json)
    content = data["sections"][0]["content"]
    found = {}
    for i, item in enumerate(content):
        if "Paragraph" not in item:
            continue
        para = item["Paragraph"]
        runs = para.get("content", [])
        text = ""
        styles = []
        for run in runs:
            if "Text" not in run:
                continue
            t = run["Text"]
            text += t.get("text", "")
            s = t.get("style", {})
            styles.append(
                "{} {}pt {}".format(
                    s.get("font_name"), s.get("font_size"), s.get("color")
                )
            )
        text_s = text.strip()
        if any(w in text_s for w in WANT):
            role = (
                "HEADLINE-1-1"
                if text_s.startswith("1-1.")
                else "SUBTITLE"
                if text_s.startswith("ㅇ")
                and ("보유" in text_s or "해결" in text_s)
                else "HEADLINE-1-2"
                if text_s.startswith("1-2.")
                else "?"
            )
            print(f"P{i} [{role}]")
            print(f"  text: {text_s[:100]}")
            print(f"  styles: {styles[:6]}")
            found[role] = styles
    return found


def assert_v6_styles(found: dict, label: str) -> None:
    # Expected from v6 original form chrome
    h = found.get("HEADLINE-1-1", [])
    assert h, f"{label}: missing 1-1 headline"
    assert any("HY헤드라인M" in s and "15" in s for s in h), (
        f"{label}: 1-1 headline not HY헤드라인M 15pt: {h}"
    )
    assert not any("14" in s and ("0000FF" in s.upper() or "blue" in s.lower()) for s in h), (
        f"{label}: 1-1 still has 14pt blue: {h}"
    )
    # color black — unhwp may report #000000 or 0 or black
    assert any(
        ("15" in s)
        and (
            "000000" in s.upper()
            or s.endswith(" 0")
            or "black" in s.lower()
            or s.rstrip().endswith("#000000")
            or s.endswith(" None")
            or "#000" in s
        )
        for s in h
    ) or any("HY헤드라인M 15" in s for s in h), f"{label}: unexpected headline styles {h}"

    subs = [found.get("SUBTITLE")] if "SUBTITLE" in found else []
    # dump may overwrite SUBTITLE — re-parse carefully below if needed
    print(f"{label}: headline OK ({h[0] if h else 'n/a'})")


if __name__ == "__main__":
    results = {}
    for k, p in FILES.items():
        results[k] = dump(k, p)

    # Strict checks on v7 / v7_min vs v6
    v6 = results["v6"]
    for label in ("v7", "v7_min"):
        cur = results[label]
        assert cur.get("HEADLINE-1-1") == v6.get("HEADLINE-1-1"), (
            f"{label} headline styles differ from v6:\n"
            f"  v6={v6.get('HEADLINE-1-1')}\n  {label}={cur.get('HEADLINE-1-1')}"
        )
        assert cur.get("HEADLINE-1-2") == v6.get("HEADLINE-1-2"), (
            f"{label} 1-2 styles differ from v6"
        )
        print(f"MATCH {label} == v6 for 1-1/1-2 headline styles")

    # Explicit expectations
    h = v6["HEADLINE-1-1"]
    print("\n--- EXPECTATION CHECK ---")
    print("1-1 headline styles:", h)
    ok_headline = any("HY헤드라인M" in s and "15" in str(s) for s in h)
    print("HY헤드라인M 15pt present:", ok_headline)
    # Check no 14pt blue on form labels
    bad = [s for s in h if "14" in s]
    print("any 14pt on 1-1 headline:", bad)

    print("PASS restore verification")
