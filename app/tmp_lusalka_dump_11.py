# -*- coding: utf-8 -*-
import json
import sys

import unhwp

sys.stdout.reconfigure(encoding="utf-8")

HWP = (
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
    r"\붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp"
)
data = json.loads(unhwp.parse(HWP).json)
content = data["sections"][0]["content"]

for i in range(15, 21):
    item = content[i]
    print("==== ITEM", i, list(item.keys()))

    def walk(o, path=""):
        if isinstance(o, dict):
            if "Text" in o and isinstance(o["Text"], dict):
                t = o["Text"]
                text = t.get("text") or ""
                st = t.get("style") or {}
                color = str(st.get("color", ""))
                if text.strip() or "0000FF" in color.upper() or "2E74B5" in color.upper():
                    print(
                        "  %s | %s %spt color=%s | %r"
                        % (
                            path,
                            st.get("font_name"),
                            st.get("font_size"),
                            color,
                            text[:120],
                        )
                    )
            for k, v in o.items():
                walk(v, path + "/" + k)
        elif isinstance(o, list):
            for j, x in enumerate(o):
                walk(x, path + "[%d]" % j)

    walk(item)
