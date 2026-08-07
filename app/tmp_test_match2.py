import zipfile, glob, os
base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
z = zipfile.ZipFile(v3)
c = z.read('Contents/section0.xml').decode('utf-8')

# Test each replacement's old text
tests = [
    ('\uad6d\ub0b4 \ubc1c\ub808\ubb34\uc6a9\uc218', 'purpose start'),
    ('\ud544\uc694\ud558\ub2e4.', 'purpose end'),
    ('\u2460 \uc2dc\uc81c\ud488:', 'dev start'),
    ('\uc591\uc0b0\uae08\ud615\uc124\uacc4', 'field start'),
    ('\uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5\uc740', 'market start'),
    ('\ud611\uc57d \uc885\ub8cc \ud6c4', 'future start'),
]

for text, label in tests:
    idx = c.find(text)
    print(f'{label}: idx={idx}')
    if idx < 0:
        # Try partial match
        for i in range(len(text)-2, 0, -1):
            partial = text[:i]
            if c.find(partial) >= 0:
                print(f'  Partial match [{partial[:20]}...]: {c.find(partial)}')
                break
