import zipfile, shutil, copy
import xml.etree.ElementTree as ET

v2_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\18_달구벌여성창업플랫폼\2.붙임.신청서식2026년_박다솜_마켓게이트_v2.hwpx'
v21_path = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\18_달구벌여성창업플랫폼\2.붙임.신청서식2026년_박다솜_마켓게이트_v2.1.hwpx'
backup_path = v21_path.replace('.hwpx', '_backup.hwpx')
shutil.copy2(v21_path, backup_path)

ns = 'http://www.hancom.co.kr/hwpml/2011/paragraph'

# Read v2
with zipfile.ZipFile(v2_path) as z:
    v2_content = z.read('Contents/section0.xml').decode('utf-8')
v2_root = ET.fromstring(v2_content)
v2_paras = v2_root.findall('{%s}p' % ns)

# First page = paras 0-6 (header + 참가신청서 page, before 사업계획서)
first_page_paras = []
for i in range(7):
    first_page_paras.append(copy.deepcopy(v2_paras[i]))
    text = ''.join(v2_paras[i].itertext()).strip()[:80]
    print(f'  Copying para {i}: {text}')

print(f'Collected {len(first_page_paras)} paragraphs from v2 first page')

# Read v2.1 from backup
with zipfile.ZipFile(backup_path) as z:
    v21_content = z.read('Contents/section0.xml').decode('utf-8')
v21_root = ET.fromstring(v21_content)

# Insert at the beginning
for idx in range(len(first_page_paras) - 1, -1, -1):
    v21_root.insert(0, first_page_paras[idx])

# Write to v2.1
new_content = ET.tostring(v21_root, encoding='unicode')
with zipfile.ZipFile(v21_path, 'w', zipfile.ZIP_DEFLATED) as zout:
    with zipfile.ZipFile(backup_path) as zin:
        for item in zin.infolist():
            if item.filename == 'Contents/section0.xml':
                zout.writestr(item, new_content.encode('utf-8'))
            else:
                zout.writestr(item, zin.read(item.filename))

# Verify
with zipfile.ZipFile(v21_path) as z:
    verify = z.read('Contents/section0.xml').decode('utf-8')
verify_root = ET.fromstring(verify)
verify_paras = verify_root.findall('{%s}p' % ns)
first_text = ''.join(verify_paras[0].itertext()).strip()[:100]
second_text = ''.join(verify_paras[1].itertext()).strip()[:100]
print(f'Done! Total paras: {len(verify_paras)}')
print(f'Para 0: {first_text}')
print(f'Para 1: {second_text}')
