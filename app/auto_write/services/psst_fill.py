# psst_fill.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.psst_fill
from core.docx.services.psst_fill import *  # noqa: F401,F403
from core.docx.services import psst_fill as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
