# -*- coding: utf-8 -*-
import sys, zipfile
sys.path.insert(0, 'app')
from lxml import etree
from auto_write.services.hwpx_fill import _local, _cell_text, _cell_colspan, _cell_rowspan

p = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)\붙임 2. 제품 양산 패키지 신청서.hwpx'
with zipfile.ZipFile(p) as z:
    xml = z.read('Contents/section0.xml')
root = etree.fromstring(xml)

def local(tag):
    return _local(tag)

tables = [el for el in root.iter() if local(el.tag) == 'tbl']
out = []
for ti, tbl in enumerate(tables):
    out.append(f'\n########## TABLE {ti} ##########')
    trs = [el for el in tbl.iter() if local(el.tag) == 'tr']
    for ri, tr in enumerate(trs):
        tcs = [el for el in tr if local(el.tag) == 'tc']
        for tc in tcs:
            addr_el = None
            for child in tc.iter():
                if local(child.tag) == 'cellAddr':
                    addr_el = child
                    break
            addr = (addr_el.get('colAddr') + ',' + addr_el.get('rowAddr')) if addr_el is not None else '?'
            txt = _cell_text(tc)[:100]
            out.append(f'  R{ri} (col,row={addr}) cspan={_cell_colspan(tc)} rspan={_cell_rowspan(tc)}: {txt!r}')

with open('tmp_pdf_pages/hwpx_grid.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('DONE', len(tables), 'tables')
