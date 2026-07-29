# -*- coding: utf-8 -*-
"""scripts/submission_regression_check.py — CLI 래퍼 (구현은 auto_write.services)."""
from __future__ import annotations

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from auto_write.services.submission_regression_check import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
