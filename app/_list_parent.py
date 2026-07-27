import os
p = r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
if os.path.isdir(p):
    for name in os.listdir(p):
        print(name)
else:
    print("PARENT NOT FOUND")
