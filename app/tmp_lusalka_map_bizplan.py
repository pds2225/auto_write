# -*- coding: utf-8 -*-
"""Map bizplan section paragraphs with charPr details."""
import zipfile, sys
from lxml import etree

sys.stdout.reconfigure(encoding='utf-8')

HWPX = r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx'
HH = 'http://www.hancom.co.kr/hwpml/2011/head'

with zipfile.ZipFile(HWPX) as z:
    hdr = etree.fromstring(z.read('Contents/header.xml'))
    sec = etree.fromstring(z.read('Contents/section0.xml'))

# charPr lookup
cpr = {}
for cp in hdr.xpath('.//*[local-name()="charPr"]'):
    cid = cp.get('id')
    font_ref = None
    for child in cp:
        if etree.QName(child).localname == 'fontRef':
            font_ref = child.get('hangul')
    cpr[cid] = {
        'h': cp.get('height'),
        'c': cp.get('textColor'),
        'f': font_ref,
    }

# font name for hangul
fonts = {}
for ff in hdr.xpath('.//*[local-name()="fontface"]'):
    if ff.get('lang') == 'HANGUL':
        for f in ff:
            fonts[f.get('id') or str(list(ff).index(f))] = f.get('face')
# also by index if no id
for ff in hdr.xpath('.//*[local-name()="fontface"]'):
    if ff.get('lang') == 'HANGUL':
        for i, f in enumerate(ff):
            fonts[str(i)] = f.get('face')

def describe(cid):
    info = cpr.get(cid, {})
    fname = fonts.get(str(info.get('f')), '?')
    return f"id={cid} {fname} {info.get('h')} {info.get('c')}"

# Find start: 사업계획서 title
started = False
for i, child in enumerate(sec):
    texts = [t.text or '' for t in child.xpath('.//*[local-name()="t"]')]
    text = ''.join(texts).strip().replace('\n', ' ')
    if '사업계획서' in text and '프로그램' in text:
        started = True
        print(f'=== START at [{i}] ===')
    if not started:
        continue
    if '개인정보' in text or '서식 1' in text:
        print(f'=== END at [{i}] ===')
        break
    tag = etree.QName(child).localname
    runs = [c for c in child if etree.QName(c).localname == 'run']
    # if paragraph has nested table, skip deep - still show
    cprs = []
    for r in runs:
        cid = r.get('charPrIDRef')
        # only if run has text
        ts = ''.join(t.text or '' for t in r.xpath('.//*[local-name()="t"]'))
        if ts.strip() or True:
            cprs.append((cid, ts[:40].replace('\n',' ')))
    role = ''
    if text.startswith('1-') or text.startswith('2.') or text.startswith('3-') or text.startswith('4-'):
        role = 'HEADLINE'
    elif text.startswith('ㅇ'):
        role = 'SUBTITLE'
    elif text.startswith('(') and '가설' in text or text.startswith('(대상자') or text.startswith('(지원금') or text.startswith('(성공'):
        role = 'BODY20'
    print(f'[{i}] {tag} {role:8} runs={len(runs)}')
    for cid, ts in cprs[:4]:
        print(f'       {describe(cid)} | {ts!r}')
    if text and len(cprs) == 0:
        print(f'       TEXT={text[:80]!r}')
