# infographic_suggest.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.infographic_suggest
from core.docx.services.infographic_suggest import *  # noqa: F401,F403
from core.docx.services import infographic_suggest as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
