# -*- coding: utf-8 -*-
"""Step 1: 서식.hwp -> 서식.hwpx (한글 COM)."""
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, r"D:\auto_write\app")
from auto_write.services.hwp_docx_convert import _convert_via_com, _SAVE_FORMATS

SRC = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
           r"\14_2026년도 인천광역시 중소기업 디자인개발지원사업 (하반기 일반기업 지원분야) 과제 모집(~7_14)"
           r"\붙임3_디자인개발지원_관련서식_2026.hwp")
DST = Path(r"D:\auto_write\WORKS\bnco_hwp\서식.hwpx")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main() -> int:
    if not SRC.exists():
        print("SRC MISSING")
        return 1
    before = sha256(SRC)
    print("SRC sha256(before) =", before)
    _convert_via_com(SRC, DST, _SAVE_FORMATS[".hwpx"])
    after = sha256(SRC)
    print("SRC sha256(after)  =", after)
    print("SRC unchanged:", before == after)
    print("DST exists:", DST.exists(), "size:", DST.stat().st_size if DST.exists() else 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
