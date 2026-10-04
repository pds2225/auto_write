# autopilot_pipeline.py -- re-export from core.docx.services
from core.docx.services.autopilot_pipeline import *  # noqa: F401,F403
# Keep legacy imports of these helpers working.  Star imports intentionally
# omit underscore-prefixed names, but the compatibility package historically
# exposed them to the existing test/report tooling.
from core.docx.services.autopilot_pipeline import (  # noqa: F401
    _RESIDUAL_RE,
    _build_todo,
    _write_report,
)
