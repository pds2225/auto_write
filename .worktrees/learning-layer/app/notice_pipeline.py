"""notice_pipeline.py — 공고 링크 → 다운로드 → 분석 → 일괄 채움 (한 번에).

사용 예 (PowerShell):
    cd D:\\auto_write\\app
    python notice_pipeline.py --url "<공고URL>" --source-pool "C:\\완성본폴더" --notify --open
    python notice_pipeline.py --notice-folder "C:\\공고\\01_STAR" --source-pool "C:\\완성본" --save-defaults
    python notice_pipeline.py --notice-folder "C:\\공고" --retry-confirm --notify

종료코드: 0=성공, 1=입력오류, 2=부분실패/마감경과/다운로드실패
"""

from __future__ import annotations

import argparse
import json
import sys

from auto_write.services.notice_pipeline import (
    format_pipeline_summary_korean,
    run_pipeline,
)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="공고 URL/폴더 → 분석 → 양식 일괄 채움 (mail+auto_write 통합)")
    parser.add_argument("--url", help="공고 상세 URL (다운로드부터)")
    parser.add_argument("--notice-folder", metavar="PATH",
                        help="이미 받아 둔 공고 폴더(다운로드 생략)")
    parser.add_argument("--source-pool", metavar="PATH",
                        help="완성본 A 폴더(생략 시 config 기본값)")
    parser.add_argument("--skip-download", action="store_true",
                        help="URL 이 있어도 다운로드 생략")
    parser.add_argument("-o", "--out", default=None,
                        help="출력 하위폴더명(기본: filled)")
    parser.add_argument("--save-defaults", action="store_true",
                        help="--source-pool 를 다음 실행 기본값으로 저장")
    parser.add_argument("--retry-confirm", action="store_true",
                        help="filled/confirm_*.json 으로 확인 칸만 재채움")
    parser.add_argument("--no-hwp", action="store_true", help="HWP 변환 끄기")
    parser.add_argument("--no-d", action="store_true",
                        help="서술 보강(bizplan) 단계 끄기")
    parser.add_argument("--use-ai-d", action="store_true",
                        help="서술 보강 시 AI 사용(키 필요)")
    parser.add_argument("--notify", action="store_true", help="완료 팝업")
    parser.add_argument("--open", action="store_true", help="filled 폴더 열기")
    parser.add_argument("--json", action="store_true", help="기계용 JSON 출력")
    args = parser.parse_args(argv)

    if not args.url and not args.notice_folder:
        parser.error("--url 또는 --notice-folder 중 하나는 필요합니다.")
    if args.save_defaults and not args.source_pool:
        parser.error("--save-defaults 는 --source-pool 과 함께 써 주세요.")

    result = run_pipeline(
        url=args.url,
        notice_folder=args.notice_folder,
        source_pool=args.source_pool,
        skip_download=args.skip_download or bool(args.notice_folder and not args.url),
        output_subdir=args.out,
        retry_confirm=args.retry_confirm,
        run_bizplan=not args.no_d,
        use_ai_bizplan=args.use_ai_d,
        convert_hwp=not args.no_hwp,
        notify=args.notify,
        open_folder_flag=args.open,
        save_defaults=args.save_defaults,
    )

    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_pipeline_summary_korean(result))
        for note in result.notes:
            print(f"※ {note}", file=sys.stderr)

    return result.exit_code if result.exit_code else (0 if result.ok else 2)


if __name__ == "__main__":
    sys.exit(main())
