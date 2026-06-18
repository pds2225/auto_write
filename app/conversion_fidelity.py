"""conversion_fidelity.py — DOCX↔HWP 변환 일치도 측정 CLI.

**구조(structural) 일치도만 측정**한다 — 단락·표·셀·이미지·텍스트.
폰트·스타일·레이아웃 등 시각 서식은 범위 밖(구조 100% ≠ 시각 100%).

사용법 (PowerShell):
    cd D:\\auto_write\\app
    python conversion_fidelity.py a.docx --roundtrip          # a→hwp→a' 라운드트립 측정
    python conversion_fidelity.py a.docx --roundtrip --no-com # COM 건너뜀(측정 불가 보고)
    python conversion_fidelity.py a.docx b.docx               # 두 DOCX 구조 직접 비교

결과는 FidelityReport.as_dict() JSON 으로 stdout 에 출력한다(종료코드 0).
roundtrip 의 DOCX→HWP 는 한글(Hancom) COM 대화형 전용이라 **사용자가 직접 연
PowerShell** 에서만 실측된다(백그라운드/CI 에서는 ok=False + 안내).
"""

from __future__ import annotations

import argparse
import json
import sys

from auto_write.services.conversion_fidelity import (
    compare_docx_structure,
    measure_roundtrip_fidelity,
)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="DOCX↔HWP 변환 일치도 측정 (구조 일치도만, 읽기 전용)")
    parser.add_argument("docx_a", help="기준 DOCX (roundtrip 입력 또는 비교 A)")
    parser.add_argument("docx_b", nargs="?",
                        help="비교 대상 DOCX (생략 시 --roundtrip 필요)")
    parser.add_argument("--roundtrip", action="store_true",
                        help="a→hwp→a' 라운드트립 후 a 와 a' 의 구조 일치도를 측정")
    parser.add_argument("--no-com", action="store_true",
                        help="한글 COM 을 쓰지 않음(roundtrip 측정 불가 — 정직 보고)")
    args = parser.parse_args(argv)

    if args.roundtrip:
        report = measure_roundtrip_fidelity(args.docx_a, use_com=not args.no_com)
    elif args.docx_b:
        report = compare_docx_structure(args.docx_a, args.docx_b)
    else:
        parser.error("두 번째 DOCX 를 주거나 --roundtrip 을 지정하세요.")
        return 0  # pragma: no cover (parser.error 가 SystemExit)

    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
