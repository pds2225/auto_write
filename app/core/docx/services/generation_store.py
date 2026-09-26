"""Compatibility alias for the canonical generation trace store.

The implementation lives in ``auto_write.services.generation_store``.  Core
DOCX callers historically import this module through their package-relative
path, so this module must resolve to the same module object rather than copy
or wrap its functions.  Keeping one module object also preserves monkeypatch
and caller identity across the legacy and core import paths.
"""

from __future__ import annotations

import sys

from auto_write.services import generation_store as _canonical


# Make ``core.docx.services.generation_store`` an import alias, not a second
# implementation.  Subsequent imports and package-relative callers receive
# the canonical module and its exact public API.
sys.modules[__name__] = _canonical
