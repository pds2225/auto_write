"""hwp_fill.py — HWP 양식 빈 표 채우기 + 본문 보강 end-to-end CLI.

흐름: HWP/HWPX → DOCX → (표 채움 + 본문 보강) → HWP. 원본은 절대 수정하지 않는다.

사용법 (PowerShell):
    cd D:\auto_write\app
    python hwp_fill.py "양식.hwp" -o "완성.hwp" --identity-json id.json
    python hwp_fill.py "양식.hwpx" -o "완성.hwpx" --fill-plan-dir plan_dir --no-ai
    python hwp_fill.py "양식.hwp" -o "완성.hwp" --brief-file brief.txt

DOCX→HWP 는 한글(Hancom Office) COM 대화형 전용이므로 **사용자가 직접 연
PowerShell** 에서 실행해야 한다. COM 미가용 시 채움 완료 DOCX 만 보존된다.

종료코드: 0=정상 / 2=제출불가(_DRAFT) / 1=입력오류·변환실패.
"""

from __future__ import annotations

import argparse
import json
import sys

from auto_write.services.hwp_fill import fill_hwp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="HWP 양식 빈 표 채우기 + 본문 보강 (원본 보존)")
    parser.add_argument("src", help="입력 양식(.hwp/.hwpx)")
    parser.add_argument("-o", "--out", required=True, help="출력 경로(.hwp/.hwpx)")
    parser.add_argument("--identity-json", help="일반현황 표 라벨→값 JSON 파일")
    parser.add_argument("--fill-plan-dir", help="fill_plan.json 등 추가 채움 계획 폴더")
    parser.add_argument("--brief-file", help="사업 브리프 텍스트 파일(본문 보강용)")
    parser.add_argument("--no-ai", action="store_true", help="AI 본문 작성 비활성")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass

    identity = None
    if args.identity_json:
        try:
            identity = json.loads(open(args.identity_json, encoding="utf-8").read())
        except Exception as exc:
            print(f"[실패] identity-json 읽기 오류: {exc}")
            return 1
    brief = ""
    if args.brief_file:
        try:
            brief = open(args.brief_file, encoding="utf-8").read()
        except Exception as exc:
            print(f"[실패] brief-file 읽기 오류: {exc}")
            return 1

    try:
        report = fill_hwp(
            args.src, args.out,
            identity=identity,
            fill_plan_dir=args.fill_plan_dir,
            brief=brief,
            use_ai=not args.no_ai,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"[실패] {exc}")
        return 1

    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    if report.draft_marked:
        return 2
    if not report.ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
