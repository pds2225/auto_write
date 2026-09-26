"""Backward-compatible module alias for the canonical suggestion service.

Keeping one module object preserves legacy monkeypatch behavior while the
implementation remains solely in ``core.docx.services``.
"""

import sys as _sys

from core.docx.services import infographic_suggest as _canonical

_sys.modules[__name__] = _canonical
