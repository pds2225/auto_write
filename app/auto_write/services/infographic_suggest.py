# infographic_suggest.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.infographic_suggest
from core.docx.services.infographic_suggest import *  # noqa: F401,F403
from core.docx.services.infographic_suggest import _SUGGESTION_RULES  # noqa: F401
from core.docx.services.infographic_suggest import _SLIDE_DESIGN_GUIDE  # noqa: F401
from core.docx.services import infographic_suggest as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
