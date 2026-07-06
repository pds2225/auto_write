# -*- coding: utf-8 -*-
"""Step 4: 검증 — zip 유효·재파싱·구조 보존(표/행/셀 수)·채운 값 spot-check·원본 해시."""
import hashlib
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\auto_write\app")
from lxml import etree
from auto_write.services.hwpx_fill import _q, _direct, _cell_text

BASE = Path(r"D:\auto_write\WORKS\bnco_hwp\서식.hwpx")           # COM 변환 원본(미수정 기준)
OUT = Path(r"D:\auto_write\WORKS\비앤코_디자인개발_서식채움_초안.hwpx")
SRC_HWP = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
               r"\14_2026년도 인천광역시 중소기업 디자인개발지원사업 (하반기 일반기업 지원분야) 과제 모집(~7_14)"
               r"\붙임3_디자인개발지원_관련서식_2026.hwp")
SRC_HASH_BEFORE = "9d2f17c5dd629b222a747df745ca2f03116a82f3d2543186dce80ed2ba6ef69a"
SECTION = "Contents/section0.xml"

ok = True


def check(name, cond, detail=""):
    global ok
    status = "PASS" if cond else "FAIL"
    if not cond:
        ok = False
    print(f"[{status}] {name} {detail}")


def structure(path: Path):
    root = etree.fromstring(zipfile.ZipFile(path).read(SECTION))
    tables = list(root.iter(_q("tbl")))
    rows = sum(len(_direct(t, "tr")) for t in tables)
    cells = sum(len(_direct(r, "tc")) for t in tables for r in _direct(t, "tr"))
    return root, tables, rows, cells


# 1) zip 유효성
with zipfile.ZipFile(OUT) as z:
    bad = z.testzip()
check("zip testzip", bad is None, f"(bad={bad})")

# 2) 재파싱 + 구조 보존
root_b, tbl_b, rows_b, cells_b = structure(BASE)
root_o, tbl_o, rows_o, cells_o = structure(OUT)
check("재파싱 OK", root_o is not None)
check("표 수 동일", len(tbl_b) == len(tbl_o), f"({len(tbl_b)} vs {len(tbl_o)})")
check("행 수 동일", rows_b == rows_o, f"({rows_b} vs {rows_o})")
check("셀 수 동일", cells_b == cells_o, f"({cells_b} vs {cells_o})")

# 3) 비섹션 엔트리 바이트 보존 + mimetype 선두 STORED
with zipfile.ZipFile(BASE) as zb, zipfile.ZipFile(OUT) as zo:
    names_b = zb.namelist()
    names_o = zo.namelist()
    check("엔트리 집합 동일", set(names_b) == set(names_o))
    check("mimetype 선두", names_o[0] == "mimetype")
    check("mimetype STORED", zo.getinfo("mimetype").compress_type == zipfile.ZIP_STORED)
    diff = [n for n in names_b if n != SECTION and zb.read(n) != zo.read(n)]
    check("비섹션 엔트리 바이트 보존", not diff, f"(diff={diff})")

# 4) 채운 값 spot-check (7개)
def cell(ti, ri, ci):
    return _cell_text(_direct(_direct(tbl_o[ti], "tr")[ri], "tc")[ci])

spots = [
    ("1-2호 과제명", cell(4, 1, 1), "한국인 족형 맞춤 발레 토슈즈 토컵·밑창 일체형(PP) 제품디자인 개발"),
    ("1-2호 참여기업명", cell(4, 2, 1), "비앤코 인터내셔날 (대표 임수미)"),
    ("1-2호 주관기관명(첫부분)", cell(4, 2, 3)[:11], "인천대학교 산학협력단"),
    ("1-1호 기업명", cell(2, 5, 2), "비앤코 인터내셔날"),
    ("1-1호 사업자번호", cell(2, 6, 3), "121-25-28496"),
    ("1-2호 지원필요성 첫줄", cell(4, 14, 1)[:11], "■ 시장 현황과 문제"),
    ("1-2호 용도특성 첫줄", cell(4, 12, 1)[:7], "■ 제품 개요"),
    ("1-2호 활용계획 첫줄", cell(4, 15, 1)[:6], "■ 활용계획"),
    ("1-2호 2024 매출", cell(4, 5, 2), "약 16억 원 [확인필요]"),
]
for name, got, want in spots:
    check(f"값 {name}", got == want, f"(got={got[:50]!r})")

# 5) 불가침 영역(1-3호 T5~T9, 동의서 T10~T14) 원본 동일
frozen_diff = []
for ti in range(5, 15):
    rb = _direct(tbl_b[ti], "tr")
    ro = _direct(tbl_o[ti], "tr")
    for ri, (trb, tro) in enumerate(zip(rb, ro)):
        for ci, (tcb, tco) in enumerate(zip(_direct(trb, "tc"), _direct(tro, "tc"))):
            if _cell_text(tcb) != _cell_text(tco):
                frozen_diff.append(f"T{ti}R{ri}C{ci}")
check("불가침 영역(1-3~1-6호) 무변경", not frozen_diff, f"(diff={frozen_diff})")

# 6) 원본 .hwp 해시 불변
h = hashlib.sha256(SRC_HWP.read_bytes()).hexdigest()
check("원본 .hwp 해시 불변", h == SRC_HASH_BEFORE, f"({h[:16]}...)")

print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
