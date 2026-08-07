"""Fix remaining field + market in v6"""
import zipfile, glob, os

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v6 = glob.glob(os.path.join(base, '*v6*.hwpx'))[0]

z = zipfile.ZipFile(v6)
files = {n: z.read(n) for n in z.namelist()}
c = files['Contents/section0.xml'].decode('utf-8')

# Field: find "시제품 개발과" to "소량 양산으로 넘어가지 못하고 있다."
f_s = c.find('\uc2dc\uc81c\ud488 \uac1c\ubc1c\uacfc')
if f_s >= 0:
    # backtrack to include "양산금형설계·양산금형제작 지원을 희망한다."
    # The full cell text starts earlier
    f_s2 = c.rfind('\n', 0, f_s)
    f_e = c.find('\ub2e4.', f_s)
    if f_e >= 0:
        f_e += 2
        # Find the actual start of this cell's content
        # Look for the section label before it
        label_pos = c.rfind('\ud76c\uc6d0\ud55c\ub2e4.', 0, f_s)
        if label_pos >= 0:
            f_s = label_pos
        new_f = (
            '\u2460 \uc591\uc0b0\uae08\ud615\uc124\uacc4: 3D \uc871\ud615 \ub370\uc774\ud130 \uae30\ubc18 '
            '\ud1a0\ubc31\uc2a4 \ud615\uc0c1/\uc0c5\ud06c \uac15\ub3c4 \ucd5c\uc885 CAD \uc124\uacc4.\n'
            '\u2461 \uc591\uc0b0\uae08\ud615\uc81c\uc791: \uc124\uacc4 \ud655\uc815 \ud6c4 \uc815\ubc00 \uae08\ud615 1\uc2dd \uc81c\uc791.\n'
            '\u2462 \uc644\uc131 \ud6c4 \ubca0\ud2b8\ub0a8 \uacf5\uc7a5\uc5d0\uc11c \uc18c\ub7c9 \uc591\uc0b0 \ucc3c\uc218 \uac00\ub2a5.'
        )
        c = c.replace(c[f_s:f_e], new_f)
        print(f'Field: ok')
    else:
        print(f'Field: end not found')
else:
    print(f'Field: start not found')

# Market: find "국내 토슈즈 시장은"
m_s = c.find('\uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5')
if m_s >= 0:
    m_e = c.find('\ub2e4.', m_s)
    if m_e >= 0:
        m_e += 2
        new_m = (
            '\u2460 \uc2dc\uc7a5 \uaddc\ubaa8: \uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5 \uc5f0\uac04 \uc57d 12.6\ub9cc \ucef4\ub808, 151\uc745 \uc6d0.\n'
            '\u2461 \ud310\ub9e4 \uacbd\ub858: B2C(\uc2a4\ub9c8\ud2b8\uc2a4\ud1a0\uc5b4) + B2B(\ubc1c\ub808\ud559\uc6d0/\uc608\uc220\uae30\uad00) \ubcd1\ud589.\n'
            '\u2462 \uac00\uaca9: \uc77c\ubc18\ud615 8\ub9cc\uc6d0, \ud504\ub9ac\ubbf8\uc5c4\ud615 15\ub9cc\uc6d0(\ud574\uc678 \ube0c\ub79c\ub4dc \ub300\ube44 33% \uc800\ub834).\n'
            '\u2463 \uae30\ud558 \uace0\uac1d: \ub17c\ud604\ub3d9 \ubcfc\uc1fc\uc774 \ubc1c\ub808\ud559\uc6d0(50\uc778) \ub4f1 \uc2dc\uc81c\ud488 \ud14c\uc2a4\ud2b8 \uc644\ub8cc.'
        )
        c = c.replace(c[m_s:m_e], new_m)
        print(f'Market: ok')
    else:
        print(f'Market: end not found')
else:
    print(f'Market: start not found')

files['Contents/section0.xml'] = c.encode('utf-8')
with zipfile.ZipFile(v6, 'w', zipfile.ZIP_DEFLATED) as z:
    for n, d in files.items():
        z.writestr(n, d)

# Verify
z6 = zipfile.ZipFile(v6)
c6 = z6.read('Contents/section0.xml').decode('utf-8')
print(f'\n\u2460: {c6.count(chr(0x2460))}')
print(f'\u2461: {c6.count(chr(0x2461))}')
print(f'\u2462: {c6.count(chr(0x2462))}')
print(f'\u2463: {c6.count(chr(0x2463))}')
print(f'ill-fitting: {c6.count("ill-fitting")}')
print(f'L013: {c6.count("Clickhere")}')
