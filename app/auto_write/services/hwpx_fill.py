# hwpx_fill.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.hwpx_fill
from core.docx.services.hwpx_fill import *  # noqa: F401,F403

# ``import *`` intentionally omits underscore-prefixed helpers, but the
# compatibility-layer services in this package use these canonical helpers.
# Re-export only the private symbols that are part of that existing internal
# service contract; keep the implementation in core/docx/services.
from core.docx.services.hwpx_fill import (  # noqa: F401
    _HP,
    _inline_texts,
    _local,
    _q,
    _same_file,
    _strip_linesegarray,
)
from core.docx.services import hwpx_fill as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
