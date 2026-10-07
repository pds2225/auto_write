"""CLI: 로컬 PC에서 auto_write 원격 제어를 준비·시작합니다.

    py -3.11 app/local_pc_remote.py --dest D:\\auto_write
    py -3.11 app/local_pc_remote.py --dest D:\\auto_write --start

기본은 계획만 보여 줍니다. 실제로 켜려면 --start (Windows PC에서).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from auto_write.services.local_pc_remote import (  # noqa: E402
    RemoteControlError,
    plan_remote_control,
    start_remote_control,
)
from auto_write.services.repo_clone import DEFAULT_CLONE_URL  # noqa: E402


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        description="로컬 PC(D:\\auto_write)에서 Cursor/Claude 원격 제어를 켭니다."
    )
    parser.add_argument("--dest", default=None, help=r"저장소 폴더 (기본: D:\auto_write)")
    parser.add_argument("--url", default=DEFAULT_CLONE_URL)
    parser.add_argument("--start", action="store_true", help="워커/세션을 실제로 시작")
    parser.add_argument(
        "--allow-non-windows",
        action="store_true",
        help="테스트용. 클라우드 VM에서 로컬 PC를 대체하지 않습니다.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.start:
            result = start_remote_control(
                args.dest,
                url=args.url,
                allow_non_windows=args.allow_non_windows,
            )
        else:
            result = plan_remote_control(args.dest, url=args.url)
    except RemoteControlError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = result.as_dict()
    payload["ok"] = True
    payload["started"] = bool(args.start)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(result.message)
        print("command:", " ".join(result.command))
        print(f"dest={result.dest}")
        print(f"backend={result.backend}")
        print(f"sha={result.sha}")
        if not args.start:
            print("시작하려면: remote_control.bat 를 더블클릭하거나 --start 를 붙이세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
