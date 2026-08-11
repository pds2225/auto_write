# -*- coding: utf-8 -*-
import zipfile
from lxml import etree

z = zipfile.ZipFile(r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx')
h = etree.fromstring(z.read('Contents/header.xml'))

# find refList / charProperties itemCnt
for el in h.xpath('.//*'):
    ln = etree.QName(el).localname
    if 'char' in ln.lower() or ln in ('refList', 'head'):
        if el.get('itemCnt') or ln in ('charProperties', 'refList'):
            print(ln, dict(el.attrib))

print('---')
for want in ('9', '10', '12', '22', '93'):
    cp = h.xpath(f'.//*[local-name()="charPr" and @id="{want}"]')[0]
    print(want, dict(cp.attrib))
    for c in cp:
        print(' ', etree.QName(c).localname, dict(c.attrib))
