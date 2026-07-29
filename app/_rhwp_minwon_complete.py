"""DEPRECATED — cross_form_hwp_pipeline.py 를 사용하세요."""
from __future__ import annotations

import sys

if __name__ == "__main__":
    print(
        "ERROR: _rhwp_minwon_complete.py 는 중단되었습니다.\n"
        "  py -3.11 cross_form_hwp_pipeline.py --notice-folder <폴더> "
        "--engine rhwp-hwpx-fill --output hwpx --confirm-output-plan",
        file=sys.stderr,
    )
    raise SystemExit(2)
