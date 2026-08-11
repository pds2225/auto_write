# -*- coding: utf-8 -*-
"""Convert Lusalka v6.hwp -> temp.hwpx for style edit (원본 미수정)."""
from pathlib import Path
import sys
sys.path.insert(0, r'D:\auto_write\app')

from auto_write.services.hwp_docx_convert import _convert_via_com, _SAVE_FORMATS

base = Path(r'C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\25_2026 예술분야 예비창업 프로그램 참여자 모집')
src = base / '붙임1. [양식] 2026 예술분야 예비창업 프로그램 신청 통합서식_루살카_v6.hwp'
dst = Path(r'D:\auto_write\app\tmp_lusalka_v6_work.hwpx')

if dst.exists():
    dst.unlink()

print('converting...', src.name, '->', dst)
_convert_via_com(src, dst, _SAVE_FORMATS['.hwpx'])
print('ok', dst.exists(), dst.stat().st_size)
