# -*- coding: utf-8 -*-
"""Step 2: 서식.hwpx 구조 dump — 표/행/셀 텍스트를 좌표와 함께 출력."""
import io
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\auto_write\app")
from lxml import etree
from auto_write.services.hwpx_fill import _q, _direct, _cell_text

HWPX = Path(r"D:\auto_write\WORKS\bnco_hwp\서식.hwpx")
OUT = Path(r"D:\auto_write\WORKS\bnco_hwp\dump.txt")
_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)


def main() -> int:
    buf = io.StringIO()
    with zipfile.ZipFile(HWPX) as z:
        names = [n for n in z.namelist() if _SECTION_RE.search(n)]
        print("sections:", names, file=buf)
        for name in sorted(names):
            root = etree.fromstring(z.read(name))
            tables = list(root.iter(_q("tbl")))
            print(f"\n===== {name}: tables={len(tables)}", file=buf)
            # 본문 단락(표 밖) 텍스트도 순서대로 — 서식 번호 헤더 위치 파악용
            body_paras = []
            for p in root.iter(_q("p")):
                # 표 안 단락 제외: 조상에 tc 가 있으면 skip
                anc = p.getparent()
                in_cell = False
                while anc is not None:
                    if str(anc.tag).endswith("}tc"):
                        in_cell = True
                        break
                    anc = anc.getparent()
                if in_cell:
                    continue
                txt = "".join(t.text or "" for t in p.iter(_q("t"))).strip()
                if txt:
                    body_paras.append(txt)
            print(f"--- body paragraphs ({len(body_paras)}):", file=buf)
            for i, txt in enumerate(body_paras):
                print(f"  P[{i}] {txt[:120]}", file=buf)
            for ti, tbl in enumerate(tables):
                rows = _direct(tbl, "tr")
                print(f"--- table[{ti}] rows={len(rows)}", file=buf)
                for ri, tr in enumerate(rows):
                    cells = _direct(tr, "tc")
                    for ci, tc in enumerate(cells):
                        txt = _cell_text(tc)
                        show = txt[:100] if txt else "(빈칸)"
                        print(f"  T{ti} R{ri} C{ci}: {show}", file=buf)
    OUT.write_text(buf.getvalue(), encoding="utf-8")
    print("dumped ->", OUT, len(buf.getvalue()), "chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
