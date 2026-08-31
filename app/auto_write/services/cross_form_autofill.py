# cross_form_autofill.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.cross_form_autofill
from core.docx.services.cross_form_autofill import *  # noqa: F401,F403
from core.docx.services import cross_form_autofill as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
