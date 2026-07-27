import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\21_기업민원처리센터 전문상담위원 추가모집"
items = []
for root, dirs, files in os.walk(p):
    for f in files:
        fp = os.path.join(root, f)
        items.append({"path": fp, "name": f, "size": os.path.getsize(fp), "ext": os.path.splitext(f)[1].lower()})
print(json.dumps(items, ensure_ascii=False, indent=2))
