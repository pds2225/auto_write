"""cross_form_fill.py — 소스 사업계획서 A 의 값을 빈 양식 B 의 빈 칸에 전사하는 CLI.

완성된 문서 A 의 라벨-값을 빈 양식 B 의 유사 항목 칸에 자동으로 옮겨 적는다.
보수적 매칭(오매칭은 빈칸보다 나쁘다)·날조 0(소스 실값만)·원본 미수정.
**표 칸**과 **본문 단락형 빈칸("○ 라벨 : ____")** 을 모두 채운다(단락은 콜론 뒤가
빈칸일 때만 — 이미 채워짐·마스킹 ○○○·문장은 보존).
**한 줄에 여러 칸이 나란히 있어도**(예: "기업명 : ____    대표자 : ____") 각 칸을
개별 인식해 채운다(빈칸만, 이미 채워진/마스킹 칸과 칸 사이 간격은 그대로 보존).
**선택칸**(예: "사업자 형태 | □ 개인 | □ 법인")도 소스 값('개인사업자')과 정확히
한 옵션에만 매칭될 때만 ■ 로 체크한다(모호하면 보류 — 끄려면 --no-checkbox).

사용법 (PowerShell):
    cd D:\auto_write\app
  # 1쌍 채우기
    python cross_form_fill.py --source A.docx --target B.docx -o out.docx
  # 공고 폴더 양식 일괄 채우기 + HWP
    python cross_form_fill.py batch --notice-folder "C:\\공고폴더" \\
        --source-pool "C:\\완성본폴더" -o filled

결과: 단일 모드는 AutofillReport(JSON). 배치 모드는 한국어 요약(stdout).
종료코드: 0=성공, 2=실패(ok=False/예외).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from auto_write.services.cross_form_autofill import (
    autofill_from_source,
    batch_autofill_from_pool,
    format_batch_detail_korean,
    format_batch_summary_korean,
    format_single_summary_korean,
    format_source_pick_korean,
    rank_source_pool,
)


def _parse_confirmations(
    confirm: list[str] | None, confirm_file: str | None
) -> dict[str, str]:
    """--confirm / --confirm-file 입력을 {타깃: 소스} 확정 맵으로 합친다."""
    merged: dict[str, str] = {}
    if confirm_file:
        with open(confirm_file, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            for k, v in data.items():
                merged[str(k)] = str(v)
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict) or "target" not in item or \
                        "source" not in item:
                    raise ValueError(
                        "확정 파일 list 항목은 {\"target\":..., \"source\":...} 형식이어야 합니다")
                merged[str(item["target"])] = str(item["source"])
        else:
            raise ValueError("확정 파일은 JSON dict 또는 list 여야 합니다")
    for entry in confirm or []:
        if "=" not in entry:
            raise ValueError(f"--confirm 형식 오류('{entry}'): \"타깃=소스\" 형태여야 합니다")
        tgt, src = entry.split("=", 1)
        tgt, src = tgt.strip(), src.strip()
        if not tgt or not src:
            raise ValueError(f"--confirm 형식 오류('{entry}'): 타깃·소스가 비어 있습니다")
        merged[tgt] = src
    return merged


def _parse_source_keywords(raw: str | None) -> tuple[str, ...] | None:
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(parts) if parts else None


def _try_notify_popup(title_line: str) -> None:
    """Windows 토스트/팝업(있으면). 실패해도 CLI 는 계속."""
    script = Path.home() / ".claude" / "scripts" / "notify_popup.ps1"
    if not script.is_file():
        return
    try:
        subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script), "-Kind", "batch",
            ],
            input=title_line,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _run_single(args: argparse.Namespace) -> int:
    try:
        confirmations = _parse_confirmations(args.confirm, args.confirm_file)
        report = autofill_from_source(
            args.source, args.target, args.out, use_ai=args.use_ai,
            confirmations=confirmations or None,
            enable_checkbox=not args.no_checkbox)
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        err = {
            "source": args.source,
            "target": args.target,
            "output": args.out,
            "ok": False,
            "error": str(exc),
            "notes": [str(exc)],
        }
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 2

    # 성공(ok) 시 기본은 비개발자용 한국어 요약(무엇이 채워졌고/확인 필요/빈칸+다음 행동).
    # --json 이거나 실패(ok=False: 비지원 입력·전사 0건 등)면 기계용 원본 JSON(하위호환:
    # 실패 리포트는 구조화 JSON 으로 남긴다 — traceback/exit1 아님).
    if getattr(args, "json", False) or not report.ok:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_single_summary_korean(report))
    return 0 if report.ok else 2


def _run_pick(args: argparse.Namespace) -> int:
    target = Path(args.target) if args.target else None
    try:
        report = rank_source_pool(
            args.pool,
            target,
            _parse_source_keywords(args.source_keywords),
            recursive=args.recursive,
            prefer_resume=args.prefer_resume,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        err = {"ok": False, "error": str(exc)}
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 2

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_source_pick_korean(report))
    return 0 if report.recommended else 2


def _run_batch(args: argparse.Namespace) -> int:
    notice = args.notice_folder or args.target_folder
    if not notice:
        print("배치 모드에는 --notice-folder(또는 --target-folder)가 필요합니다.", file=sys.stderr)
        return 2
    if not args.source_pool:
        print("배치 모드에는 --source-pool 이 필요합니다.", file=sys.stderr)
        return 2

    try:
        confirmations = _parse_confirmations(args.confirm, args.confirm_file)
        report = batch_autofill_from_pool(
            notice,
            args.source_pool,
            output_subdir=args.out or "filled",
            source_keywords=_parse_source_keywords(args.source_keywords),
            recursive=args.recursive,
            prefer_resume=args.prefer_resume,
            use_ai=args.use_ai,
            confirmations=confirmations or None,
            enable_checkbox=not args.no_checkbox,
            convert_hwp=not args.no_hwp,
        )
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"[실패] {exc}", file=sys.stderr)
        return 2

    summary = format_batch_summary_korean(report)
    print(summary)

    # 양식별 상세(확인 필요 칸의 --confirm 명령 + 빈칸 목록). 집계만으론 "어느 칸?
    # 무슨 명령?"을 알 수 없던 갭을 메운다. 확인 필요·빈칸이 없으면 빈 문자열이라 생략.
    detail = format_batch_detail_korean(report)
    if detail:
        print()
        print(detail)

    if args.json:
        print(json.dumps({
            "notice_folder": report.notice_folder,
            "source_pool": report.source_pool,
            "output_dir": report.output_dir,
            "ok_count": report.ok_count,
            "hwp_count": report.hwp_count,
            "items": [
                {
                    "target": i.target,
                    "source": i.source,
                    "output": i.output,
                    "hwp_output": i.hwp_output,
                    "ok": i.ok,
                    "transcribed": i.transcribed,
                    "needs_confirm_count": i.needs_confirm_count,
                    "needs_confirm": i.needs_confirm,
                    "unmatched_targets": i.unmatched_targets,
                    "hwp_ok": i.hwp_ok,
                    "notes": i.notes,
                }
                for i in report.items
            ],
            "skipped_targets": report.skipped_targets,
        }, ensure_ascii=False, indent=2))

    if args.notify:
        _try_notify_popup(summary.split("\n")[0])

    if not report.items:
        return 2
    return 0 if report.ok_count > 0 else 2


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="소스 A 의 라벨-값을 빈 양식 B 의 유사 칸에 전사(결정론·보수적·날조0)")
    sub = parser.add_subparsers(dest="command")

    # --- 단일 1쌍 ---
    single = sub.add_parser("fill", help="소스 1개 → 타깃 1개 채우기(기본)")
    single.add_argument("--source", required=True, help="소스(값이 채워진) DOCX/HWP/HWPX")
    single.add_argument("--target", required=True, help="타깃(빈 양식) DOCX/HWP/HWPX")
    single.add_argument("-o", "--out", required=True, help="출력 경로(원본과 같으면 거부)")
    single.add_argument("--use-ai", action="store_true",
                        help="AI 사용(v1 미지원 슬롯 — 기본은 결정론 매칭)")
    single.add_argument("--confirm", action="append", metavar="타깃=소스",
                        help="needs_confirm 후보 확정 적용(반복 가능)")
    single.add_argument("--confirm-file", metavar="PATH",
                        help="확정 맵 JSON 파일")
    single.add_argument("--no-checkbox", action="store_true",
                        help="선택칸 자동 체크 끄기")
    single.add_argument("--json", action="store_true",
                        help="사람용 요약 대신 기계용 원본 JSON 출력")

    # --- 배치: 공고 폴더 ---
    batch = sub.add_parser("batch", help="공고 폴더 양식 일괄 채우기 + HWP")
    batch.add_argument("--notice-folder", "--target-folder",
                        dest="notice_folder", metavar="PATH", required=True,
                        help="공고 첨부가 모인 폴더(양식 파일들)")
    batch.add_argument("--source-pool", required=True, metavar="PATH",
                       help="완성본 A 가 있는 폴더(키워드+최신순으로 1개 선택)")
    batch.add_argument("-o", "--out", default="filled",
                       help="공고 폴더 안 출력 하위폴더명(기본: filled)")
    batch.add_argument("--source-keywords", metavar="KW,KW,...",
                       help="소스 A 선택용 파일명 키워드(쉼표 구분, 기본: 사업계획서,신청서,...)")
    batch.add_argument("--recursive", action="store_true",
                       help="소스 풀 하위 폴더까지 재귀 스캔")
    batch.add_argument("--prefer-resume", action="store_true",
                       help="이력서 파일명·날짜 우선, 신청/동의/추천서 감점")
    batch.add_argument("--use-ai", action="store_true")
    batch.add_argument("--confirm", action="append", metavar="타깃=소스")
    batch.add_argument("--confirm-file", metavar="PATH")
    batch.add_argument("--no-checkbox", action="store_true")
    batch.add_argument("--no-hwp", action="store_true",
                       help="HWP 자동 변환 끄기(DOCX만 저장)")
    batch.add_argument("--notify", action="store_true",
                       help="완료 시 Windows 팝업(가능할 때만)")
    batch.add_argument("--json", action="store_true",
                       help="한국어 요약 뒤에 기계용 JSON 도 출력")

    # --- 소스 풀 추천 ---
    pick = sub.add_parser("pick", help="소스 풀에서 최적 완성본 1개 추천")
    pick.add_argument("--pool", required=True, metavar="PATH",
                      help="완성본 A 가 있는 폴더")
    pick.add_argument("--target", metavar="PATH",
                      help="dry-run 매칭용 타깃 양식(선택)")
    pick.add_argument("--recursive", action="store_true",
                      help="하위 폴더까지 재귀 스캔")
    pick.add_argument("--prefer-resume", action="store_true",
                      help="이력서 파일명·날짜 우선, 신청/동의/추천서 감점")
    pick.add_argument("--source-keywords", metavar="KW,KW,...",
                      help="파일명 키워드(쉼표 구분)")
    pick.add_argument("--json", action="store_true",
                      help="한국어 요약 대신 JSON 출력")

    # 하위호환: subcommand 없이 --source --target
    parser.add_argument("--source", help=argparse.SUPPRESS)
    parser.add_argument("--target", help=argparse.SUPPRESS)
    parser.add_argument("-o", "--out", help=argparse.SUPPRESS)
    parser.add_argument("--use-ai", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--confirm", action="append", metavar="타깃=소스",
                        help=argparse.SUPPRESS)
    parser.add_argument("--confirm-file", metavar="PATH", help=argparse.SUPPRESS)
    parser.add_argument("--no-checkbox", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)

    if args.command == "batch":
        return _run_batch(args)
    if args.command == "pick":
        return _run_pick(args)
    if args.command == "fill":
        return _run_single(args)

    # 레거시: python cross_form_fill.py --source ... --target ... -o ...
    if args.source and args.target and args.out:
        return _run_single(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
