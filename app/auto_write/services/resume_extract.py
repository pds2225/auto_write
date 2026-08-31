# resume_extract.py -- re-export from core.docx.services
from core.docx.services.resume_extract import *  # noqa: F401,F403
from core.docx.services import resume_extract as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
from core.docx.services.resume_extract import profile_to_json  # noqa: F401
