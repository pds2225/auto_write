# hwpx_fill.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.hwpx_fill
#
# import * 는 _이름(예: _set_cell_text, _strip_linesegarray)을 안 가져온다.
# 가드 테스트·우회 채움 경로가 그 이름을 쓰므로 정본 심볼을 전부 재노출한다.
from core.docx.services.hwpx_fill import *  # noqa: F401,F403
from core.docx.services import hwpx_fill as _canon

globals().update({k: v for k, v in vars(_canon).items() if not k.startswith("__")})
