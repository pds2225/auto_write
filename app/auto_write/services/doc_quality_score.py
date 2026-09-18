# doc_quality_score.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.doc_quality_score
from core.docx.services.doc_quality_score import *  # noqa: F401,F403
from core.docx.services.doc_quality_score import _count_bold_paragraphs  # noqa: F401
from core.docx.services import doc_quality_score as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
