# -*- coding: utf-8 -*-
"""Dump charPr templates and remaining bizplan paras."""
import zipfile, sys, copy
from lxml import etree

sys.stdout.reconfigure(encoding='utf-8')
HWPX = r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx'

with zipfile.ZipFile(HWPX) as z:
    hdr = etree.fromstring(z.read('Contents/header.xml'))
    sec = etree.fromstring(z.read('Contents/section0.xml'))

# max id
ids = [int(cp.get('id')) for cp in hdr.xpath('.//*[local-name()="charPr"]')]
print('max charPr id', max(ids), 'count', len(ids))

for want in ('10', '12', '22', '93', '9', '97'):
    cps = hdr.xpath(f'.//*[local-name()="charPr" and @id="{want}"]')
    if not cps:
        print(f'charPr {want} MISSING')
        continue
    print(f'\n=== charPr {want} ===')
    print(etree.tostring(cps[0], encoding='unicode')[:800])

# remaining after 62
print('\n--- after 62 ---')
for i in range(62, 80):
    if i >= len(sec):
        break
    child = sec[i]
    texts = [t.text or '' for t in child.xpath('.//*[local-name()="t"]')]
    text = ''.join(texts).strip().replace('\n', ' ')
    if '서식 1' in text or (text.startswith('직급') and '성명' in text):
        print(f'[{i}] END-ish {text[:60]!r}')
        break
    role = ''
    if text.startswith(('1-1.', '1-2.', '2.', '3-1.', '3-2.', '4-1.')):
        role = 'HEADLINE'
    elif text.startswith('ㅇ'):
        role = 'SUBTITLE'
    elif text.startswith(('(가설', '(대상자', '(지원금', '(성공')):
        role = 'BODY20'
    print(f'[{i}] {role:8} | {text[:90]!r}')
