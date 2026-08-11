# -*- coding: utf-8 -*-
"""Apply min style slice: 1-1 headline + 2 subtitles only → v7_min.hwp"""
from __future__ import annotations

import copy
import shutil
import sys
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, r'D:\auto_write\app')
from auto_write.services.hwpx_charpr_guard import assert_charpr_append_only
from auto_write.services.hwp_docx_convert import _SAVE_FORMATS, _convert_via_com

SRC_HWPX = Path(r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx')
WORK_HWPX = Path(r'D:\auto_write\app\tmp_lusalka_v7_min_work.hwpx')
OUT_DIR = Path(
    r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625'
    r'\25_2026 예술분야 예비창업 프로그램 참여자 모집'
)
OUT_HWP = OUT_DIR / (
    '붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v7_min.hwp'
)

# HWPX section child indices for 1-1 only
IDX_HEADLINE = 21   # 1-1. 창업 동기
IDX_SUB1 = 22       # ㅇ 보유 역량...
IDX_SUB2 = 24       # ㅇ 해결하고자 하는...
# leave [27]=1-2 untouched

HH = 'http://www.hancom.co.kr/hwpml/2011/head'


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def main() -> None:
    if not SRC_HWPX.exists():
        raise SystemExit(f'missing work hwpx: {SRC_HWPX}')
    if OUT_HWP.exists():
        OUT_HWP.unlink()
    shutil.copy2(SRC_HWPX, WORK_HWPX)

    with zipfile.ZipFile(WORK_HWPX, 'r') as zin:
        files = {n: zin.read(n) for n in zin.namelist()}

    hdr = etree.fromstring(files['Contents/header.xml'])
    sec = etree.fromstring(files['Contents/section0.xml'])

    # Find charProperties parent
    char_props = None
    for el in hdr.iter():
        if _local(el.tag) == 'charProperties':
            char_props = el
            break
    if char_props is None:
        raise SystemExit('charProperties not found')

    def find_cp(cid: str):
        for el in char_props:
            if _local(el.tag) == 'charPr' and el.get('id') == cid:
                return el
        raise KeyError(cid)

    # Clone: 10 → 107 (맑은고딕 14pt black, keep bold for subtitle)
    # Clone: 12 → 108 (맑은고딕 14pt blue for headline)
    cp_black = copy.deepcopy(find_cp('10'))
    cp_black.set('id', '107')
    cp_black.set('height', '1400')

    cp_blue = copy.deepcopy(find_cp('12'))
    cp_blue.set('id', '108')
    cp_blue.set('height', '1400')
    cp_blue.set('textColor', '#0000FF')

    char_props.append(cp_black)
    char_props.append(cp_blue)
    char_props.set('itemCnt', str(int(char_props.get('itemCnt', '0')) + 2))

    assert_charpr_append_only(hdr)

    def para_text(p) -> str:
        return ''.join(t.text or '' for t in p.xpath('.//*[local-name()="t"]')).strip()

    def set_text_runs(p, new_id: str) -> int:
        """Retarget runs that contain text (skip empty control runs)."""
        n = 0
        for run in p:
            if _local(run.tag) != 'run':
                continue
            texts = ''.join(t.text or '' for t in run.xpath('.//*[local-name()="t"]'))
            if not texts.strip():
                continue
            run.set('charPrIDRef', new_id)
            n += 1
        return n

    targets = [
        (IDX_HEADLINE, '108', '1-1. 창업 동기', 'HEADLINE'),
        (IDX_SUB1, '107', 'ㅇ 보유 역량', 'SUBTITLE'),
        (IDX_SUB2, '107', 'ㅇ 해결하고자', 'SUBTITLE'),
    ]
    for idx, cid, expect, role in targets:
        p = sec[idx]
        text = para_text(p)
        if expect not in text:
            raise SystemExit(f'[{idx}] expected {expect!r} got {text[:60]!r}')
        n = set_text_runs(p, cid)
        print(f'OK [{idx}] {role} → charPr {cid} runs={n} | {text[:50]}')

    # Sanity: 1-2 still charPr 93
    p12 = sec[27]
    t12 = para_text(p12)
    if '1-2.' not in t12:
        raise SystemExit(f'[27] expected 1-2 got {t12!r}')
    for run in p12:
        if _local(run.tag) != 'run':
            continue
        texts = ''.join(t.text or '' for t in run.xpath('.//*[local-name()="t"]'))
        if texts.strip() and run.get('charPrIDRef') != '93':
            raise SystemExit(f'1-2 charPr changed unexpectedly: {run.get("charPrIDRef")}')
    print(f'OK [27] 1-2 unchanged charPr 93 | {t12}')

    files['Contents/header.xml'] = etree.tostring(
        hdr, xml_declaration=True, encoding='UTF-8', standalone=True
    )
    files['Contents/section0.xml'] = etree.tostring(
        sec, xml_declaration=True, encoding='UTF-8', standalone=True
    )

    with zipfile.ZipFile(WORK_HWPX, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name, data in files.items():
            zout.writestr(name, data)
    print(f'wrote {WORK_HWPX}')

    print('COM convert →', OUT_HWP.name)
    _convert_via_com(WORK_HWPX, OUT_HWP, _SAVE_FORMATS['.hwp'])
    print('OUT', OUT_HWP.exists(), OUT_HWP.stat().st_size if OUT_HWP.exists() else 0)


if __name__ == '__main__':
    main()
