"""bizplan_autopilot.py (CLI 진입점) — 제출 가능 사업계획서 생성·완성 오케스트레이터.

초안/메모 DOCX 를 받아 목표 점수까지 반복:
  AI 근거명시 작성 → 품질 오토파일럿(서식+이미지+PSST) → 공고 채점 → 목표 도달까지.

``app`` 디렉토리에서 실행하거나 ``app`` 이 sys.path 에 있어야 한다.

사용 예
-------
  cd D:\\auto_write\\app
  python bizplan_autopilot.py "C:\\초안\\사업계획서_초안.docx" --brief-file brief.txt
  python bizplan_autopilot.py 초안.docx --announcement-file 공고.txt --target-ratio 0.85 --max-loops 3
  python bizplan_autopilot.py 초안.docx --no-ai --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auto_write.services.bizplan_autopilot import run_bizplan_autopilot


def _read_text(path: str | None) -> str:
    """공고/브리프 파일에서 텍스트를 읽는다(DOCX/PDF/HWP/TXT 자동 인식)."""
    if not path:
        return ""
    if not Path(path).exists():
        return ""
    try:
        from auto_write.services.doc_text_extract import extract_text

        text, _notes = extract_text(path)
        return text
    except Exception:
        try:
            return Path(path).read_text(encoding="utf-8")
        except Exception:
            return ""


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="제출 가능 사업계획서 생성·완성 오케스트레이터 (AI작성+품질+채점 반복)"
    )
    parser.add_argument("input", help="초안/메모 DOCX 경로")
    parser.add_argument("--output", "-o", help="최종 출력 DOCX(미지정 시 results/ 자동 명명)")
    parser.add_argument("--brief", default="", help="사업 브리프 텍스트(아이디어·팀·수치)")
    parser.add_argument("--brief-file", help="사업 브리프 텍스트 파일 경로")
    parser.add_argument("--announcement-file", help="공고 평가기준 텍스트 파일(있으면 채점·목표반복)")
    parser.add_argument("--target-ratio", type=float, default=0.85, help="목표 충족률(기본 0.85)")
    parser.add_argument("--max-loops", type=int, default=3, help="최대 반복 횟수(기본 3)")
    parser.add_argument("--no-ai", action="store_true", help="AI 작성/채점 비활성(구조·서식만)")
    parser.add_argument("--placeholder-only", action="store_true", help="이미지를 자리표시만 삽입")
    parser.add_argument("--underline", action="store_true", help="강조 시 밑줄 추가")
    parser.add_argument("--blind-review", action="store_true",
                        help="블라인드 공고 모드 — ○○○ 마스킹 허용 + 실명 잔존 검출(fail)")
    parser.add_argument("--strict", action="store_true",
                        help="종료코드 계약 활성: 0=제출가능/2=제출불가 (기본은 항상 0)")
    parser.add_argument("--no-report", action="store_true", help="통합 리포트(md) 생략")
    parser.add_argument("--json", action="store_true", help="결과 JSON 출력")
    args = parser.parse_args(argv)

    brief = args.brief or _read_text(args.brief_file)
    announcement = _read_text(args.announcement_file) or None

    report = run_bizplan_autopilot(
        args.input,
        args.output,
        brief=brief,
        announcement_text=announcement,
        target_ratio=args.target_ratio,
        max_loops=args.max_loops,
        use_ai=not args.no_ai,
        placeholder_only=args.placeholder_only,
        underline=args.underline,
        blind_review=args.blind_review,
        write_report=not args.no_report,
    )

    def _strict_exit() -> int:
        if (args.strict and report.acceptance_verdict
                and not report.acceptance_submittable):
            return 2
        return 0

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return _strict_exit()

    print("=" * 64)
    print(f"AI 사용   : {'예' if report.ai_used else '아니오(키 미연결)'}")
    print(f"반복 횟수 : {report.loops_run} / 목표 {report.target_ratio*100:.0f}%")
    if report.score_history:
        last = report.score_history[-1]
        print(f"공고 채점 : {last.total_score}/{last.max_total} ({last.pass_ratio*100:.0f}%) "
              f"| 목표도달 {'예' if report.target_reached else '아니오'}")
    else:
        print("공고 채점 : 생략(공고 미제공 또는 AI 미연결)")
    gate = "통과" if report.final_gate_passed else "미달"
    print(f"서식 품질 : {report.final_quality_score:.1f}/100 (게이트 {gate})")
    if report.acceptance_verdict:
        print(f"수용검사  : {report.acceptance_verdict} (fail {report.acceptance_fail_defects}건)"
              + (" → 출력명에 _DRAFT 표시" if report.draft_marked else ""))
    print(f"이미지    : NotebookLM 슬라이드 프롬프트 {report.prompts_inserted}건")
    print(f"AI 보강   : {report.ai_areas_written}영역")
    print(f"출력 DOCX : {report.output_docx}")
    print(f"원본 백업 : {report.backup_dir}")
    if report.report_md:
        print(f"리포트    : {report.report_md}")
    if report.manual_todo:
        print("제출 전 확인 :")
        for t in report.manual_todo:
            print(f"  - {t}")
    print("=" * 64)
    return _strict_exit()


if __name__ == "__main__":
    sys.exit(main())
