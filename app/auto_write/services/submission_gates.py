# submission_gates.py — re-export from core.docx.services
from core.docx.services.submission_gates import *  # noqa: F401,F403
from core.docx.services import submission_gates as _canon

globals().update({k: v for k, v in vars(_canon).items() if not k.startswith("__")})
