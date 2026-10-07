"""DEPRECATED — cross_form_hwp_pipeline.py 를 사용하세요.

이 스크립트는 DOCX-only 우회 재발 방지를 위해 비활성화되었습니다.

대체 (RHWP, COM 없음, HWPX 출력):
  cd D:\\auto_write\\app
  py -3.11 cross_form_hwp_pipeline.py ^
      --notice-folder "C:\\...\\21_기업민원..." ^
      --engine rhwp-hwpx-fill --output hwpx --confirm-output-plan
"""
from __future__ import annotations

import sys

_MSG = """
ERROR: _finish_minwon_rhwp.py 는 사용 중단되었습니다.
승인 없는 DOCX-only 우회 재발 방지를 위해 cross_form_hwp_pipeline.py 로 통합했습니다.

예시 (HWPX, COM 없음):
  py -3.11 cross_form_hwp_pipeline.py --notice-folder "<공고폴더>" ^
      --engine rhwp-hwpx-fill --output hwpx --confirm-output-plan

예시 (DOCX, 명시적 선택):
  py -3.11 cross_form_hwp_pipeline.py --notice-folder "<공고폴더>" ^
      --engine docx-crossform --output docx --confirm-output-plan
"""


def main() -> int:
    print(_MSG.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
