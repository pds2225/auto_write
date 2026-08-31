# doc_text_extract.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.doc_text_extract
from core.docx.services.doc_text_extract import *  # noqa: F401,F403
from core.docx.services import doc_text_extract as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
