"""cross_form_fill.py — 소스 사업계획서 A 의 값을 빈 양식 B 의 빈 칸에 전사하는 CLI.

완성된 문서 A 의 라벨-값을 빈 양식 B 의 유사 항목 칸에 자동으로 옮겨 적는다.
보수적 매칭(오매칭은 빈칸보다 나쁘다)·날조 0(소스 실값만)·원본 미수정.

사용법 (PowerShell):
    cd D:\auto_write\app
    python cross_form_fill.py --source A.docx --target B.docx -o out.docx
    python cross_form_fill.py --source A.hwp  --target B.hwp  -o out.hwp

결과는 AutofillReport(JSON)로 출력한다. 종료코드: 0=성공, 2=실패(ok=False).
"""

from __future__ import annotations

import argparse
import json
import sys

from auto_write.services.cross_form_autofill import autofill_from_source


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="소스 A 의 라벨-값을 빈 양식 B 의 유사 칸에 전사(결정론·보수적·날조0)")
    parser.add_argument("--source", required=True, help="소스(값이 채워진) DOCX/HWP/HWPX")
    parser.add_argument("--target", required=True, help="타깃(빈 양식) DOCX/HWP/HWPX")
    parser.add_argument("-o", "--out", required=True, help="출력 경로(원본과 같으면 거부)")
    parser.add_argument("--use-ai", action="store_true",
                        help="AI 사용(v1 미지원 슬롯 — 기본은 결정론 매칭)")
    args = parser.parse_args(argv)

    report = autofill_from_source(
        args.source, args.target, args.out, use_ai=args.use_ai)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 2


if __name__ == "__main__":
    sys.exit(main())
