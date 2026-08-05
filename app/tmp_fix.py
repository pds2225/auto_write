import zipfile, shutil

hwpx = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\18_달구벌여성창업플랫폼\2.붙임.신청서식2026년_박다솜_마켓게이트_v2.hwpx'
backup = hwpx.replace('.hwpx', '_backup2.hwpx')
shutil.copy2(hwpx, backup)

with zipfile.ZipFile(hwpx) as z:
    with z.open('Contents/section0.xml') as f:
        content = f.read().decode('utf-8')

changes = [
    ('14종·115,000건', '14종·110,000건+'),
    ('14종·115,000건+', '14종·110,000건+'),
    ('115,000건 이상', '110,000건+'),
    ('115,000건 이상의', '110,000건+의'),
    ('14종 115,000건', '14종 110,000건+'),
    ('115,000건', '110,000건+'),
]

total = 0
for old, new in changes:
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        print(f'"{old}" -> "{new}": {count}건')
        total += count

with zipfile.ZipFile(hwpx, 'w', zipfile.ZIP_DEFLATED) as zout:
    with zipfile.ZipFile(backup) as zin:
        for item in zin.infolist():
            if item.filename == 'Contents/section0.xml':
                zout.writestr(item, content.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

print(f'총 {total}건 수정 완료')
