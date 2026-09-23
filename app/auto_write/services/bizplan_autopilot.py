"""Backward-compatible module alias for the canonical bizplan service."""

import sys as _sys

from core.docx.services import bizplan_autopilot as _canonical

_sys.modules[__name__] = _canonical
