import zipfile, re, xml.etree.ElementTree as ET, sys

hwpx = sys.argv[1]
with zipfile.ZipFile(hwpx) as z:
    with z.open('Contents/section0.xml') as f:
        content = f.read().decode('utf-8')

ns = {
    'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
}

root = ET.fromstring(content)
paras = root.findall('.//hp:p', ns)

# 1. Required markers
markers = {'붙임1': False, '붙임2': False, '붙임3': False, '붙임4': False, '증빙서류1': False}
for p in paras:
    text = ''.join(t.text or '' for t in p.findall('.//hp:t', ns))
    for key in markers:
        if key in text:
            markers[key] = True

print('=== 필수 서류 마커 ===')
for k, v in markers.items():
    status = 'OK' if v else 'MISSING'
    print(f'  {k}: {status}')

# 2. Key data
data_checks = {
    '박다솜': False,
    '010-2930-6666': False,
    '1992': False,
    '마포구': False,
    '마켓게이트': False,
    '2026년 8월 4일': False,
}
for p in paras:
    text = ''.join(t.text or '' for t in p.findall('.//hp:t', ns))
    for key in data_checks:
        if key in text:
            data_checks[key] = True

print('\n=== 핵심 데이터 ===')
for k, v in data_checks.items():
    status = 'OK' if v else 'MISSING'
    print(f'  {k}: {status}')

# 3. Placeholder check
placeholders = ['[확인필요]', '010-0000', 'OOO', '2000.00.00']
found_ph = []
for p in paras:
    text = ''.join(t.text or '' for t in p.findall('.//hp:t', ns))
    for ph in placeholders:
        if ph in text:
            found_ph.append(ph)

print(f'\n=== 플레이스홀더 잔존: {len(found_ph)}건 ===')
for ph in found_ph:
    print(f'  {ph}')

# 4. Images, tables, paragraphs
images = root.findall('.//hp:pic', ns)
tables = root.findall('.//hp:tbl', ns)
print(f'\n=== 구조 ===')
print(f'  이미지(서명 등): {len(images)}개')
print(f'  표: {len(tables)}개')
print(f'  전체 문단: {len(paras)}개')
