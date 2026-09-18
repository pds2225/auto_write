"""Compatibility alias for the existing generation trace store.

The generation store remains canonical in ``auto_write.services`` while the
core OpenAI client imports it through the core service namespace.  Both paths
must resolve to the same module object so trace instrumentation and test
patches cannot diverge.
"""

import sys as _sys

from auto_write.services import generation_store as _canonical

_sys.modules[__name__] = _canonical
