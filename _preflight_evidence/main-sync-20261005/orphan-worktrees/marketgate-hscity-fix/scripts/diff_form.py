# -*- coding: utf-8 -*-
"""원본 양식 ↔ 작성본 전수 대조 — '값만 채웠는가'를 증거로 판정한다.

비교 축 3가지:
  1) 텍스트(hp:t) 순서열 diff — 어떤 문구가 사라졌/바뀌었나
  2) 구조 카운트 — 표/행/셀/문단/체크박스 개수가 같은가
  3) 서식(charPrIDRef) 변경 — 어느 run 의 서식을 건드렸나
"""
import sys
import zipfile
from difflib import SequenceMatcher

from lxml import etree

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS = {"hp": HP, "hh": HH}

SRC = sys.argv[1]
DST = sys.argv[2]


def load(path):
    with zipfile.ZipFile(path) as z:
        sec = etree.fromstring(z.read("Contents/section0.xml"))
        hdr = etree.fromstring(z.read("Contents/header.xml"))
    return sec, hdr


def texts(sec):
    return [(t.text or "") for t in sec.findall(".//hp:t", NS)]


def counts(sec):
    return {
        "표": len(sec.findall(".//hp:tbl", NS)),
        "행": len(sec.findall(".//hp:tr", NS)),
        "칸": len(sec.findall(".//hp:tc", NS)),
        "문단": len(sec.findall(".//hp:p", NS)),
        "run": len(sec.findall(".//hp:run", NS)),
        "체크박스": len(sec.findall(".//hp:checkBtn", NS)),
        "이미지": len(sec.findall(".//hp:pic", NS)),
    }


def charpr_seq(sec):
    return [r.get("charPrIDRef") for r in sec.findall(".//hp:run", NS)]


a_sec, a_hdr = load(SRC)
b_sec, b_hdr = load(DST)

print("=== 1. 구조 카운트 ===")
ca, cb = counts(a_sec), counts(b_sec)
for k in ca:
    mark = "OK" if ca[k] == cb[k] else "!! 변경"
    print(f"  {k:5s} 원본 {ca[k]:4d} → 작성본 {cb[k]:4d}   {mark}")

print("\n=== 2. 텍스트 diff (양식 문구가 바뀐 곳) ===")
ta, tb = texts(a_sec), texts(b_sec)
sm = SequenceMatcher(None, ta, tb, autojunk=False)
n_fill, n_edit, n_drop, n_add = 0, 0, 0, 0
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        continue
    old = [x for x in ta[i1:i2]]
    new = [x for x in tb[j1:j2]]
    for k in range(max(len(old), len(new))):
        o = old[k] if k < len(old) else "<없음>"
        n = new[k] if k < len(new) else "<없음>"
        if o.strip() == "" and n.strip():
            kind = "값채움 "
            n_fill += 1
        elif o.strip() and n.strip() == "":
            kind = "삭제!! "
            n_drop += 1
        elif o.strip() and n.strip() and o.strip() != n.strip():
            kind = "변경!! "
            n_edit += 1
        else:
            continue
        print(f"  [{kind}] {o.strip()[:48]!r:52s} → {n.strip()[:48]!r}")

print(f"\n  요약: 값채움 {n_fill} / 양식문구 변경 {n_edit} / 양식문구 삭제 {n_drop}")

print("\n=== 3. 서식(charPrIDRef) 변경 ===")
sa, sb = charpr_seq(a_sec), charpr_seq(b_sec)
color_a = {cp.get("id"): (cp.get("textColor") or "#000000").upper()
           for cp in a_hdr.findall(".//hh:charPr", NS)}
color_b = {cp.get("id"): (cp.get("textColor") or "#000000").upper()
           for cp in b_hdr.findall(".//hh:charPr", NS)}
if len(sa) != len(sb):
    print(f"  run 개수가 달라 위치 대조 불가 ({len(sa)} vs {len(sb)})")
else:
    runs_a = a_sec.findall(".//hp:run", NS)
    runs_b = b_sec.findall(".//hp:run", NS)
    changed = 0
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            txt = "".join(t.text or "" for t in runs_b[i].findall("hp:t", NS)).strip()
            old_txt = "".join(t.text or "" for t in runs_a[i].findall("hp:t", NS)).strip()
            print(f"  charPr {x}({color_a.get(x)}) → {y}({color_b.get(y)})  "
                  f"원문 {old_txt[:30]!r} / 현재 {txt[:30]!r}")
            changed += 1
    print(f"  서식 변경 run: {changed}")

print("\n=== 4. header.xml(서식 정의) 자체 변경 ===")
print(f"  charPr 개수 원본 {len(color_a)} → 작성본 {len(color_b)}   "
      f"{'OK(정의 무변경)' if len(color_a) == len(color_b) else '!! 변경'}")
same = all(color_a.get(k) == color_b.get(k) for k in color_a)
print(f"  기존 charPr 색 정의 동일: {'OK' if same else '!! 변경'}")
