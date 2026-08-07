"""v6f: Use shorter, more robust anchors"""
import zipfile, glob, os, re
import xml.etree.ElementTree as ET

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
v6 = os.path.join(base, os.path.basename(v3).replace('_v3', '_v6'))

z3 = zipfile.ZipFile(v3)
files = {n: z3.read(n) for n in z3.namelist()}
c = files['Contents/section0.xml'].decode('utf-8')

# L012/L013
for g in ['\uc791\uc131 \uc608\uc2dc\ub294 \uc0ad\uc81c', '\uc791\uc131 \uc608\uc2dc\ub294\r\n\uc0ad\uc81c']:
    c = c.replace(g, '')
c = re.sub(r'Clickhere:set:\d+:Direction:wstring:\d+: ?', '', c)
c = re.sub(r'HelpState:wstring:\d+: ?', '', c)
for ph in ['\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694.', '\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694']:
    c = c.replace(ph, '')

def rep(c, s_kw, e_kw, new):
    si = c.find(s_kw)
    if si < 0:
        return c, False
    ei = c.find(e_kw, si)
    if ei < 0:
        return c, False
    ei += len(e_kw)
    return c.replace(c[si:ei], new), True

# Dev - use shorter end
new_dev = (
    '\u2460 \uc2dc\uc81c\ud488: 2023\ub144 \uac1c\ubc1c \ucc3c\uc218, '
    '\uc54c\ud30c\ud14c\uc2a4\ud2b8(2025.10~11)/\ud544\ub4dc\ud14c\uc2a4\ud2b8(2025.12~2026.01) \uac70\uccd0 340\ucef4\ub808 \uc81c\uc791. '
    '3\ucc28 \ud14c\uc2a4\ud2b8(2026.04) \uc9c4\ud589 \uc911.\n'
    '\u2461 \uc81c\uc870\uae30\ubc18: \ubca0\ud2b8\ub0a8 \ud638\uce58\ubbfc \uacf5\uc7a5 \ub124\ud2b8\uc6cc\ud06c \ud655\ubcf4. '
    '\ubd09\uc81c/\uc81c\ud654(30\ub144 \uacbd\ub825)/\ud604\uc9c0\uacf5\uc7a5 \uc5f0\uacb0 \ud300 \ud611\uc5c5.\n'
    '\u2462 \uc9c0\uc2dd\uc7ac\uc0b0: \u2018\ub8e8\uc0b4\uce74\u2019 \uc0c1\ud45c \ub4f1\ub85d \uc644\ub8cc(2025.08.26).\n'
    '\u2463 \ub0a8\uc740 \uacfc\uc81c: \uc18c\uc7ac/\uad6c\uc870 \uac80\uc99d \uc644\ub8cc. '
    '\uc591\uc0b0\uc6a9 \uae08\ud615 \uc124\uacc4/\uc81c\uc791 \uc644\ub8cc \uc2dc \uc18c\ub7c9 \uc591\uc0b0 \uac00\ub2a5.'
)
c, ok = rep(c, '\u2460 \uc2dc\uc81c\ud488: 2023', '\uc591\uc0b0 \uc9c1\uc804', new_dev)
print(f'Dev: {ok}')

# Field - find the actual cell content
# "양산금형설계·양산금형제작" is in a different cell (checkbox area)
# The field description text is in another cell
field_desc_start = c.find('\uc591\uc0b0\uae08\ud615\uc124\uacc4\u00b7\uc591\uc0b0\uae08\ud615\uc81c\uc791')
if field_desc_start >= 0:
    # Find end of this cell's text
    field_end = c.find('\uc218 \uc788\ub2e4.', field_desc_start)
    if field_end >= 0:
        field_end += len('\uc218 \uc788\ub2e4.')
        new_field = (
            '\u2460 \uc591\uc0b0\uae08\ud615\uc124\uacc4: 3D \uc871\ud615 \ub370\uc774\ud130 \uae30\ubc18 '
            '\ud1a0\ubc31\uc2a4 \ud615\uc0c1/\uc0c5\ud06c \uac15\ub3c4 \ucd5c\uc885 CAD \uc124\uacc4.\n'
            '\u2461 \uc591\uc0b0\uae08\ud615\uc81c\uc791: \uc124\uacc4 \ud655\uc815 \ud6c4 \uc815\ubc00 \uae08\ud615 1\uc2dd \uc81c\uc791.\n'
            '\u2462 \uc644\uc131 \ud6c4 \ubca0\ud2b8\ub0a8 \uacf5\uc7a5\uc5d0\uc11c \uc18c\ub7c9 \uc591\uc0b0 \ucc3c\uc218 \uac00\ub2a5.'
        )
        old = c[field_desc_start:field_end]
        c = c.replace(old, new_field)
        print(f'Field: True')
    else:
        print(f'Field: end not found')
else:
    print(f'Field: start not found')

# Market
market_start = c.find('\uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5')
if market_start >= 0:
    market_end = c.find('\ucc28\ubcc4\uc810', market_start)
    if market_end >= 0:
        # Find end of sentence after 차별점
        market_end = c.find('\ub2e4.', market_end)
        if market_end >= 0:
            market_end += 2  # len("다.")
            new_market = (
                '\u2460 \uc2dc\uc7a5 \uaddc\ubaa8: \uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5 \uc5f0\uac04 \uc57d 12.6\ub9cc \ucef4\ub808, 151\uc745 \uc6d0.\n'
                '\u2461 \ud310\ub9e4 \uacbd\ub858: B2C(\uc2a4\ub9c8\ud2b8\uc2a4\ud1a0\uc5b4) + B2B(\ubc1c\ub808\ud559\uc6d0/\uc608\uc220\uae30\uad00) \ubcd1\ud589.\n'
                '\u2462 \uac00\uaca9: \uc77c\ubc18\ud615 8\ub9cc\uc6d0, \ud504\ub9ac\ubbf8\uc5c4\ud615 15\ub9cc\uc6d0(\ud574\uc678 \ube0c\ub79c\ub4dc \ub300\ube44 33% \uc800\ub834).\n'
                '\u2463 \uae30\ud558 \uace0\uac1d: \ub17c\ud604\ub3d9 \ubcfc\uc1fc\uc774 \ubc1c\ub808\ud559\uc6d0(50\uc778) \ub4f1 \uc2dc\uc81c\ud488 \ud14c\uc2a4\ud2b8 \uc644\ub8cc.'
            )
            old_m = c[market_start:market_end]
            c = c.replace(old_m, new_market)
            print(f'Market: True')
        else:
            print(f'Market: sentence end not found')
    else:
        print(f'Market: 차별점 not found')
else:
    print(f'Market: start not found')

# L002
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

print(f'\nv6: {v6}')
print(f'lineseg: {rm}')

z6 = zipfile.ZipFile(v6)
c6 = z6.read('Contents/section0.xml').decode('utf-8')
print(f'\u2460: {c6.count(chr(0x2460))}')
print(f'L012: {c6.count(chr(0xc791)+chr(0xc131))}')
print(f'L013: {c6.count("Clickhere")}')
print(f'ill-fitting: {c6.count("ill-fitting")}')
