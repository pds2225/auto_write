"""Backward-compatible module alias for the canonical HWP COM service.

The legacy path must share the canonical module globals so COM fixtures can
patch availability/dispatch without silently bypassing the patched behavior.
"""

import sys as _sys

from core.docx.services import hwp_com_fill as _canonical

_sys.modules[__name__] = _canonical
