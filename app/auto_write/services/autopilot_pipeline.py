"""기존 import와 monkeypatch가 정본 파이프라인에 함께 적용되도록 한다."""

import sys as _sys

from core.docx.services import autopilot_pipeline as _canonical

_sys.modules[__name__] = _canonical
