# conversion_fidelity.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.conversion_fidelity
from core.docx.services.conversion_fidelity import *  # noqa: F401,F403
from core.docx.services.conversion_fidelity import _norm_text, _note_loss, _ratio  # noqa: F401
from core.docx.services import conversion_fidelity as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
