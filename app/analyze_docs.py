"""analyze_docs.py (CLI 진입점) — 공고문 분석 / 양식 분석.

공고문(DOCX/PDF/HWP/TXT)에서 평가기준·배점·자격·마감·제출서류 등을 추출하고,
제출 양식(DOCX/HWP/PDF)에서 작성 항목·필수입력·PSST 구조를 요약한다.

``app`` 디렉토리에서 실행하거나 ``app`` 이 sys.path 에 있어야 한다.

사용 예
-------
  cd D:\\auto_write\\app
  python analyze_docs.py announcement "C:\\공고\\모집공고.hwp"
  python analyze_docs.py announcement 공고.txt --text-of "직접 붙여넣은 공고 본문..."
  python analyze_docs.py form "C:\\양식\\사업계획서_양식.hwp"
  python analyze_docs.py folder "C:\\공고\\01_STAR-Exploration"
"""

from __future__ import annotations

import argparse
import json
import sys


def _print_announcement(r) -> None:
    print("=" * 64)
    print(f"[공고 분석] {r.source}")
    print(f"AI 사용: {'예' if r.ai_used else '아니오(휴리스틱)'} | 본문 {r.text_chars}자")
    print("-" * 64)
    if r.criteria:
        print(f"■ 평가기준 (총 {r.total_max_score}점)")
        for c in r.criteria:
            print(f"  - {c['name']}: {c['max_score']}점" + (f"  ({c['description']})" if c.get("description") else ""))
    else:
        print("■ 평가기준: 배점 항목을 찾지 못함(공고에 배점 미명시일 수 있음)")
    ki = r.key_info or {}
    print("-" * 64)
    print("■ 핵심 정보")
    def show(label, key):
        v = ki.get(key)
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        if v:
            print(f"  · {label}: {v}")
    show("지원대상", "support_target")
    show("지원자격", "eligibility")
    show("지원금액", "funding_amount")
    show("신청마감", "deadline")
    show("제출서류", "required_documents")
    show("지원내용", "support_content")
    show("가점/우대", "bonus_points")
    show("유의사항", "notes")
    if r.notes:
        print("-" * 64)
        print("※ 안내:")
        for n in r.notes:
            print(f"  - {n}")
    print("=" * 64)


def _print_form(r) -> None:
    print("=" * 64)
    print(f"[양식 분석] {r.template_name}")
    print(f"섹션 {r.section_count} | 표 {r.table_count}(필수셀 {r.required_cell_count}) | "
          f"이미지슬롯 {r.image_slot_count}")
    print(f"작성 항목 {r.question_count}개 (필수 {r.required_question_count}개)")
    present = [k for k, v in r.psst_present.items() if v]
    missing = [k for k, v in r.psst_present.items() if not v]
    print(f"PSST 존재: {', '.join(present) or '없음'} | 누락: {', '.join(missing) or '없음'}")
    print("-" * 64)
    if r.writable_items:
        print("■ 작성 항목(필수 우선):")
        for it in r.writable_items:
            print(f"  · {it}")
    if r.analysis_notes:
        print("-" * 64)
        print("※ 분석 노트:")
        for n in r.analysis_notes[:10]:
            print(f"  - {n}")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="공고문/양식 분석기")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ann = sub.add_parser("announcement", help="공고문 분석(평가기준·자격·마감·제출서류 등)")
    ann.add_argument("input", help="공고 파일(DOCX/PDF/HWP/TXT) 경로")
    ann.add_argument("--text-of", help="파일 대신 직접 공고 텍스트를 전달")
    ann.add_argument("--no-ai", action="store_true", help="AI 비활성(휴리스틱만)")
    ann.add_argument("--json", action="store_true", help="JSON 출력")

    frm = sub.add_parser("form", help="양식 분석(작성 항목·필수입력·PSST 구조)")
    frm.add_argument("input", help="양식 파일(DOCX/HWP/PDF) 경로")
    frm.add_argument("--json", action="store_true", help="JSON 출력")

    fld = sub.add_parser("folder", help="공고 폴더 통째 분석(공고+양식 목록, 한국어 요약)")
    fld.add_argument("input", help="공고 첨부 폴더 경로")
    fld.add_argument("--no-ai", action="store_true", help="AI 비활성(휴리스틱만)")
    fld.add_argument("--no-save-json", action="store_true",
                     help=".analysis/ JSON 저장 안 함")
    fld.add_argument("--json", action="store_true", help="한국어 요약 뒤 JSON 도 출력")

    args = parser.parse_args(argv)

    if args.cmd == "announcement":
        from auto_write.services.announcement_analyzer import analyze_announcement

        openai_service = None
        if args.no_ai:
            openai_service = _DummyNoAI()
        if args.text_of:
            r = analyze_announcement(args.text_of, is_text=True, openai_service=openai_service)
        else:
            r = analyze_announcement(args.input, openai_service=openai_service)
        if args.json:
            print(json.dumps(r.as_dict(), ensure_ascii=False, indent=2))
        else:
            _print_announcement(r)
        return 0

    if args.cmd == "form":
        from auto_write.services.form_analyzer import analyze_form

        r = analyze_form(args.input)
        if args.json:
            print(json.dumps(r.as_dict(), ensure_ascii=False, indent=2))
        else:
            _print_form(r)
        return 0

    if args.cmd == "folder":
        from auto_write.services.folder_analyzer import (
            analyze_folder,
            format_folder_summary_korean,
        )

        openai_service = None
        if args.no_ai:
            openai_service = _DummyNoAI()
        r = analyze_folder(
            args.input,
            openai_service=openai_service,
            save_json=not args.no_save_json,
        )
        print(format_folder_summary_korean(r))
        if args.json:
            print(json.dumps(r.as_dict(), ensure_ascii=False, indent=2))
        return 0

    parser.error("알 수 없는 명령")
    return 1


class _DummyNoAI:
    """--no-ai 용: available=False 로 휴리스틱 경로를 강제."""

    available = False

    def complete_json(self, *a, **k):
        return None

    def parse_announcement(self, *a, **k):  # pragma: no cover
        return []


if __name__ == "__main__":
    sys.exit(main())
