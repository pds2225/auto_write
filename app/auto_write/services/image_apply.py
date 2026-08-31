# image_apply.py -- re-export from core.docx.services
from core.docx.services.image_apply import *  # noqa: F401,F403
from core.docx.services import image_apply as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
