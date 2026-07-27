import os
import sys

p = r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\21_기업민원처리센터 전문상담위원 추가모집"
if not os.path.isdir(p):
    print("NOT_FOUND", p, file=sys.stderr)
    sys.exit(1)
for root, dirs, files in os.walk(p):
    for f in files:
        fp = os.path.join(root, f)
        print(fp, os.path.getsize(fp))
