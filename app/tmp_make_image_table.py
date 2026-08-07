# -*- coding: utf-8 -*-
"""Create HWPX with all10 images in A4 table (2 per row + title row)"""
import zipfile, os, struct

IMG_DIR = r'C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\02. 밸류업파트너스\2026 토슈즈공통\2. 사업계획서\2. 참고자료\2. 사용'
OUT = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)\루살카_참고이미지모음.hwpx'

# Image list: (filename, title)
images = [
    ('01_루살카_사업개요_인포그래픽.png', '루살카 사업개요 인포그래픽'),
    ('02_발레토슈즈_발봉쇄_위험_700PSI.png', '발레토슈즈 발봉쇄 위험 (700PSI)'),
    ('03_토슈즈_충격비교_스포츠순위.png', '토슈즈 충격비교 - 스포츠 순위'),
    ('04_토슈즈_연간소모품비_1000만원.png', '토슈즈 연간 소모품비 (1,000만원)'),
    ('05_발레전공생_연간유지비용_1500만원.png', '발레전공생 연간 유지비용 (1,500만원)'),
    ('06_발질병_문제점_종합.png', '발 질병 문제점 종합'),
    ('07_토슈즈_비용과다_영수증.png', '토슈즈 비용 과다 영수증'),
    ('08_루살카_사업로드맵.png', '루살카 사업 로드맵'),
    ('09_토슈즈_시장분석_151억.png', '토슈즈 시장분석 (151억원)'),
    ('10_AI_3D데이터_활용.png', 'AI·3D 데이터 활용'),
]

# Load images
img_data = {}
for fname, _ in images:
    path = os.path.join(IMG_DIR, fname)
    with open(path, 'rb') as f:
        img_data[fname] = f.read()

# A4 dimensions in HWPUNIT (1mm =28.3465 HWPUNIT)
PAGE_W = 59528  # A4 width
PAGE_H = 84188  # A4 height
MARGIN_L = 5669  # left margin ~20mm
MARGIN_R = 5669
MARGIN_T = 4252  # top ~15mm
MARGIN_B = 4252
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R  # ~48190
CELL_W = (CONTENT_W - 300) // 2  # 2 cells with small gap
IMG_H = 20000  # image height ~70mm
TITLE_H = 2000  # title row height ~7mm
ROW_GAP = 200

# Generate image IDs
bin_items = []
for i, (fname, _) in enumerate(images):
    bin_name = f'img{i:03d}'
    bin_items.append((bin_name, fname))

# Build manifest entries
manifest_items = []
for bin_name, fname in bin_items:
    ext = fname.rsplit('.', 1)[1].lower()
    mime = 'image/png' if ext == 'png' else 'image/jpeg'
    manifest_items.append(f'  <opf:item id="{bin_name}" href="BinData/{fname}" media-type="{mime}" />')

# Build body paragraphs
body_paragraphs = []

# Title paragraph
body_paragraphs.append(f'''<hp:p hp:paraPrIDRef="0" hp:styleIDRef="0">
  <hp:run hp:charPrIDRef="0">
    <hp:t>\ub8e8\uc0b4\uce74 \ucc38\uace0 \uc774\ubbf8\uc9c0 \ubaa8\uc74c</hp:t>
  </hp:run>
</hp:p>''')

# Build table with image pairs
def make_cell_img(bin_name, fname, w, h):
    return f'''<hp:tc hp:colSpan="1" hp:rowSpan="1" hp:width="{w}" hp:height="{h}">
  <hp:cellAddr hp:x="0" hp:y="0"/>
  <hp:cellSz hp:width="{w}" hp:height="{h}"/>
  <hp:cellSpacing hp:left="50" hp:right="50" hp:top="50" hp:bottom="50"/>
  <hp:cellMargin hp:left="100" hp:right="100" hp:top="100" hp:bottom="100"/>
  <hp:tcPr>
    <hp:cellBorderFill hp:fillRefID="0"/>
  </hp:tcPr>
  <hp:subList hp:listFlags="0" hp:isArray="true">
    <hp:p hp:paraPrIDRef="0" hp:styleIDRef="0">
      <hp:run hp:charPrIDRef="0">
        <hp:pic hp:instID="{bin_name}" hp:zOrder="0">
          <hp:sz hp:width="{w-200}" hp:height="{h-200}" hp:widthRelTo="ABSOLUTE" hp:heightRelTo="ABSOLUTE"/>
          <hp:pos hp:treatAsChar="0" hp:textWrap="SQUARE" hp:vertRelTo="PARA" hp:horzRelTo="COLUMN" hp:vertOffset="0" hp:horzOffset="0"/>
          <hp:imgRect hp:left="0" hp:top="0" hp:right="{w-200}" hp:bottom="{h-200}"/>
          <hp:imgClip hp:left="0" hp:top="0" hp:right="0" hp:bottom="0"/>
        </hp:pic>
      </hp:run>
    </hp:p>
  </hp:subList>
</hp:tc>'''

def make_cell_title(title, w, h):
    return f'''<hp:tc hp:colSpan="1" hp:rowSpan="1" hp:width="{w}" hp:height="{h}">
  <hp:cellAddr hp:x="0" hp:y="0"/>
  <hp:cellSz hp:width="{w}" hp:height="{h}"/>
  <hp:cellSpacing hp:left="50" hp:right="50" hp:top="50" hp:bottom="50"/>
  <hp:cellMargin hp:left="100" hp:right="100" hp:top="50" hp:bottom="50"/>
  <hp:tcPr>
    <hp:cellBorderFill hp:fillRefID="0"/>
  </hp:tcPr>
  <hp:subList hp:listFlags="0" hp:isArray="true">
    <hp:p hp:paraPrIDRef="0" hp:styleIDRef="0">
      <hp:run hp:charPrIDRef="0">
        <hp:t>{title}</hp:t>
      </hp:run>
    </hp:p>
  </hp:subList>
</hp:tc>'''

rows_xml = []
for pair_idx in range(5):
    i1 = pair_idx * 2
    i2 = i1 + 1
    bin1, fname1 = bin_items[i1]
    _, title1 = images[i1]
    bin2, fname2 = bin_items[i2]
    _, title2 = images[i2]
    
    # Image row
    row_img = f'''<hp:tr>
  {make_cell_img(bin1, fname1, CELL_W, IMG_H)}
  {make_cell_img(bin2, fname2, CELL_W, IMG_H)}
</hp:tr>'''
    
    # Title row
    row_title = f'''<hp:tr>
  {make_cell_title(title1, CELL_W, TITLE_H)}
  {make_cell_title(title2, CELL_W, TITLE_H)}
</hp:tr>'''
    
    rows_xml.append(row_img)
    rows_xml.append(row_title)

table_xml = f'''<hp:p hp:paraPrIDRef="0" hp:styleIDRef="0">
  <hp:tbl hp:tblStyleIDRef="0" hp:zOrder="0" hp:width="{CONTENT_W}">
    <hp:tblPr>
      <hp:cellSpacing hp:val="0"/>
    </hp:tblPr>
    {"".join(rows_xml)}
  </hp:tbl>
</hp:p>'''

body_xml = '\n'.join(body_paragraphs) + '\n' + table_xml

# Build section0.xml
section0 = f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<hp:sec hp:id="0" hp:width="{PAGE_W}" hp:height="{PAGE_H}" hp:marginLeft="{MARGIN_L}" hp:marginRight="{MARGIN_R}" hp:marginTop="{MARGIN_T}" hp:marginBottom="{MARGIN_B}" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/main">
{body_xml}
</hp:sec>'''

# Build header.xml
header = f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<hp:doc xmlns:hp="http://www.hancom.co.kr/hwpml/2011/main">
  <hp:secPr hp:id="0">
    <hp:paper hp:width="{PAGE_W}" hp:height="{PAGE_H}" hp:marginLeft="{MARGIN_L}" hp:marginRight="{MARGIN_R}" hp:marginTop="{MARGIN_T}" hp:marginBottom="{MARGIN_B}"/>
  </hp:secPr>
  <hp:charPrList hp:count="1">
    <hp:charPr hp:id="0" hp:height="1000" hp:textColor="000000" hp:shadeColor="000000" hp:shade="0"/>
  </hp:charPrList>
  <hp:paraPrList hp:count="1">
    <hp:paraPr hp:id="0" hp:align="LEFT" hp:lineSpacing="160"/>
  </hp:paraPrList>
</hp:doc>'''

# content.hpf
content_hpf = f'''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<opf:package xmlns:opf="http://www.idpf.org/2007/opf" version="2.0">
  <opf:metadata>
    <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">\ub8e8\uc0b4\uce74 \ucc38\uace0 \uc774\ubbf8\uc9c0 \ubaa8\uc74c</dc:title>
  </opf:metadata>
  <opf:manifest>
    <opf:item id="section0" href="section0.xml" media-type="text/xml" />
    {chr(10).join(manifest_items)}
  </opf:manifest>
</opf:package>'''

# manifest.xml
manifest_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/hwpml"/>
</manifest:manifest>'''

# container.xml
container_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container">
  <ocf:rootfiles>
    <ocf:rootfile full-path="Contents/content.hpf" media-type="application/hwpml"/>
  </ocf:rootfiles>
</ocf:container>'''

# container.rdf
container_rdf = '''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="">
    <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">\ub8e8\uc0b4\uce74 \ucc38\uace0 \uc774\ubbf8\uc9c0 \ubaa8\uc74c</dc:title>
  </rdf:Description>
</rdf:RDF>'''

# Write HWPX
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('mimetype', 'application/hwpml')
    z.writestr('Contents/header.xml', header)
    z.writestr('Contents/section0.xml', section0)
    z.writestr('Contents/content.hpf', content_hpf)
    z.writestr('META-INF/container.xml', container_xml)
    z.writestr('META-INF/container.rdf', container_rdf)
    z.writestr('META-INF/manifest.xml', manifest_xml)
    for bin_name, fname in bin_items:
        z.writestr(f'BinData/{fname}', img_data[fname])

print(f'[OK] Created: {OUT}')
print(f'Images: {len(images)}')
print(f'Rows: {len(images)//2} pairs (image+title)')
