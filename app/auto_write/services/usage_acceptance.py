# usage_acceptance.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.usage_acceptance
from core.docx.services.usage_acceptance import *  # noqa: F401,F403
from core.docx.services import usage_acceptance as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
