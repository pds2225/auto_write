# -*- coding: utf-8 -*-
"""v6b: Fix purpose section + verify all plan sections are 개조식"""
import zipfile, os, re, glob
import xml.etree.ElementTree as ET

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
v6 = os.path.join(base, os.path.basename(v3).replace('_v3', '_v6'))

z3 = zipfile.ZipFile(v3)
files = {n: z3.read(n) for n in z3.namelist()}
c = files['Contents/section0.xml'].decode('utf-8')

# L012/L013 cleanup
c = c.replace('\uc791\uc131 \uc608\uc2dc\ub294 \uc0ad\uc81c', '')
for frag in ['\uc81c\ucd9c \uc2dc \ud30c\ub780\uc0c9 \ub0b4\uc6a9 \ubb38\uad6c\uc640 ', '\u203b ']:
    c = c.replace(frag, '')
c = re.sub(r'Clickhere:set:\d+:Direction:wstring:\d+: ?', '', c)
c = re.sub(r'HelpState:wstring:\d+: ?', '', c)
for ph in ['\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694.', '\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694']:
    c = c.replace(ph, '')

# Find purpose section by anchor and replace
# The purpose text starts with "국내 발레무용수" and ends with "필요하다."
purpose_anchor = '\uad6d\ub0b4 \ubc1c\ub808'
purpose_end = '\ud544\uc694\ud558\ub2e4.'
pi = c.find(purpose_anchor)
if pi >= 0:
    pe = c.find(purpose_end, pi) + len(purpose_end)
    old_p = c[pi:pe]
    new_p = '\u2460 \uc871\ubd80 \ubd80\uc0c1 \ud604\uc2e4: \uad6d\ub0b4 \ubc1c\ub808\ubb34\uc6a9\uc218 \ub300\uc0c1 \uc5f0\uad6c\uc5d0 \ub530\ub974\uba74, \uc871\ubd80 \uad00\ub828 \ubd80\uc0c1\uc774 \uc804\uccb4 \ubb34\uc6a9\uc0c1\ud574\uc758 58%\ub97c \ucc28\uc9c0\ud558\uace0 \uc804\ubb38 \ubb34\uc6a9\uc218 \uc57d 89%\uac00 \uc871\ubd80 \ubcc0\ud615, \ub9cc\uc131 \ud1b5\uc99d\uc744 \uacac\ub2e4. \ud1a0\uc218\uc988 \ucc29\uc6a9 \uc5f0\uc218\uac00 1\ub144 \ub297 \ub54c\ub9c8\ub2e4 \ud558\uc9c0 \ubd80\uc0c1 \uac00\ub2a5\uc131\uc774 21%\ub85c \ub192\uc544\uc9c4\ub2e4.\n\u2461 \ud574\uc678 \ube0c\ub79c\ub4dc \uc758\uc874 \ubb38\uc81c: Freed, Grishko, Bloch \ub4f1 \ud574\uc678 \ube0c\ub79c\ub4dc\uac00 \uc11c\uc591\uc778 \ubc1c\ud615 \uae30\uc900\uc73c\ub85c \uc81c\uc791\ub418\uc5b4, \ubc1c\ubc88\uc774 \ub111\uace0 \ubc1c\ub4f1\uc774 \ub192\uc740 \ud55c\uad6d\uc778 \ubc1c\ud615\uacfc \ub9de\uc9c0 \uc54a\ub2e4. \uad6d\ub0b4\uc5d0\ub294 \ud1a0\uc218\uc988 \uc81c\uc791 \uae30\ubc18\uc774 \uc5c6\uc5b4 \uc218\uc785 \uc81c\ud488 \uc758\uc874, \ud53d\ud305\ub3c4 \uacbd\ud5d8\uacfc \uac10 \uc758\uc874 \uc2e4\uc815.\n\u2462 \uc2dc\uc7a5 \uae30\ud68c: 20~40\ub300 \uc5ec\uc131 \uc911\uc2ec \uc131\uc778 \ubc1c\ub808 \uc218\uac15 \uc778\uad6d \uc99d\uac00\ub85c \ud1a0\uc218\uc988 \uc218\uc694 \ud568\uae4d \uc99d\uac00. \uc0ac\uc5c5\uc131 \ud655\uc778.\n\u2463 \ud604\uc7ac \ub2a8\uacc4: \uc2dc\uc81c\ud488, \ud544\ub4dc\ud14c\uc2a4\ud2b8\uae4c\uc9c0 \uc790\uccb4 \uc5ed\ub7c9 \uc644\ub8cc. \uc815\ubc00 \uc0ac\ucd9c \uae08\ud615 \uc124\uacc4, \uc81c\uc791\uc5d0\ub294 \uc804\ubb38 \uc7a5\ube44\uc640 \uc678\uc8fc\ube44\uc6a9 \ud544\uc694 \u2192 \uc9c0\uc6d0\uae30\uad00 \ub3c4\uc6c0 \ud544\uc694.'
    c = c.replace(old_p, new_p)
    print(f'Purpose: {len(old_p)}->{len(new_p)}')
else:
    print('Purpose anchor not found')

# 개조식: 제품개발현황
dev_anchor = '\u2460 \uc2dc\uc81c\ud488:'
dev_end = '\u2018\uc591\uc0b0 \uc9c1\uc804 \ub2e8\uacc4\u2019\uc774\ub2e4.'
di = c.find(dev_anchor)
if di >= 0:
    de = c.find(dev_end, di) + len(dev_end)
    old_d = c[di:de]
    new_d = '\u2460 \uc2dc\uc81c\ud488: 2023\ub144 \uac1c\ubc1c \ucc3c\uc218 \ud6c4 \uc54c\ud30c\ud14c\uc2a4\ud2b8(2025.10~11), \ud544\ub4dc\ud14c\uc2a4\ud2b8(2025.12~2026.01) \uac70\uccd0 \ub204\uc801 340\ucef4\ub808 \uc2dc\uc81c\ud488 \uc81c\uc791. 3\ucc28 \ud14c\uc2a4\ud2b8(2026.04) \uc120\ud654\uc608\uc220\uace0, H\ubc1c\ub808\ud559\uc6d0 \ub300\uc0c1 \uc9c4\ud589 \uc911.\n\u2461 \uc81c\uc870\uae30\ubc18: \ubca0\ud2b8\ub0a8 \ud638\uce58\ubbfc \uc81c\uc870\uacf5\uc7a5 \ub124\ud2b8\uc6cc\ud06c \ud655\ubcf4. \ubd09\uc81c(\uc778\uc2a4\ube44\ub098), \uc81c\ud654(\uc138\ube0c\uc6e8\uacf5\ubc29, 30\ub144 \uacbd\ub825), \ud604\uc9c0\uacf5\uc7a5 \uc5f0\uacb0(\ube44\u00b7\ucf54 \uc778\ud130\ub108\uc15c\ub09c) \ud300 \ud611\uc5c5.\n\u2462 \uc9c0\uc2dd\uc7ac\uc0b0: \u2018\ub8e8\uc0b4\uce74\u2019 \ud55c\uae00, \uc601\ubb38 \uc0c1\ud45c \ub4f1\ub85d \uc644\ub8cc(2025.08.26, \uc81c25\ub958 \ubc1c\ub808\uc6a9 \uc2e0\ubc1c).\n\u2463 \ub0a8\uc740 \uacfc\uc81c: \uc18c\uc7ac, \uad6c\uc870 \uac80\uc99d \uc644\ub8cc. \uc591\uc0b0\uc6a9 \ud1a0\ubc31\uc2a4 \uc0ac\ucd9c \uae08\ud615 \uc124\uacc4, \uc81c\uc791 \uc644\ub8cc \uc2dc \uc18c\ub7c9 \uc591\uc0b0 \uac00\ub2a5.'
    c = c.replace(old_d, new_d)
    print(f'Dev: {len(old_d)}->{len(new_d)}')
else:
    print('Dev anchor not found')

# 개조식: 지원 희망 분야
field_anchor = '\uc591\uc0b0\uae08\ud615\uc124\uacc4'
field_end = '\uc591\uc0b0 \ucc3c\uc218 \uac00\ub2a5.'
fi = c.find(field_anchor)
if fi >= 0:
    fe = c.find(field_end, fi) + len(field_end)
    old_f = c[fi:fe]
    new_f = '\u2460 \uc591\uc0b0\uae08\ud615\uc124\uacc4: 3D \uc871\ud615 \ub370\uc774\ud130\ub97c \ud65c\uc6a9\ud574 \ud55c\uad6d\uc778 \ud45c\uc900 \uc871\ud615 \uae30\uc900 \ud1a0\ubc31\uc2a4 \ud615\uc0c1, \uc0c5\ud06c \uac15\ub3c4 \ucd5c\uc885 CAD \uc124\uacc4.\n\u2461 \uc591\uc0b0\uae08\ud615\uc81c\uc791: \uc124\uacc4 \ud655\uc815 \ud6c4 \ud1a0\ubc31\uc2a4 \uc0ac\ucd9c\uc6a9 \uc815\ubc00 \uae08\ud615 1\uc2dd \uc81c\uc791.\n\u2462 \uc644\uc131 \ud6c4 \ubca0\ud2b8\ub0a8 \uc81c\uc870\uacf5\uc7a5\uc5d0\uc11c \uacfc\ub77c \uc18c\ub7c9 \uc591\uc0b0 \ucc3c\uc218 \uac00\ub2a5.'
    c = c.replace(old_f, new_f)
    print(f'Field: {len(old_f)}->{len(new_f)}')
else:
    print('Field anchor not found')

# 개조식: 시장분석
market_anchor = '\uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5\uc740'
market_end = '\ucc28\ubcc4\uc810\uc744 \ud568\uae4d \uc81c\uacf5\ud55c\ub2e4.'
mi = c.find(market_anchor)
if mi >= 0:
    me = c.find(market_end, mi) + len(market_end)
    old_m = c[mi:me]
    new_m = '\u2460 \uc2dc\uc7a5 \uaddc\ubaa8: \uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5 \uc5f0\uac04 \uc57d 12.6\ub9cc \ucef4\ub808, 151\uc745 \uc6d0(\uc804\ubb38 \ubb34\uc6a9\uc218 \uc57d 3,000\uba85 + \uc131\uc778 \ucde8\ubbf8 \ubc1c\ub808\uce35 \uc57d 3,000\uba85).\n\u2461 \ud310\ub9e4 \uacbd\ub858: B2C(\uc2a4\ub9c8\ud2b8\uc2a4\ud1a0\uc5b4 \uc9c1\uc811\ud310\ub9e4 + \uad6c\ub3c5\ud615 \uc7ac\uc8fc\ubb38) + B2B(\ubc1c\ub808\ud559\uc6d0, \uc608\uc220\uae30\uad00 \uc815\uae30\uacf5\uae09) \ubcd1\ud589.\n\u2462 \uac00\uaca9 \uaca9\ub9dd\ub825: \uc77c\ubc18\ud615 8\ub9cc\uc6d0, \ud504\ub9ac\ubbf8\uc5c4\ud615 15\ub9cc\uc6d0(\ud574\uc678 \ube0c\ub79c\ub4dc 9~18\ub9cc\uc6d0 \ub300\ube44 \uc57d 33% \uc800\ub834). \ucc28\ubcc4\uc810: \ub9de\ucda4 \uc124\uacc4 + \uacfc \uc218\uba85(5\ubc30 \ud5a8\uc9c0).\n\u2463 \uae30\ud558 \uace0\uac1d \ub124\ud2b8\uc6cc\ud06c: \ub17c\ud604\ub3d9 \ubcfc\uc1fc\uc774 \ubc1c\ub808\ud559\uc6d0(50\uc778), \uc120\ud654\uc608\uc220\uace0, \uc608\uc6d0\uc608\uc220\uc911, \ud55c\uc591\ub300, \uc774\ud654\uc5ec\ub300 \ubc1c\ub808\uc804\uacf5\uc0dd \ub124\ud2b8\uc6cc\ud06c\uc5d0\uc11c \uc2dc\uc81c\ud488 \ud14c\uc2a4\ud2b8 \uc644\ub8cc.'
    c = c.replace(old_m, new_m)
    print(f'Market: {len(old_m)}->{len(new_m)}')
else:
    print('Market anchor not found')

# 개조식: 향후 계획
future_anchor = '\ud611\uc57d \uc885\ub8cc \ud6c4'
future_end_m = '\ub77c\uc778 \ud655\uc7a5\uc774\ub2e4.'
fi2 = c.find(future_anchor)
if fi2 >= 0:
    fe2 = c.find(future_end_m, fi2) + len(future_end_m)
    old_fu = c[fi2:fe2]
    new_fu = '\u2460 \uc815\uc2dd \uc591\uc0b0: \ud655\ubcf4\ud55c \uae08\ud615\uc73c\ub85c \ubca0\ud2b8\ub0a8 \ud638\uce58\ubbfc \uc81c\uc870\uacf5\uc7a5 \ud1b5\ud55c \uc815\uc2dd \uc591\uc0b0, \ucd9c\uc2dc \uc2dc\uc791.\n\u2461 \ud310\ub9e4 \uacbd\ub858: \uc628\ub77c\uc778(\uc2a4\ub9c8\ud2b8\uc2a4\ud1a0\uc5b4, 3D \uc2a4\uce94 \ud6c4 \ub514\uc9c0\ud138 \uc871\ud615 \ud504\ub85c\ud544 \uc800\uc7a5 \u2192 \uc6d0\ud074\ub9ad \uc7ac\uc8fc\ubb38) + \ubc1c\ub808\ud559\uc6d0, \uc608\uc220\uae30\uad00 B2B \uc81c\ud734 \ubcd1\ud589.\n\u2462 \ub9e4\ucd9c \ubaa9\ud45c: 2026\ub144 \ud558\ubc18\uae30 \uc57d 2,200\ub9cc \uc6d0(\ucd08\ub3c4 \uc591\uc0b0 300\ucef4\ub808) \u2192 2027\ub144 \uc57d 1\uc745 7,000\ub9cc \uc6d0 \u2192 2028\ub144 \uc57d 5\uc745 \uc6d0(\ud574\uc678 \ud3ec\ud568).\n\u2463 \uae30\ub300\ud6a8\uacfc: \u2460 \uad6d\uc0b0 \ud1a0\uc218\uc988 \ube0c\ub79c\ub4dc \uc815\ub9bd(\uc218\uc785 \uc758\uc874 \ud0c8\ud53c) \u2461 \ubb34\uc6a9\uc218 \uc871\ubd80 \ubd80\uc0c1 \uac10\uc18c(ill-fitting \ubb38\uc81c \ud574\uacb0) \u2462 \uc18c\ubaa8\ud488 \ube44\uc6a9 \uc808\uac10(\uc57d 33% \uc800\ub834) \u2463 3D \uc871\ud615 DB \ucd95\uc801 \u2192 \ud6c4\uc18d \ub9de\ucda4\uc81c\ud488 \ub77c\uc778 \ud655\uc7a5.'
    c = c.replace(old_fu, new_fu)
    print(f'Future: {len(old_fu)}->{len(new_fu)}')
else:
    print('Future anchor not found')

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

with zipfile.ZipFile(v6, 'w', zipfile.ZIP_DEFLATED) as z:
    for n, d in files.items():
        z.writestr(n, d)

# Verify
z6 = zipfile.ZipFile(v6)
c6 = z6.read('Contents/section0.xml').decode('utf-8')
print(f'\n=== v6b verify ===')
print(f'\u2460: {c6.count(chr(0x2460))}')
print(f'\u2461: {c6.count(chr(0x2461))}')
print(f'\u2462: {c6.count(chr(0x2462))}')
print(f'\u2463: {c6.count(chr(0x2463))}')
print(f'L012 guide: {c6.count(chr(0xc791)+chr(0xc131)+" "+chr(0xc608)+chr(0xc2dc))}')
print(f'L013 ClickHere: {c6.count("Clickhere")}')
print(f'ill-fitting: {c6.count("ill-fitting")}')
print(f'Old style: {c6.count(chr(0xc6d0)+chr(0xc778)+"="+chr(0xc740))}')
