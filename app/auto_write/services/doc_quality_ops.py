# doc_quality_ops.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.doc_quality_ops
from core.docx.services.doc_quality_ops import *  # noqa: F401,F403
from core.docx.services import doc_quality_ops as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
