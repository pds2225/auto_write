"""Backward-compatible module alias for the canonical HWP conversion service."""

import sys as _sys

from core.docx.services import hwp_docx_convert as _canonical

_sys.modules[__name__] = _canonical
