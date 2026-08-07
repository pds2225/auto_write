import zipfile, re, os, glob

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v4 = glob.glob(os.path.join(base, '*v4*.hwpx'))[0]
z = zipfile.ZipFile(v4)
c = z.read('Contents/section0.xml').decode('utf-8')

# Use actual Korean from the content
kw1 = '\uc791\uc131 \uc608\uc2dc\ub294 \uc0ad\uc81c'
kw2 = '\ud30c\ub780\uc0c9 \ub0b4\uc6a9 \ubb38\uad6c'
print(f'Guide kw1: {c.count(kw1)}')
print(f'Guide kw2: {c.count(kw2)}')

# Search for each occurrence
for kw in [kw1, kw2]:
    idx = 0
    while True:
        idx = c.find(kw, idx)
        if idx < 0:
            break
        snippet = c[max(0,idx-30):idx+len(kw)+30]
        print(f'  at {idx}: ...{snippet}...')
        idx += 1

# Content checks
print(f'\n3ucc28: {c.count(chr(0x3)+chr(0xcc28))}')

# Try finding plan text with a unique substring
plan_sub = '\ud1a0\ubc31\uc2a4 \ud615\uc0c1'
idx = c.find(plan_sub)
print(f'\nPlan [{plan_sub}] at: {idx}')

future_sub = '\ud611\uc57d \uc885\ub8cc \ud6c4'
idx = c.find(future_sub)
print(f'Future [{future_sub}] at: {idx}')
