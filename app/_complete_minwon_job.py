"""DEPRECATED — cross_form_hwp_pipeline.py 를 사용하세요.

이 스크립트는 COM 경로·출력 형식이 명시되지 않아 재발 방지를 위해 래퍼만 유지합니다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_NOTICE = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\21_기업민원처리센터 전문상담위원 추가모집"
)

_MSG = """
WARN: _complete_minwon_job.py → cross_form_hwp_pipeline.py 로 리다이렉트합니다.
--confirm-output-plan 이 없으면 실행이 거부됩니다.
"""


def main() -> int:
    print(_MSG.strip(), file=sys.stderr)
    app = Path(__file__).resolve().parent
    cmd = [
        sys.executable,
        "cross_form_hwp_pipeline.py",
        "--notice-folder",
        str(_NOTICE),
        "--engine",
        "com-hwpx-fill",
        "--output",
        "hwpx",
        "--output",
        "hwp",
        "--confirm-output-plan",
    ]
    return subprocess.call(cmd, cwd=app)


if __name__ == "__main__":
    raise SystemExit(main())
