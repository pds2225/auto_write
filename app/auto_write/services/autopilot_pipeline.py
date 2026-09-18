"""Backward-compatible alias for the canonical autopilot pipeline.

The legacy import path must expose the same module object as the canonical
implementation.  A star re-export copies function objects but not their
module globals, so monkeypatching ``force_draft_name`` through the legacy path
would otherwise fail to exercise the real rename-lock handling.
"""

import sys as _sys

from core.docx.services import autopilot_pipeline as _canonical

_sys.modules[__name__] = _canonical
