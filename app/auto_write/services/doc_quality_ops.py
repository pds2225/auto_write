# doc_quality_ops.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.doc_quality_ops
from core.docx.services.doc_quality_ops import *  # noqa: F401,F403
from core.docx.services.doc_quality_ops import _is_guide_text  # noqa: F401
from core.docx.services import doc_quality_ops as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
