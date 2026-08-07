"""Final fix v4: guide text + content + lineseg"""
import zipfile, os, re, glob
import xml.etree.ElementTree as ET

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
v4 = glob.glob(os.path.join(base, '*v4*.hwpx'))[0]

z3 = zipfile.ZipFile(v3)
c3 = z3.read('Contents/section0.xml').decode('utf-8')
z4 = zipfile.ZipFile(v4)
files = {n: z4.read(n) for n in z4.namelist()}
c4 = files['Contents/section0.xml'].decode('utf-8')

# L012: Remove guide text with ※ prefix
c4 = re.sub(r'\u203b\s*\uc81c\ucd9c\s*\uc2dc\s*\ud30c\ub780\uc0c9\s*\ub0b4\uc6a9\s*\ubb38\uad6c\uc640\s*\uc791\uc131\s*\uc608\uc2dc\ub294\s*\uc0ad\uc81c', '', c4)
c4 = re.sub(r'\uc81c\ucd9c\s*\uc2dc\s*\ud30c\ub780\uc0c9\s*\ub0b4\uc6a9\s*\ubb38\uad6c\uc640\s*\uc791\uc131\s*\uc608\uc2dc\ub294\s*\uc0ad\uc81c', '', c4)

# Content: replace plan section from v3
p1 = c3.find('[1')
p2 = c3.find('\ub2e4.', p1) + 2 if p1 >= 0 else -1
if p1 >= 0 and p2 > p1:
    old_p = c3[p1:p2]
    new_p = '[1\uac1c\uc6d4\ucc3c, 9\uc6d4] 3\ucc28 \ud544\ub4dc\ud14c\uc2a4\ud2b8(\uc120\ud654\uc608\uace0\u00b7H\ubc1c\ub808\ud559\uc6d0) \uacb0\uacfc\uc640 \ub204\uc801 340\ucef4\ub808 \uc2dc\uc81c\ud488 \ub370\uc774\ud130\ub97c \ubc18\uc601\ud574 \ud1a0\ubc31\uc2a4 \ud615\uc0c1(\uac01\ub3c4\u00b7\uae4a\uc774)\uacfc \uc0c5\ud06c \uac15\ub3c4\ub97c \ucd5c\uc885 CAD \uc124\uacc4\ub85c \ud655\uc815. \ud55c\uad6d\uc778 \ud45c\uc900 \uc871\ud615 DB(\ubc1c\ubc88\ub108\ube44\u00b7\uc544\uce58\ub192\uc774 \ubd84\ud3ec)\ub97c \uc124\uacc4 \ud30c\ub770\ubbf8\ud130\uc5d0 \ubc18\uc601. [2\uac1c\uc6d4\ucc3c, 10\uc6d4] \ud655\uc815 \uc124\uacc4 \uae30\uc900 \ud1a0\ubc31\uc2a4 \uc0ac\ucd9c\uc6a9 \uc815\ubc00 \uae08\ud615 1\uc2dd \uc81c\uc791 \ud6c4 1\ucc28 \uc2dc\ud5d8\uc0ac\ucd9c. \uc2dc\ud5d8\uc0ac\ucd9c\ud488\uc740 \ud544\ub4dc\ud14c\uc2a4\ud2b8 \ucc38\uac00\uc790(\uc120\ud654\uc608\uace0 \uc804\uacf5\uc0dd)\uc5d0\uac8c \ucc29\ud654 \ud3c9\uac00\ub97c \uc758\ub8b0\ud574 \ud53d\ud305 \uc815\ud655\ub3c4\ub97c \uac80\uc99d. [3\uac1c\uc6d4\ucc3c, 11\uc6d4] \uae08\ud615 \ubbf8\uc138\uc870\uc815(\uc0c5\ud06c \uac15\ub3c4\u00b7\ud1a0\ubc31\uc2a4 \uac01\ub3c4 \ubcf4\uc815), \ubca0\ud2b8\ub0a8 \ud638\uce58\ubbfc \uc81c\uc870\uacf5\uc7a5\uc5d0\uc11c 50\ucef4\ub808 \uc2dc\ud5d8\uc591\uc0b0 \ud6c4 \ud488\uc9c8\uac80\uc99d(\ub0b4\uad6c\uc131\u00b7\ucc29\ud654\uac10\u00b7\uc218\uba85). \uacb0\uacfc\ubcf4\uace0\uc11c \uc791\uc131\u00b7\uc81c\ucd9c. \ubcd1\ud589\ud558\uc5ec \ub17c\ud604\ub3d9 \ubcfc\uc1fc\uc774 \ubc1c\ub808\ud559\uc6d0(50\uc778)\u00b7\uc120\ud654\uc608\uc220\uace0 \ub300\uc0c1 B2B \uad6c\ub9e4\uc758\ud5a5\uc11c\ub97c \ud655\ubcf4\ud558\uace0, \ud611\uc57d \uc885\ub8cc \uc2dc\uc810\uae4c\uc9c0 \uc0ac\uc5c5\uc790\ub4f1\ub85d\uc744 \uc644\ub8cc\ud574 \uc0ac\uc5c5\uc790\ub4f1\ub85d\uc99d\uc744 \uc9c0\uc6d0\uae30\uad00\uc5d0 \uc81c\ucd9c\ud55c\ub2e4.'
    c4 = c4.replace(old_p, new_p)
    print(f'Plan: replaced {len(old_p)}->{len(new_p)}')

# Content: replace future section from v3
f1 = c3.find('\ud611\uc57d \uc885\ub8cc \ud6c4')
f2 = c3.find('\uc788\ub2e4.', f1) + 3 if f1 >= 0 else -1
if f1 >= 0 and f2 > f1:
    old_f = c3[f1:f2]
    new_f = '\ud611\uc57d \uc885\ub8cc \ud6c4 \ud655\ubcf4\ud55c \uae08\ud615\uc73c\ub85c \ubca0\ud2b8\ub0a8 \ud638\uce58\ubbfc \uc81c\uc870\uacf5\uc7a5\uc744 \ud1b5\ud55c \uc815\uc2dd \uc591\uc0b0\u00b7\ucd9c\uc2dc\ub97c \uc2dc\uc791\ud55c\ub2e4. \ud310\ub9e4\ub294 \uc628\ub77c\uc778(\uc2a4\ub9c8\ud2b8\uc2a4\ud1a0\uc5b4, 3D \uc2a4\uce94 \ud6c4 \ub514\uc9c0\ud138 \uc871\ud615 \ud504\ub85c\ud544 \uc800\uc7a5\u2192\uc6d0\ud074\ub9ad \uc7ac\uc8fc\ubb38)\uacfc \ubc1c\ub808\ud559\uc6d0\u00b7\uc608\uc220\uae30\uad00 B2B \uc81c\ud734\ub97c \ubcd1\ud589\ud55c\ub2e4. \ub9e4\ucd9c \ubaa9\ud45c\ub294 2026\ub144 \ud558\ubc18\uae30 \uc57d 2,200\ub9cc \uc6d0(\ucd08\ub3c4 \uc591\uc0b0 300\ucef4\ub808), 2027\ub144 \uc57d 1\uc745 7,000\ub9cc \uc6d0(\uc6d4 200\ucef4\ub808 \ud655\ub300), 2028\ub144 \uc57d 5\uc745 \uc6d0(\ud574\uc678 \ud3ec\ud568)\uc774\ub2e4. \uae30\ub300\ud6a8\uacfc\ub294 \u2460 \ud55c\uad6d\uc778 \ubc1c\ud615\uc5d0 \ucd5c\uc801\ud654\ub41c \uad6d\uc0b0 \ud1a0\uc218\uc988 \ube0c\ub79c\ub4dc \uc815\ub9bd(\uc218\uc785 \uc758\uc874 \ud0c8\ud53c) \u2461 \ubb34\uc6a9\uc218 \uc871\ubd80 \ubd80\uc0c1\u00b7\ud1b5\uc99d \uac10\uc18c(\uc871\ubd80 \ubd80\uc0c1 58% \uc6d0\uc778\uc778 ill-fitting \ud1a0\uc218\uc988 \ubb38\uc81c \ud574\uacb0) \u2462 \uc804\uacf5\uc0dd\u00b7\ucde8\ubbf8 \ubc1c\ub808\uce35 \uc18c\ubaa8\ud488 \uad6c\ub9e4\ube44\uc6a9 \uc808\uac10(\uc218\uc785 \ub300\ube44 \uc57d 33% \uc800\ub834) \u2463 3D \uc871\ud615 \ub370\uc774\ud130\ubca0\uc774\uc2a4 \ucd95\uc801\uc744 \ud1b5\ud55c \ud6c4\uc18d \ub9de\ucda4\uc81c\ud488(\ud1a0\ud32c\ub4dc\u00b7\uc6dc\ubc0d\uc218\uc988 \ub4f1) \ub77c\uc778 \ud655\uc7a5\uc774\ub2e4.'
    c4 = c4.replace(old_f, new_f)
    print(f'Future: replaced {len(old_f)}->{len(new_f)}')

# L002/L074: linesegarray
NS = 'http://www.hancom.co.kr/hwpml/2011/main'
ET.register_namespace('hp', NS)
tree = ET.fromstring(c4)
rm = 0
def rls(p):
    global rm
    tr = [c for c in p if c.tag == '{%s}linesegarray' % NS]
    for c in p:
        rls(c)
    for c in tr:
        p.remove(c)
        rm += 1
rls(tree)
c4 = ET.tostring(tree, encoding='unicode', xml_declaration=True)
files['Contents/section0.xml'] = c4.encode('utf-8')

if os.path.exists(v4):
    os.remove(v4)
with zipfile.ZipFile(v4, 'w', zipfile.ZIP_DEFLATED) as z:
    for n, d in files.items():
        z.writestr(n, d)

# Verify
zf = zipfile.ZipFile(v4)
cf = zf.read('Contents/section0.xml').decode('utf-8')
hf = zf.read('Contents/header.xml').decode('utf-8')
tf = ET.fromstring(cf)

print(f'\nlineseg removed: {rm}')
print(f'L012 guide: {cf.count(chr(0x791)+chr(0x131)+" "+chr(0x608)+chr(0x2dc))}')
print(f'L013 ClickHere: {cf.count("Clickhere")}')
print(f'Content 3차: {cf.count(chr(0x3)+chr(0xcc28))}')
print(f'Content ill-fitting: {cf.count("ill-fitting")}')
print(f'Content 초도: {cf.count(chr(0xcd08)+chr(0xb3c4))}')
