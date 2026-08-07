import zipfile, glob, os
base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
z = zipfile.ZipFile(v3)
c = z.read('Contents/section0.xml').decode('utf-8')

# Test: find a unique substring from the purpose section
test = '\uad6d\ub0b4 \ubc1c\ub808'
idx = c.find(test)
print(f'Test [{test}]: idx={idx}')
if idx >= 0:
    print(f'  Content: {repr(c[idx:idx+50])}')
    # Now try to find the exact string from my script
    full = '\uad6d\ub0b4 \ubc1c\ub808\ubb34\uc6a9\uc218 \ub300\uc0c1'
    idx2 = c.find(full)
    print(f'  Full [{full}]: idx={idx2}')

# Also test the ① character
test2 = '\u2460'
idx3 = c.find(test2)
print(f'\n\u2460: idx={idx3}')

# Print the actual bytes of the first match
if idx >= 0:
    snippet = c[idx:idx+10]
    print(f'  Bytes: {snippet.encode("utf-8").hex()}')
