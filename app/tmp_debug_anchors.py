import zipfile, glob, os, re

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
z = zipfile.ZipFile(v3)
c = z.read('Contents/section0.xml').decode('utf-8')

# Check each anchor
anchors = {
    'dev_start': '\u2460 \uc2dc\uc81c\ud488:',
    'dev_end': '\u2018\uc591\uc0b0 \uc9c1\uc804 \ub2e8\uacc4\u2019\uc774\ub2e4.',
    'field_start': '\uc591\uc0b0\uae08\ud615\uc124\uacc4',
    'field_end': '\uc591\uc0b0\uc5d0 \ucc3c\uc218\ud560 \uc218 \uc788\ub2e4.',
    'market_kw1': '\uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5\uc740',
    'market_end': '\ucc28\ubcc4\uc810\uc744 \ud568\uae4d \uc81c\uacf5\ud55c\ub2e4.',
}

for name, kw in anchors.items():
    idx = c.find(kw)
    print(f'{name}: {idx}')
    if idx >= 0:
        print(f'  ctx: {repr(c[idx:idx+40])}')
    else:
        # Try shorter
        for i in range(len(kw)-2, 0, -1):
            if c.find(kw[:i+1]) >= 0:
                print(f'  partial({i+1}): {repr(kw[:i+1])} at {c.find(kw[:i+1])}')
                break
