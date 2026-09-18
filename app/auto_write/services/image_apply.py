# image_apply.py -- re-export from core.docx.services
from core.docx.services.image_apply import *  # noqa: F401,F403
from core.docx.services.image_apply import _find_anchor  # noqa: F401
from core.docx.services import image_apply as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
