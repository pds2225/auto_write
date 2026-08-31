# acceptance_remediation.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.acceptance_remediation
from core.docx.services.acceptance_remediation import *  # noqa: F401,F403
from core.docx.services import acceptance_remediation as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
