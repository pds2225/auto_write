# -*- coding: utf-8 -*-
"""Map bizplan section paragraphs with charPr details (precise start)."""
import zipfile, sys
from lxml import etree

sys.stdout.reconfigure(encoding='utf-8')

HWPX = r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx'

with zipfile.ZipFile(HWPX) as z:
    hdr = etree.fromstring(z.read('Contents/header.xml'))
    sec = etree.fromstring(z.read('Contents/section0.xml'))

cpr = {}
for cp in hdr.xpath('.//*[local-name()="charPr"]'):
    cid = cp.get('id')
    font_ref = None
    for child in cp:
        if etree.QName(child).localname == 'fontRef':
            font_ref = child.get('hangul')
    cpr[cid] = {'h': cp.get('height'), 'c': cp.get('textColor'), 'f': font_ref}

fonts = {}
for ff in hdr.xpath('.//*[local-name()="fontface"]'):
    if ff.get('lang') == 'HANGUL':
        for i, f in enumerate(ff):
            fonts[str(i)] = f.get('face')

def describe(cid):
    info = cpr.get(cid, {})
    fname = fonts.get(str(info.get('f')), '?')
    return f"id={cid} {fname} {info.get('h')} {info.get('c')}"

# Find ALL children containing exact bizplan title
for i, child in enumerate(sec):
    texts = [t.text or '' for t in child.xpath('.//*[local-name()="t"]')]
    text = ''.join(texts).strip().replace('\n', ' ')
    if '사업계획서' in text:
        print(f'FOUND bizplan mention [{i}]: {text[:100]!r}')

print('---')
# Start at child that equals the title table text exactly-ish
start_i = None
for i, child in enumerate(sec):
    texts = [t.text or '' for t in child.xpath('.//*[local-name()="t"]')]
    text = ''.join(texts).strip().replace('\n', ' ')
    if text == '2026 예술분야 예비창업 프로그램 사업계획서' or text.startswith('2026 예술분야 예비창업 프로그램 사업계획서'):
        start_i = i
        break

print('start_i', start_i)
if start_i is None:
    sys.exit(1)

for i in range(start_i, min(start_i + 45, len(sec))):
    child = sec[i]
    texts = [t.text or '' for t in child.xpath('.//*[local-name()="t"]')]
    text = ''.join(texts).strip().replace('\n', ' ')
    if '서식 1' in text or '개인정보 수집' in text:
        print(f'=== END at [{i}] ===')
        break
    tag = etree.QName(child).localname
    runs = [c for c in child if etree.QName(c).localname == 'run']
    role = ''
    if text.startswith(('1-1.', '1-2.', '2.', '3-1.', '3-2.', '4-1.')):
        role = 'HEADLINE'
    elif text.startswith('ㅇ'):
        role = 'SUBTITLE'
    elif text.startswith(('(가설', '(대상자', '(지원금', '(성공')):
        role = 'BODY20'
    print(f'[{i}] {role:8} | {text[:90]!r}')
    for r in runs[:4]:
        cid = r.get('charPrIDRef')
        ts = ''.join(t.text or '' for t in r.xpath('.//*[local-name()="t"]')).replace('\n', ' ')[:50]
        has_tbl = any(etree.QName(x).localname == 'tbl' for x in r)
        if ts or has_tbl:
            print(f'         {describe(cid)} | tbl={has_tbl} | {ts!r}')
