"""lrule_gate.py — L규칙 CLI 게이트 (HWPX).

Sprint 3: ``hwpx_self_diagnose`` 래퍼. 종료코드 0/1/2/3 동일.
"""

from __future__ import annotations

import sys

from hwpx_self_diagnose import main as diagnose_main


def main(argv: list[str] | None = None) -> int:
    return diagnose_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
