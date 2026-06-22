"""document_quality_orchestrator.py (CLI 진입점)

auto_write 문서 품질 개선 하네스를 커맨드라인에서 실행한다.
``app`` 디렉토리에서 실행하거나 ``app`` 이 sys.path 에 있어야 한다.

사용 예
-------
  cd D:\\auto_write\\app
  python document_quality_orchestrator.py "C:\\path\\사업계획서.docx"
  python document_quality_orchestrator.py in.docx --output out.docx --underline
  python document_quality_orchestrator.py --rollback "..\\results\\backup\\20260605_120000" out.docx
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auto_write.config import get_settings, ensure_directories
from auto_write.services.document_quality_orchestrator import DocumentQualityOrchestrator


def _make_orchestrator() -> DocumentQualityOrchestrator:
    settings = get_settings()
    ensure_directories(settings)
    # 분류 보조용 AI는 선택 — 키 없으면 규칙 기반으로만 동작
    openai_service = None
    try:
        from auto_write.services.openai_client import OpenAIService
        svc = OpenAIService(settings)
        openai_service = svc if getattr(svc, "available", False) else None
    except Exception:
        openai_service = None
    return DocumentQualityOrchestrator(settings.results_root, openai_service=openai_service)


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔(cp949)에서 한글·기호(— ✅ ❌) 출력 시 UnicodeEncodeError 방지
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="auto_write 문서 품질 개선 하네스 (DOCX 후처리·검수·점수)"
    )
    parser.add_argument("input", nargs="?", help="입력 DOCX 경로")
    parser.add_argument("--output", "-o", help="출력 DOCX 경로(미지정 시 results/ 자동 명명)")
    parser.add_argument("--no-emphasis", action="store_true", help="핵심문장 Bold 강조 비활성")
    parser.add_argument("--underline", action="store_true", help="강조 시 밑줄도 추가")
    parser.add_argument("--keep-guides", action="store_true", help="양식 안내문구 삭제 비활성")
    parser.add_argument("--normalize-fonts", action="store_true", help="글자크기 이상치 보정 활성")
    parser.add_argument("--ruleset", choices=["auto", "bizplan", "report", "minimal", "off"],
                        default=None,
                        help="사업계획서 규칙 프리셋 적용(opt-in). auto=문서유형 자동 매핑, 미지정=현행")
    parser.add_argument("--no-report", action="store_true", help="리포트(md/json) 생성 생략")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 으로 출력")
    parser.add_argument("--rollback", nargs=2, metavar=("BACKUP_DIR", "TARGET"),
                        help="백업 디렉토리에서 TARGET 으로 원본 복구")
    args = parser.parse_args(argv)

    if args.rollback:
        backup_dir, target = args.rollback
        ok = DocumentQualityOrchestrator.rollback(backup_dir, target)
        print(f"[rollback] {'성공' if ok else '실패'}: {backup_dir} -> {target}")
        return 0 if ok else 1

    if not args.input:
        parser.error("입력 DOCX 경로가 필요합니다 (또는 --rollback 사용)")

    orch = _make_orchestrator()
    result = orch.run(
        args.input,
        args.output,
        emphasize=not args.no_emphasis,
        underline=args.underline,
        remove_guides=not args.keep_guides,
        normalize_fonts=args.normalize_fonts,
        write_report=not args.no_report,
        ruleset=args.ruleset,
    )

    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0

    s = result.score
    print("=" * 64)
    print(f"문서 유형 : {result.doc_type.type_label} ({result.doc_type.confidence:.0%})")
    print(f"품질 점수 : {s.total:.1f}/100 - {s.grade} | 게이트 {'통과' if result.passed else '미달'} (반복 {result.iterations}회)")
    o = result.ops
    print(f"후처리    : 안내문구-{o.guide_paragraphs_removed} 글머리표-{o.bullet_spacing_fixed} "
          f"표셀-{o.table_cells_cleaned} 빈단락-{o.empty_paragraphs_removed} 강조-{o.paragraphs_emphasized}")
    if result.psst:
        print(f"PSST      : {result.psst.summary}")
    print(f"이미지제안: {len(result.infographic.suggestions)}건 (기존 {result.infographic.existing_images}장)")
    print(f"출력 DOCX : {result.output_docx}")
    print(f"원본 백업 : {result.backup_dir}")
    if result.report_md:
        print(f"리포트    : {result.report_md}")
    if result.manual_review:
        print("수동 확인 :")
        for m in result.manual_review:
            print(f"  - {m}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
