"""resume_fill.py — 범용 이력서 자동작성기 CLI.

원본 이력서(들) → 구조화 프로필(profile.json) → (P2+) 빈 양식 채움.
현재 구현: ``extract`` (P1, M1). ``fill`` 은 P2/P3 에서 추가한다.

사용법 (PowerShell):
    cd D:\auto_write\app
  # 이력서 폴더/파일 → profile.json (needs_confirm 목록 출력)
    python resume_fill.py extract "C:\\...\\01. 경영지도사 이력서" -o profile.json
    python resume_fill.py extract A.hwp B.hwpx -o profile.json --limit 3
    python resume_fill.py extract "폴더" -o profile.json --all   # 전체 병합

종료코드: 0=성공(추출됨), 1=입력오류(파일 없음/인자 오류), 2=추출 0건.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auto_write.services.resume_extract import (
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
    return parser


def _force_utf8_console() -> None:
    """cp949 콘솔이 ⚠···— 등 비-cp949 문자를 못 찍어 크래시하는 것 방지."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
