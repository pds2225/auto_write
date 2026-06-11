"""hwp_docx.py — HWP/HWPX ↔ DOCX 양방향 변환 CLI.

확장자로 방향을 자동 인식한다 (.hwp/.hwpx → .docx, .docx → .hwp).
원본은 절대 수정하지 않는다(같은 경로 출력 금지).

사용법 (PowerShell):
    cd D:\auto_write\app
    python hwp_docx.py "양식.hwp"                      # → 양식.docx
    python hwp_docx.py "사업계획서.docx"               # → 사업계획서.hwp (한글 COM 필요)
    python hwp_docx.py "양식.hwp" -o "분석용.docx"
    python hwp_docx.py "양식.hwp" --no-com             # 한글 COM 건너뛰고 구조 변환만

DOCX→HWP 는 한글(Hancom Office) COM 이 필요하므로 **사용자가 직접 연 PowerShell**
에서 실행해야 한다(백그라운드 세션에서는 한글이 안 뜰 수 있음).
"""

from __future__ import annotations

import argparse
import sys

from auto_write.services.hwp_docx_convert import convert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="HWP/HWPX ↔ DOCX 양방향 변환 (원본 보존)")
    parser.add_argument("src", help="입력 파일(.hwp/.hwpx/.docx)")
    parser.add_argument("-o", "--out", help="출력 경로(기본: 입력과 같은 폴더, 반대 확장자)")
    parser.add_argument("--no-com", action="store_true",
                        help="한글 COM 을 쓰지 않고 구조 변환만 시도(HWP→DOCX 전용)")
    args = parser.parse_args(argv)

    try:
        report = convert(args.src, args.out, use_com=not args.no_com)
    except (ValueError, FileNotFoundError) as exc:
        print(f"[실패] {exc}")
        return 2

    if report.ok:
        print(f"[완료] {report.direction} ({report.method}) → {report.output}")
    else:
        print(f"[실패] {report.direction} 변환 실패")
    for note in report.notes:
        print(f"  - {note}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
