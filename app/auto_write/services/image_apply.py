# image_apply.py -- re-export from core.docx.services
from core.docx.services.image_apply import *  # noqa: F401,F403
from core.docx.services.image_apply import _find_anchor  # noqa: F401
from core.docx.services import image_apply as _canonical

# 이전 경로를 사용하는 보고서·검사 도구의 private helper도 유지한다.
globals().update({
    name: value for name, value in vars(_canonical).items()
    if name.startswith("_") and not name.startswith("__")
})
