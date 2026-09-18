# hwp_docx_convert.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.hwp_docx_convert
from core.docx.services.hwp_docx_convert import *  # noqa: F401,F403
from core.docx.services.hwp_docx_convert import _nonempty_file, _resolve_paths  # noqa: F401
from core.docx.services import hwp_docx_convert as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
