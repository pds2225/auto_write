# acceptance_remediation.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.acceptance_remediation
from core.docx.services.acceptance_remediation import *  # noqa: F401,F403
from core.docx.services import acceptance_remediation as _canon

globals().update({k: v for k, v in vars(_canon).items() if not k.startswith("__")})
