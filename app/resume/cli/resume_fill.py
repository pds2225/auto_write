"""resume_fill.py — 범용 이력서 자동작성기 CLI.

원본 이력서(들) → 구조화 프로필(profile.json) → 빈 양식 채움.
구현: ``extract``(P1, M1) · ``fill``(P2, M3 — 신상정보 + 반복행 리스트 표).

사용법 (PowerShell):
    cd D:\auto_write\app
  # 이력서 폴더/파일 → profile.json (needs_confirm 목록 출력)
    python resume_fill.py extract "C:\\...\\01. 경영지도사 이력서" -o profile.json
    python resume_fill.py extract A.hwp B.hwpx -o profile.json --limit 3
    python resume_fill.py extract "폴더" -o profile.json --all   # 전체 병합
  # 빈 양식(HWPX) + profile.json → 채운 제출본
    python resume_fill.py fill 양식.hwpx --profile profile.json -o 완성본.hwpx

종료코드:
  extract — 0=성공(추출됨), 1=입력오류(파일 없음/인자 오류), 2=추출 0건.
  fill    — 0=채움 성공, 1=입력오류(파일 없음), 2=채운 행 0(매핑 실패).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from resume.services.resume_extract import (
    build_profile,
    format_build_korean,
    profile_to_json,
)


def _cmd_extract(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.inputs]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print("입력 경로 없음:", ", ".join(missing), file=sys.stderr)
        return 1
    limit = None if args.all else args.limit
    result = build_profile(
        list(paths),
        recursive=not args.no_recursive,
        prefer_resume=not args.no_prefer_resume,
        limit=limit,
    )
    print(format_build_korean(result))
    if args.output:
        out = Path(args.output)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(profile_to_json(result), encoding="utf-8")
            print(f"\n저장: {out}")
        except OSError as exc:
            print(f"\nprofile.json 저장 실패: {exc}", file=sys.stderr)
            # 추출 자체는 성공했으므로 아래 판정으로 종료코드 유지.
    if not result.merged_sources:
        return 2
    return 0


def _cmd_fill(args: argparse.Namespace) -> int:
    from resume.services.resume_fill_service import (
        fill_resume_form,
        format_fill_korean,
    )

    form = Path(args.form)
    if not form.exists():
        print(f"양식 파일 없음: {form}", file=sys.stderr)
        return 1
    prof_path = Path(args.profile)
    if not prof_path.exists():
        print(f"profile.json 없음: {prof_path}", file=sys.stderr)
        return 1
    try:
        prof = json.loads(prof_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"profile.json 로드 실패: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output) if args.output else form.with_name(form.stem + "_filled.hwpx")
    try:
        report = fill_resume_form(
            form, out, prof,
            identity_fill=not args.no_identity,
            normalize_black=not args.no_black,
        )
    except (FileNotFoundError, ValueError, TypeError) as exc:
        print(f"채움 실패: {exc}", file=sys.stderr)
        return 1

    print(format_fill_korean(report))
    filled_rows = sum(s["filled"] for s in report.sections)
    if filled_rows == 0 and not report.identity_filled:
        return 2  # 반복행·신상정보 모두 못 채움 = 매핑 실패
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume_fill", description="범용 이력서 자동작성기")
    sub = parser.add_subparsers(dest="command", required=True)

    ex = sub.add_parser("extract", help="원본 이력서 → 구조화 profile.json")
    ex.add_argument("inputs", nargs="+", help="이력서 파일(들) 또는 폴더")
    ex.add_argument("-o", "--output", help="profile.json 저장 경로")
    ex.add_argument("--limit", type=int, default=8,
                    help="폴더일 때 상위 N개만 병합(기본 8)")
    ex.add_argument("--all", action="store_true",
                    help="상위 N개 제한 없이 전체 병합")
    ex.add_argument("--no-recursive", action="store_true",
                    help="폴더 하위 재귀 스캔 끄기")
    ex.add_argument("--no-prefer-resume", action="store_true",
                    help="'이력서' 파일명 가산점 끄기")
    ex.set_defaults(func=_cmd_extract)

    fl = sub.add_parser("fill", help="빈 양식(HWPX) + profile.json → 채운 제출본")
    fl.add_argument("form", help="빈 이력서 양식(.hwpx)")
    fl.add_argument("--profile", required=True, help="profile.json 경로")
    fl.add_argument("-o", "--output", help="완성본 저장 경로(.hwpx, 기본 <양식>_filled.hwpx)")
    fl.add_argument("--no-identity", action="store_true",
                    help="신상정보 라벨-값 칸 채움 끄기(반복행만)")
    fl.add_argument("--no-black", action="store_true",
                    help="유색 예시체 검정 정규화 끄기")
    fl.set_defaults(func=_cmd_fill)
    return parser


def main(argv: list[str] | None = None) -> int:
    from auto_write.utils import force_utf8_console
    force_utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
