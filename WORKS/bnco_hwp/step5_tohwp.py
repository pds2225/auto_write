# -*- coding: utf-8 -*-
"""Step 5(시도): 최종.hwpx -> 최종.hwp (한글 COM). 실패/행이면 .hwpx 만 납품."""
import sys
from pathlib import Path

sys.path.insert(0, r"D:\auto_write\app")
from auto_write.services.hwp_docx_convert import _convert_via_com, _SAVE_FORMATS

SRC = Path(r"D:\auto_write\WORKS\비앤코_디자인개발_서식채움_초안.hwpx")
DST = Path(r"D:\auto_write\WORKS\비앤코_디자인개발_서식채움_초안.hwp")

_convert_via_com(SRC, DST, _SAVE_FORMATS[".hwp"])
print("HWP OK:", DST.exists(), DST.stat().st_size if DST.exists() else 0)
