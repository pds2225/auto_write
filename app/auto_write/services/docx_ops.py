# docx_ops.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.docx_ops
from core.docx.services.docx_ops import *  # noqa: F401,F403
from core.docx.services import docx_ops as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
