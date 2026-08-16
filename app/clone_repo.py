"""CLI: GitHub auto_write 저장소를 안전하게 clone 한다.

사용:
    py -3.11 app/clone_repo.py --dest D:\\auto_write
    py -3.11 app/clone_repo.py --dest D:\\auto_write --json

이미 같은 저장소가 있으면 덮어쓰지 않고 현재 SHA만 보여 준다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from auto_write.services.repo_clone import (  # noqa: E402
    DEFAULT_CLONE_URL,
    CloneError,
    clone_repository,
    default_dest,
)


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        description="pds2225/auto_write 를 git clone 합니다. 기존 폴더는 덮어쓰지 않습니다."
    )
    parser.add_argument(
        "--dest",
        default=None,
        help=r"받을 폴더 (Windows 기본: D:\auto_write)",
    )
    parser.add_argument("--url", default=DEFAULT_CLONE_URL, help="clone URL")
    parser.add_argument("--branch", default=None, help="받을 브랜치 (기본: 원격 HEAD)")
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    args = parser.parse_args(argv)

    try:
        dest = Path(args.dest) if args.dest else default_dest()
        result = clone_repository(dest, url=args.url, branch=args.branch)
    except CloneError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        payload = result.as_dict()
        payload["ok"] = True
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(result.message)
        print(f"url={result.url}")
        print(f"branch={result.branch}")
        print(f"sha={result.sha}")
        if result.action == "cloned":
            print("다음: setup.bat 을 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
