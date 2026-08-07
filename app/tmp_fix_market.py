import zipfile, glob, os

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v6 = glob.glob(os.path.join(base, '*v6*.hwpx'))[0]

z = zipfile.ZipFile(v6)
files = {n: z.read(n) for n in z.namelist()}
c = files['Contents/section0.xml'].decode('utf-8')

# Market: use correct anchor "토슈즈" = \ud1a0\uc288\uc988
m_s = c.find('\uc2dc\uc7a5\uc740 \uc5f0\uac04')
if m_s >= 0:
    # backtrack to include "국내 토슈즈"
    m_s = c.rfind('\uc740', 0, m_s)  # find the 은 before 시장
    if m_s >= 0:
        m_s += 1  # skip 은
    m_e = c.find('\ub2e4.', m_s)
    if m_e >= 0:
        m_e += 2
        new_m = (
            '\u2460 \uc2dc\uc7a5 \uaddc\ubaa8: \uad6d\ub0b4 \ud1a0\uc288\uc988 \uc2dc\uc7a5 \uc5f0\uac04 \uc57d 12.6\ub9cc \ucef4\ub808, 151\uc745 \uc6d0.\n'
            '\u2461 \ud310\ub9e4 \uacbd\ub858: B2C(\uc2a4\ub9c8\ud2b8\uc2a4\ud1a0\uc5b4) + B2B(\ubc1c\ub808\ud559\uc6d0/\uc608\uc220\uae30\uad00) \ubcd1\ud589.\n'
            '\u2462 \uac00\uaca9: \uc77c\ubc18\ud615 8\ub9cc\uc6d0, \ud504\ub9ac\ubbf8\uc5c4\ud615 15\ub9cc\uc6d0(\ud574\uc678 \ube0c\ub79c\ub4dc \ub300\ube44 33% \uc800\ub834).\n'
            '\u2463 \uae30\ud558 \uace0\uac1d: \ub17c\ud604\ub3d9 \ubcfc\uc1fc\uc774 \ubc1c\ub808\ud559\uc6d0(50\uc778) \ub4f1 \uc2dc\uc81c\ud488 \ud14c\uc2a4\ud2b8 \uc644\ub8cc.'
        )
        old = c[m_s:m_e]
        c = c.replace(old, new_m)
        print(f'Market: ok')
    else:
        print(f'Market: end not found')
else:
    print(f'Market: start not found')

files['Contents/section0.xml'] = c.encode('utf-8')
with zipfile.ZipFile(v6, 'w', zipfile.ZIP_DEFLATED) as z:
    for n, d in files.items():
        z.writestr(n, d)

z6 = zipfile.ZipFile(v6)
c6 = z6.read('Contents/section0.xml').decode('utf-8')
print(f'\u2460: {c6.count(chr(0x2460))}')
print(f'\u2463: {c6.count(chr(0x2463))}')
print(f'ill-fitting: {c6.count("ill-fitting")}')
