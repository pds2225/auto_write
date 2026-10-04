"""Backward-compatible module alias for the canonical Hancom COM guard."""

import sys as _sys

from core.docx.services import hancom_com_guard as _canonical

_sys.modules[__name__] = _canonical
