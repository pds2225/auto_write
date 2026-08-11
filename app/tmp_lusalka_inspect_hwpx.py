# -*- coding: utf-8 -*-
"""Inspect HWPX paragraph indices and charPr for bizplan section."""
import zipfile, sys, re
from lxml import etree

sys.stdout.reconfigure(encoding='utf-8')

HWPX = r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx'
NS = {
    'hp': 'http://www.hancom.co.kr/hwpml/2011/main',
    'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
}

with zipfile.ZipFile(HWPX) as z:
    hdr = z.read('Contents/header.xml')
    sec = z.read('Contents/section0.xml')

hroot = etree.fromstring(hdr)
# list fonts
print('=== FONTFACES ===')
for ff in hroot.xpath('.//hh:fontface', namespaces=NS):
    lang = ff.get('lang') or ff.get('{http://www.w3.org/XML/1998/namespace}lang') or '?'
    print(f' fontface lang={lang} count={ff.get("count")}')
    for i, f in enumerate(ff):
        print(f'  [{i}] {f.get("face")} id={f.get("id")}')

print('\n=== CHARPR (sample / HY / blue / 14pt+) ===')
for cp in hroot.xpath('.//hh:charPr', namespaces=NS):
    cid = cp.get('id')
    height = cp.get('height')
    color = cp.get('textColor')
    fonts = []
    for child in cp:
        tag = etree.QName(child).localname
        if tag in ('fontRef', 'font'):
            fonts.append(f'{tag}:{dict(child.attrib)}')
    # show interesting ones
    h = int(height or 0)
    interesting = (
        '0000FF' in (color or '').upper()
        or h >= 1400
        or any('헤드' in str(f) or 'HY' in str(f) for f in fonts)
    )
    if interesting or cid in ('0','1','2'):
        print(f' charPr id={cid} height={height} color={color} {fonts[:4]}')

# Top-level paragraphs in section (same order as unhwp content items?)
sroot = etree.fromstring(sec)
# Get all direct children of section that are p or tbl
children = list(sroot)
print(f'\n=== SECTION children: {len(children)} ===')
# Actually section may wrap differently
print('root tag', sroot.tag)
# find all top-level hp:p and hp:tbl under section body
body_items = []
for el in sroot.iter():
    pass

# Better: get section's content sequence
# In HWPX, section0.xml root is hp:sec, children are hp:p / hp:tbl / hp:ctrl etc.
for i, child in enumerate(sroot):
    tag = etree.QName(child).localname
    if tag == 'p':
        texts = [t.text or '' for t in child.xpath('.//hp:t', namespaces=NS)]
        text = ''.join(texts).strip().replace('\n', ' ')
        # first run charPr
        runs = child.xpath('./hp:run', namespaces=NS)
        cprs = []
        for r in runs[:4]:
            cprs.append(r.get('charPrIDRef') or r.get('charPrID') or '?')
        if 14 <= i <= 50:
            print(f'[{i}] p charPr={cprs} | {text[:90]}')
    elif tag == 'tbl':
        if 14 <= i <= 50:
            print(f'[{i}] tbl')
    else:
        if 14 <= i <= 50:
            print(f'[{i}] {tag}')
