import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
roots = [
    r"C:\Users\ekth3\OneDrive\바탕 화면",
    r"D:\auto_write\app\results",
    r"D:\auto_write\results",
]
patterns = (".hwp", ".hwpx", ".docx", ".pdf")
keywords = ("프로필", "이력", "resume", "profile", "company_master", "밸류", "상담", "민원", "master")
found = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        # skip deep trees
        rel = os.path.relpath(dirpath, root)
        if rel.count(os.sep) > 4:
            dirnames.clear()
            continue
        for f in filenames:
            fl = f.lower()
            if not fl.endswith(patterns):
                continue
            if any(k in f for k in keywords) or any(k in fl for k in ("profile", "resume", "master")):
                fp = os.path.join(dirpath, f)
                try:
                    found.append({"path": fp, "size": os.path.getsize(fp)})
                except OSError:
                    pass
print(json.dumps(found[:50], ensure_ascii=False, indent=2))
