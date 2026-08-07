import zipfile, glob, os
base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
z = zipfile.ZipFile(v3)
c = z.read('Contents/section0.xml').decode('utf-8')

# Test full old strings from v6d replacements
# Purpose old (first50 chars)
p_start = '\uad6d\ub0b4 \ubc1c\ub808\ubb34\uc6a9\uc218 \ub300\uc0c1 \uc5f0\uad6c\uc5d0 \ub530\ub974\uba74 \uc871\ubd80 \uad00\ub828 \ubd80\uc0c1\uc774 \uc804\uccb4 \ubb34\uc6a9\uc0c1\ud574\uc758 58%\ub97c \ucc28\uc9c0\ud558\uace0,'
idx = c.find(p_start)
print(f'Purpose old start: {idx}')
if idx >= 0:
    # Get the full text until purpose end
    end = c.find('\ud544\uc694\ud558\ub2e4.', idx)
    if end >= 0:
        full_old = c[idx:end+len('\ud544\uc694\ud558\ub2e4.')]
        print(f'  Full old length: {len(full_old)}')
        # Check if this exact string appears
        check = c.find(full_old)
        print(f'  Self-match: {check}')

# Dev old
d_start = '\u2460 \uc2dc\uc81c\ud488: 2023\ub144'
idx = c.find(d_start)
print(f'\nDev old start: {idx}')
if idx >= 0:
    end = c.find('\uc591\uc0b0 \uc9c1\uc804 \ub2e8\uacc4\u2019\uc774\ub2e4.', idx)
    if end >= 0:
        full = c[idx:end+len('\uc591\uc0b0 \uc9c1\uc804 \ub2e8\uacc4\u2019\uc774\ub2e4.')]
        print(f'  Length: {len(full)}')
        # Check for any XML tags inside
        import re
        tags = re.findall(r'<[^>]+>', full)
        print(f'  XML tags inside: {len(tags)}')
        if tags:
            print(f'  First tag: {tags[0][:50]}')
