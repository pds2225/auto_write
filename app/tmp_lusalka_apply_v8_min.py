# -*- coding: utf-8 -*-
"""L154 min sample: 1-1 body parenthesis labels #0000FF → #2E74B5 (L155).

Does NOT touch: 1-1 headline, ㅇ form prompts (L070), anything from 1-2 onward.
Source v6.hwp is never overwritten.
"""
from __future__ import annotations

import copy
import shutil
import sys
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, r"D:\auto_write\app")
from auto_write.services.hwpx_charpr_guard import assert_charpr_append_only
from auto_write.services.hwp_docx_convert import _SAVE_FORMATS, _convert_via_com

BASE = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
)
SRC_HWP = BASE / (
    "붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
)
WORK_HWPX = Path(r"D:\auto_write\app\tmp_lusalka_v8_min_work.hwpx")
OUT_HWP = BASE / (
    "붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v8_min.hwp"
)

ACCENT = "#2E74B5"
TARGET_SNIPPETS = (
    "(해당 분야 전문가인 대표자가 직접 경험한 문제)",
    "(통계로 확인한 문제의 보편성과 시급성)",
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def para_text(p) -> str:
    return "".join(t.text or "" for t in p.xpath('.//*[local-name()="t"]'))


def main() -> None:
    if not SRC_HWP.exists():
        raise SystemExit(f"missing source: {SRC_HWP}")

    if WORK_HWPX.exists():
        WORK_HWPX.unlink()
    if OUT_HWP.exists():
        OUT_HWP.unlink()

    print("COM HWP→HWPX...", SRC_HWP.name)
    _convert_via_com(SRC_HWP, WORK_HWPX, _SAVE_FORMATS[".hwpx"])
    print("work", WORK_HWPX.exists(), WORK_HWPX.stat().st_size)

    with zipfile.ZipFile(WORK_HWPX, "r") as zin:
        files = {n: zin.read(n) for n in zin.namelist()}

    hdr = etree.fromstring(files["Contents/header.xml"])
    sec = etree.fromstring(files["Contents/section0.xml"])

    char_props = None
    for el in hdr.iter():
        if _local(el.tag) == "charProperties":
            char_props = el
            break
    if char_props is None:
        raise SystemExit("charProperties not found")

    # Map id → charPr; find blue 20pt candidates (height 2000 = 20pt in HWPX units/10)
    by_id = {}
    max_id = -1
    for el in char_props:
        if _local(el.tag) != "charPr":
            continue
        cid = int(el.get("id"))
        by_id[cid] = el
        max_id = max(max_id, cid)

    # Locate section range: after 1-1. headline, before 1-2.
    idx_11 = idx_12 = None
    for i, child in enumerate(sec):
        if _local(child.tag) != "p":
            continue
        t = para_text(child).strip()
        if t.startswith("1-1."):
            idx_11 = i
        if t.startswith("1-2."):
            idx_12 = i
            break
    if idx_11 is None or idx_12 is None:
        raise SystemExit(f"anchors missing: 1-1={idx_11} 1-2={idx_12}")
    print(f"range: after [{idx_11}] until before [{idx_12}]")

    # Collect runs to retarget: text contains target snippets AND current color #0000FF
    changes = []
    source_cp_ids = set()
    for i in range(idx_11 + 1, idx_12):
        p = sec[i]
        if _local(p.tag) != "p":
            continue
        full = para_text(p).strip()
        # skip form chrome prompts starting with ㅇ
        if full.startswith("ㅇ"):
            print(f"SKIP chrome [{i}]: {full[:40]}")
            continue
        for run in p:
            if _local(run.tag) != "run":
                continue
            texts = "".join(t.text or "" for t in run.xpath('.//*[local-name()="t"]'))
            if not any(s in texts for s in TARGET_SNIPPETS):
                continue
            cid = run.get("charPrIDRef")
            cp = by_id.get(int(cid)) if cid is not None else None
            color = (cp.get("textColor") if cp is not None else "") or ""
            height = cp.get("height") if cp is not None else "?"
            if color.upper() != "#0000FF":
                print(f"SKIP non-#0000FF [{i}] charPr={cid} color={color} | {texts[:50]!r}")
                continue
            changes.append((i, run, cid, texts.strip()[:80], height))
            source_cp_ids.add(int(cid))

    if not changes:
        raise SystemExit("no target blue label runs found in 1-1 body")
    if len(source_cp_ids) != 1:
        print("WARN multiple source charPr ids:", source_cp_ids)

    src_id = next(iter(source_cp_ids))
    new_id = max_id + 1
    cp_new = copy.deepcopy(by_id[src_id])
    cp_new.set("id", str(new_id))
    cp_new.set("textColor", ACCENT)
    char_props.append(cp_new)
    char_props.set("itemCnt", str(int(char_props.get("itemCnt", "0")) + 1))
    assert_charpr_append_only(hdr)
    print(f"append charPr {src_id} → {new_id} textColor {ACCENT}")

    for i, run, old_cid, preview, height in changes:
        run.set("charPrIDRef", str(new_id))
        print(f"RETARGET [{i}] charPr {old_cid}→{new_id} height={height} | {preview!r}")

    # Sanity: 1-1 headline and ㅇ prompts unchanged color-wise (still their original refs)
    h_runs = []
    for run in sec[idx_11]:
        if _local(run.tag) == "run" and "".join(
            t.text or "" for t in run.xpath('.//*[local-name()="t"]')
        ).strip():
            h_runs.append(run.get("charPrIDRef"))
    print(f"SANITY headline [{idx_11}] charPr refs={h_runs} (unchanged)")

    files["Contents/header.xml"] = etree.tostring(
        hdr, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    files["Contents/section0.xml"] = etree.tostring(
        sec, xml_declaration=True, encoding="UTF-8", standalone=True
    )

    with zipfile.ZipFile(WORK_HWPX, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in files.items():
            zout.writestr(name, data)

    print("COM HWPX→HWP...", OUT_HWP.name)
    _convert_via_com(WORK_HWPX, OUT_HWP, _SAVE_FORMATS[".hwp"])
    print("OUT", OUT_HWP.exists(), OUT_HWP.stat().st_size if OUT_HWP.exists() else 0)


if __name__ == "__main__":
    main()
