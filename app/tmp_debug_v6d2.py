import zipfile, glob, os, re

base = r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\24_제품 양산 패키지 수혜기업 모집(~8_7)'
v3 = glob.glob(os.path.join(base, '*v3*.hwpx'))[0]
z = zipfile.ZipFile(v3)
files = {n: z.read(n) for n in z.namelist()}
c = files['Contents/section0.xml'].decode('utf-8')

# Apply L012/L013 cleanup
c = c.replace('\uc791\uc131 \uc608\uc2dc\ub294 \uc0ad\uc81c', '')
for frag in ['\uc81c\ucd9c \uc2dc \ud30c\ub780\uc0c9 \ub0b4\uc6a9 \ubb38\uad6c\uc640 ', '\u203b ']:
    c = c.replace(frag, '')
c = re.sub(r'Clickhere:set:\d+:Direction:wstring:\d+: ?', '', c)
c = re.sub(r'HelpState:wstring:\d+: ?', '', c)
for ph in ['\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694.', '\uc774\uace0\uc744 \ub9c8\uc6b0\uc2a4\ub85c \ub204\uad6c\uace0 \ub0b4\uc6a9\uc744 \uc785\ub825\ud558\uc138\uc694']:
    c = c.replace(ph, '')

# Now try the EXACT same strings from v6d
old_purpose = '\uad6d\ub0b4 \ubc1c\ub808\ubb34\uc6a9\uc218 \ub300\uc0c1 \uc5f0\uad6c\uc5d0 \ub530\ub974\uba74 \uc871\ubd80 \uad00\ub828 \ubd80\uc0c1\uc774 \uc804\uccb4 \ubb34\uc6a9\uc0c1\ud574\uc758 58%\ub97c \ucc28\uc9c0\ud558\uace0,'
idx = c.find(old_purpose)
print(f'Purpose: idx={idx}')
if idx >= 0:
    print(f'  OK, first 20: {repr(c[idx:idx+20])}')
    # Find the full old string
    end = c.find('\ud544\uc694\ud558\ub2e4.', idx)
    if end >= 0:
        full = c[idx:end+len('\ud544\uc694\ud558\ub2e4.')]
        print(f'  Full length: {len(full)}')
        # Now check if this EXACT string is what v6d uses
        # The v6d replacement string should match this
else:
    print('  NOT FOUND')
    # Check partial
    for i in range(5, len(old_purpose), 5):
        if c.find(old_purpose[:i]) < 0:
            print(f'  Diverges at {i}: {repr(old_purpose[:i][-10:])}')
            break
