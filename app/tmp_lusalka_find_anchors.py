# -*- coding: utf-8 -*-
"""Find bizplan paragraphs by text anchors in HWPX."""
import zipfile, sys
from lxml import etree

sys.stdout.reconfigure(encoding='utf-8')

HWPX = r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx'
HP = 'http://www.hancom.co.kr/hwpml/2011/main'
HS = 'http://www.hancom.co.kr/hwpml/2011/section'

with zipfile.ZipFile(HWPX) as z:
    sec = z.read('Contents/section0.xml')

sroot = etree.fromstring(sec)
print('root', sroot.tag, 'nchild', len(sroot))

# Dump raw structure of child 15
child = sroot[15]
print('child15 tag', child.tag)
print(etree.tostring(child, encoding='unicode')[:2000])

print('\n--- search anchors ---')
anchors = ['1-1. 창업 동기', 'ㅇ 보유 역량', '(가설을 확인할', '※ 10p 이내로', '4-1.']
# walk all hp:p
paras = sroot.xpath('.//*[local-name()="p"]')
print('total p count', len(paras))
for i, p in enumerate(paras):
    texts = [t.text or '' for t in p.xpath('.//*[local-name()="t"]')]
    text = ''.join(texts)
    if any(a in text for a in anchors) or (i >= 0 and False):
        runs = p.xpath('.//*[local-name()="run"]')
        # only direct? get first-level runs under p
        direct_runs = [c for c in p if etree.QName(c).localname == 'run']
        cprs = [r.get('charPrIDRef') for r in direct_runs[:5]]
        print(f'para#{i} direct_runs={len(direct_runs)} all_runs={len(runs)} cpr={cprs} | {text[:100]}')

print('\n--- section children 13-20 raw tags/text ---')
for i in range(13, 22):
    c = sroot[i]
    texts = [t.text or '' for t in c.xpath('.//*[local-name()="t"]')]
    text = ''.join(texts).strip()[:80]
    print(f'[{i}] {etree.QName(c).localname} text={text!r}')
    # show first run attribs
    for r in c.xpath('.//*[local-name()="run"]')[:3]:
        print(f'    run attribs={dict(r.attrib)} children={[etree.QName(x).localname for x in r][:5]}')
