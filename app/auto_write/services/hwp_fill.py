"""Backward-compatible module alias for the canonical HWP fill service."""

import sys as _sys

from core.docx.services import hwp_fill as _canonical

# Keep function globals and monkeypatch seams shared with the canonical module.
_sys.modules[__name__] = _canonical
