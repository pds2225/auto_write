# -*- coding: utf-8 -*-
import zipfile, os, re, glob, shutil
import xml.etree.ElementTree as ET

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
v5 = os.path.join(base, os.path.basename(v3).replace('_v3', '_v5'))

z3 = zipfile.ZipFile(v3)
files = {n: z3.read(n) for n in z3.namelist()}
c = files['Contents/section0.xml'].decode('utf-8')

# L012: Remove guide text (raw)
guide = '\uc791\uc131 \uc608\uc2dc\ub294 \uc0ad\uc81c'
while guide in c:
    c = c.replace(guide, '')
# Remove leftover prefix fragments
for frag in ['\uc81c\ucd9c \uc2dc \ud30c\ub780\uc0c9 \ub0b4\uc6a9 \ubb38\uad6c\uc640 ', '\u203b ']:
    c = c.replace(frag, '')

# L013: ClickHere
c = re.sub(r'Clickhere:set:\d+:Direction:wstring:\d+: ?', '', c)
c = re.sub(r'HelpState:wstring:\d+: ?', '', c)
for ph in ['\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694.', '\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694']:
    c = c.replace(ph, '')

# Content: plan
a1 = '[1\uac1c\uc6d4\ucc3c,'
e1 = '\uc9c0\uc6d0\uae30\uad00\uc5d0 \uc81c\ucd9c\ud55c\ub2e4.'
i1 = c.find(a1)
if i1 >= 0:
    ie1 = c.find(e1, i1) + len(e1)
    old = c[i1:ie1]
    # Build replacement with Korean chars
    new_parts = [
        '[1\uac1c\uc6d4\ucc3c, 9\uc6d4] 3\ucc28 \ud544\ub4dc\ud14c\uc2a4\ud2b8(',
        '\uc120\ud654\uc608\uace0, H\ubc1c\ub808\ud559\uc6d0) \uacb0\uacfc\uc640 \ub204\uc801 340\ucef4\ub808 \uc2dc\uc81c\ud488 ',
        '\ub370\uc774\ud130\ub97c \ubc18\uc601\ud574 \ud1a0\ubc31\uc2a4 \ud615\uc0c1(\uac01\ub3c4, \uae4a\uc774)\uacfc ',
        '\uc0c5\ud06c \uac15\ub3c4\ub97c \ucd5c\uc885 CAD \uc124\uacc4\ub85c \ud655\uc815. ',
        '\ud55c\uad6d\uc778 \ud45c\uc900 \uc871\ud615 DB(\ubc1c\ubc88\ub108\ube44, \uc544\uce58\ub192\uc774 \ubd84\ud3ec)\ub97c \uc124\uacc4 \ud30c\ub770\ubbf8\ud130\uc5d0 \ubc18\uc601. ',
        '[2\uac1c\uc6d4\ucc3c, 10\uc6d4] \ud655\uc815 \uc124\uacc4 \uae30\uc900 \ud1a0\ubc31\uc2a4 \uc0ac\ucd9c\uc6a9 \uc815\ubc00 \uae08\ud615 1\uc2dd \uc81c\uc791 \ud6c4 1\ucc28 \uc2dc\ud5d8\uc0ac\ucd9c. ',
        '\uc2dc\ud5d8\uc0ac\ucd9c\ud488\uc740 \ud544\ub4dc\ud14c\uc2a4\ud2b8 \ucc38\uac00\uc790(\uc120\ud654\uc608\uace0 \uc804\uacf5\uc0dd)\uc5d0\uac8c ',
        '\ucc29\ud654 \ud3c9\uac00\ub97c \uc758\ub8b0\ud574 \ud53d\ud305 \uc815\ud655\ub3c4\ub97c \uac80\uc99d. ',
        '[3\uac1c\uc6d4\ucc3c, 11\uc6d4] \uae08\ud615 \ubbf8\uc138\uc870\uc815(\uc0c5\ud06c \uac15\ub3c4, \ud1a0\ubc31\uc2a4 \uac01\ub3c4 \ubcf4\uc815), ',
        '\ubca0\ud2b8\ub0a8 \ud638\uce58\ubbfc \uc81c\uc870\uacf5\uc7a5\uc5d0\uc11c 50\ucef4\ub808 \uc2dc\ud5d8\uc591\uc0b0 \ud6c4 ',
        '\ud488\uc9c8\uac80\uc99d(\ub0b4\uad6c\uc131, \ucc29\ud654\uac10, \uc218\uba85). \uacb0\uacfc\ubcf4\uace0\uc11c \uc791\uc131, \uc81c\ucd9c. ',
        '\ubcd1\ud589\ud558\uc5ec \ub17c\ud604\ub3d9 \ubcfc\uc1fc\uc774 \ubc1c\ub808\ud559\uc6d0(50\uc778), ',
        '\uc120\ud654\uc608\uc220\uace0 \ub300\uc0c1 B2B \uad6c\ub9e4\uc758\ud5a5\uc11c\ub97c \ud655\ubcf4\ud558\uace0, ',
        '\ud611\uc57d \uc885\ub8cc \uc2dc\uc810\uae4c\uc9c0 \uc0ac\uc5c5\uc790\ub4f1\ub85d\uc744 \uc644\ub8cc\ud574 ',
        '\uc0ac\uc5c5\uc790\ub4f1\ub85d\uc99d\uc744 \uc9c0\uc6d0\uae30\uad00\uc5d0 \uc81c\ucd9c\ud55c\ub2e4.'
    ]
    new = ''.join(new_parts)
    c = c.replace(old, new)
    print(f'Plan: {len(old)}->{len(new)}')

# Content: future
a2 = '\ud611\uc57d \uc885\ub8cc \ud6c4'
e2 = '\uc788\ub2e4.'
i2 = c.find(a2)
if i2 >= 0:
    ie2 = c.find(e2, i2) + len(e2)
    old2 = c[i2:ie2]
    new2_parts = [
        '\ud611\uc57d \uc885\ub8cc \ud6c4 \ud655\ubcf4\ud55c \uae08\ud615\uc73c\ub85c \ubca0\ud2b8\ub0a8 \ud638\uce58\ubbfc \uc81c\uc870\uacf5\uc7a5\uc744 \ud1b5\ud55c \uc815\uc2dd \uc591\uc0b0, \ucd9c\uc2dc\ub97c \uc2dc\uc791\ud55c\ub2e4. ',
        '\ud310\ub9e4\ub294 \uc628\ub77c\uc778(\uc2a4\ub9c8\ud2b8\uc2a4\ud1a0\uc5b4, 3D \uc2a4\uce94 \ud6c4 \ub514\uc9c0\ud138 \uc871\ud615 \ud504\ub85c\ud544 \uc800\uc7a5, \uc6d0\ud074\ub9ad \uc7ac\uc8fc\ubb38)\uacfc ',
        '\ubc1c\ub808\ud559\uc6d0, \uc608\uc220\uae30\uad00 B2B \uc81c\ud734\ub97c \ubcd1\ud589\ud55c\ub2e4. ',
        '\ub9e4\ucd9c \ubaa9\ud45c\ub294 2026\ub144 \ud558\ubc18\uae30 \uc57d 2,200\ub9cc \uc6d0(\ucd08\ub3c4 \uc591\uc0b0 300\ucef4\ub808), ',
        '2027\ub144 \uc57d 1\uc745 7,000\ub9cc \uc6d0(\uc6d4 200\ucef4\ub808 \ud655\ub300), 2028\ub144 \uc57d 5\uc745 \uc6d0(\ud574\uc678 \ud3ec\ud568)\uc774\ub2e4. ',
        '\uae30\ub300\ud6a8\uacfc\ub294 ',
        '\u2460 \ud55c\uad6d\uc778 \ubc1c\ud615\uc5d0 \ucd5c\uc801\ud654\ub41c \uad6d\uc0b0 \ud1a0\uc218\uc988 \ube0c\ub79c\ub4dc \uc815\ub9bd(\uc218\uc785 \uc758\uc874 \ud0c8\ud53c), ',
        '\u2461 \ubb34\uc6a9\uc218 \uc871\ubd80 \ubd80\uc0c1, \ud1b5\uc99d \uac10\uc18c(\uc871\ubd80 \ubd80\uc0c1 58% \uc6d0\uc778\uc778 ill-fitting \ud1a0\uc218\uc988 \ubb38\uc81c \ud574\uacb0), ',
        '\u2462 \uc804\uacf5\uc0dd, \ucde8\ubbf8 \ubc1c\ub808\uce35 \uc18c\ubaa8\ud488 \uad6c\ub9e4\ube44\uc6a9 \uc808\uac10(\uc218\uc785 \ub300\ube44 \uc57d 33% \uc800\ub834), ',
        '\u2463 3D \uc871\ud615 \ub370\uc774\ud130\ubca0\uc774\uc2a4 \ucd95\uc801\uc744 \ud1b5\ud55c \ud6c4\uc18d \ub9de\ucda4\uc81c\ud488(\ud1a0\ud32c\ub4dc, \uc6dc\ubc0d\uc218\uc988 \ub4f1) \ub77c\uc778 \ud655\uc7a5\uc774\ub2e4.'
    ]
    new2 = ''.join(new2_parts)
    c = c.replace(old2, new2)
    print(f'Future: {len(old2)}->{len(new2)}')

# L002: linesegarray
NS = 'http://www.hancom.co.kr/hwpml/2011/main'
ET.register_namespace('hp', NS)
tree = ET.fromstring(c)
rm = 0
def rls(p):
    global rm
    tr = [ch for ch in p if ch.tag == '{%s}linesegarray' % NS]
    for ch in list(p):
        rls(ch)
    for ch in tr:
        p.remove(ch)
        rm += 1
rls(tree)
c = ET.tostring(tree, encoding='unicode', xml_declaration=True)
files['Contents/section0.xml'] = c.encode('utf-8')

with zipfile.ZipFile(v5, 'w', zipfile.ZIP_DEFLATED) as z:
    for n, d in files.items():
        z.writestr(n, d)
print(f'v5: {v5}')
print(f'lineseg removed: {rm}')

# Verify
z5 = zipfile.ZipFile(v5)
c5 = z5.read('Contents/section0.xml').decode('utf-8')
# Use actual Korean for checks
checks = [
    ('L012 guide', c5.count('\uc791\uc131 \uc608\uc2dc\ub294 \uc0ad\uc81c'), 0),
    ('L013 ClickHere', c5.count('Clickhere'), 0),
    ('L013 HelpState', c5.count('HelpState'), 0),
    ('L013 placeholder', c5.count('\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4'), 0),
    ('Plan 3\ucc28', c5.count('3\ucc28'), '>0'),
    ('Future ill-fitting', c5.count('ill-fitting'), 1),
    ('L070 \ubd84\ub7c9', c5.count('\ubd84\ub7c9:'), '>0'),
]
all_ok = True
for name, val, exp in checks:
    if exp == 0:
        ok = val == 0
    elif isinstance(exp, str) and exp[0] == '>':
        ok = val > int(exp[1:])
    else:
        ok = val == exp
    if not ok:
        all_ok = False
    print(f'  [{"OK" if ok else "FAIL"}] {name}: {val}')
print(f'\n{"ALL PASSED" if all_ok else "FAILED"}')
