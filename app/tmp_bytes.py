import zipfile, glob, os
base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v6 = glob.glob(os.path.join(base, '*v6*.hwpx'))[0]
z = zipfile.ZipFile(v6)
c = z.read('Contents/section0.xml').decode('utf-8')

idx = 165157
snippet = c[idx:idx+20]
anchor = '\uad6d\ub0b4 \ud1a0\uc218\uc988 \uc2dc\uc7a5'
print(f'Content at {idx}: {repr(snippet)}')
print(f'Anchor: {repr(anchor)}')
print(f'Match: {snippet[:len(anchor)] == anchor}')
print(f'Content bytes: {snippet.encode("utf-8").hex()}')
print(f'Anchor bytes: {anchor.encode("utf-8").hex()}')
