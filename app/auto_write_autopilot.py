"""auto_write_autopilot.py (CLI 진입점) — 문서 품질 '수정' 오토파일럿.

진단만 하던 단계를 실제 수정으로 잇고 한 번에 무인 실행한다:
  백업+서식수정+점수게이트 → 이미지 실제 적용 → PSST 보강 → 통합 리포트.

``app`` 디렉토리에서 실행하거나 ``app`` 이 sys.path 에 있어야 한다.

사용 예
-------
  cd D:\\auto_write\\app
  python auto_write_autopilot.py "C:\\path\\사업계획서.docx"
  python auto_write_autopilot.py in.docx --output out.docx --underline
  python auto_write_autopilot.py in.docx --placeholder-only --no-psst --json
"""

from __future__ import annotations

import argparse
import json
import sys

from auto_write.services.autopilot_pipeline import run_autopilot


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="auto_write 문서 품질 수정 오토파일럿 (서식+이미지+PSST 무인 적용)"
    )
    parser.add_argument("input", help="입력 DOCX 경로")
    parser.add_argument("--output", "-o", help="최종 출력 DOCX(미지정 시 results/ 자동 명명)")
    parser.add_argument("--no-emphasis", action="store_true", help="핵심문장 Bold 강조 비활성")
    parser.add_argument("--underline", action="store_true", help="강조 시 밑줄도 추가")
    parser.add_argument("--keep-guides", action="store_true", help="양식 안내문구 삭제 비활성")
    parser.add_argument("--normalize-fonts", action="store_true", help="글자크기 이상치 보정 활성")
    parser.add_argument("--max-images", type=int, default=8, help="이미지 적용 최대 개수(기본 8)")
    parser.add_argument("--placeholder-only", action="store_true",
                        help="차트 생성 없이 자리표시만 삽입(가장 안전)")
    parser.add_argument("--no-psst", action="store_true", help="PSST 작성 보강 생략")
    parser.add_argument("--blind-review", action="store_true",
                        help="블라인드 공고 모드 — ○○○ 마스킹 허용 + 실명 잔존 검출(fail)")
    parser.add_argument("--required-format", default=None,
                        help="공고 요구 산출 형식(예: hwp) — 다르면 제출명 차단(_DRAFT)+변환 안내")
    parser.add_argument("--strict", action="store_true",
                        help="종료코드 계약 활성: 0=제출가능/2=제출불가·게이트미달/3=검사불능 (기본은 항상 0)")
    parser.add_argument("--submit-clean", action="store_true",
                        help="게이트 직전 NotebookLM 프롬프트를 md 로 보존 후 작업용 블록 제거(제출 정리)")
    parser.add_argument("--no-acceptance", action="store_true",
                        help="실사용 수용검사 게이트(DRAFT 마킹) 생략")
    parser.add_argument("--no-report", action="store_true", help="통합 리포트(md) 생성 생략")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 으로 출력")
    args = parser.parse_args(argv)

    report = run_autopilot(
        args.input,
        args.output,
        emphasize=not args.no_emphasis,
        underline=args.underline,
        remove_guides=not args.keep_guides,
        normalize_fonts=args.normalize_fonts,
        max_images=args.max_images,
        placeholder_only=args.placeholder_only,
        psst_scaffold=not args.no_psst,
        acceptance_gate=not args.no_acceptance,
        blind_review=args.blind_review,
        required_format=args.required_format,
        submit_clean=args.submit_clean,
        write_report=not args.no_report,
    )

    def _strict_exit() -> int:
        if not args.strict:
            return 0
        # 종료코드 4분류(ralplan v2 P2): 검사불능(환경 문제) > 문서 결함 순
        if report.acceptance_error or report.draft_mark_error:
            return 3
        if ((report.acceptance_verdict and not report.acceptance_submittable)
                or report.format_mismatch or not report.passed):
            return 2
        return 0

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return _strict_exit()

    print("=" * 64)
    print(f"문서 유형 : {report.doc_type}")
    gate = "통과" if report.passed else "미달"
    print(f"품질 점수 : {report.score_total:.1f}/100 - {report.grade} | 게이트 {gate} "
          f"(반복 {report.iterations}회)")
    print(f"후처리    : {report.ops_summary}")
    print(f"이미지    : NotebookLM 슬라이드 프롬프트 {report.prompts_inserted}건")
    print(f"PSST 보강 : {report.psst_areas_scaffolded}영역 / {report.psst_items_added}항목 "
          f"(충족률 {report.psst_overall_ratio*100:.0f}%)")
    if report.acceptance_verdict:
        print(f"수용검사  : {report.acceptance_verdict} (fail {report.acceptance_fail_defects}건)"
              + (" → 출력명에 _DRAFT 표시" if report.draft_marked else ""))
    print(f"출력 DOCX : {report.output_docx}")
    print(f"원본 백업 : {report.backup_dir}")
    if report.report_md:
        print(f"리포트    : {report.report_md}")
    if report.manual_todo:
        print("수동 보완 :")
        for t in report.manual_todo:
            print(f"  - {t}")
    print("=" * 64)
    return _strict_exit()


if __name__ == "__main__":
    sys.exit(main())
