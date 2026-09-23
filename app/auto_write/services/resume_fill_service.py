"""Backward-compatible module alias for the canonical resume fill service."""

import sys as _sys

from core.docx.services import resume_fill_service as _canonical

_sys.modules[__name__] = _canonical
