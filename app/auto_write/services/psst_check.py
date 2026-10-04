# psst_check.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.psst_check
from core.docx.services.psst_check import *  # noqa: F401,F403
from core.docx.services.psst_check import _grade  # noqa: F401
from core.docx.services import psst_check as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
