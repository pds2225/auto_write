import zipfile, glob, os
base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
z = zipfile.ZipFile(v3)
c = z.read('Contents/section0.xml').decode('utf-8')

old = '\uad6d\ub0b4 \ubc1c\ub808\ubb34\uc6a9\uc218 \ub300\uc0c1 \uc5f0\uad6c\uc5d0 \ub530\ub974\uba74 \uc871\ubd80 \uad00\ub828 \ubd80\uc0c1\uc774 \uc804\uccb4 \ubb34\uc6a9\uc0c1\ud574\uc758 58%\ub97c \ucc28\uc9c0\ud558\uace0,'
idx = c.find(old)
print(f'Match: {idx}')
if idx < 0:
    # Binary search for divergence
    lo, hi = 0, len(old)
    while lo < hi:
        mid = (lo + hi) // 2
        if c.find(old[:mid+1]) >= 0:
            lo = mid + 1
        else:
            hi = mid
    print(f'Diverges at char {lo}')
    found = c.find(old[:lo])
    if found >= 0:
        print(f'  Up to: {repr(old[:lo])}')
        print(f'  Content: {repr(c[found:found+lo+10])}')
        print(f'  Expected next: {repr(old[lo:lo+5])}')
