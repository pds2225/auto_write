# cross_form_autofill.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.cross_form_autofill
from core.docx.services.cross_form_autofill import *  # noqa: F401,F403
from core.docx.services.cross_form_autofill import (  # noqa: F401
    _FORM_GLOB_PATTERNS,
    _best_source_for_target,
    _bracket_conflict,
    _cluster_rep,
    _is_obvious_placeholder,
    _iter_all_tables,
    _key,
)
from core.docx.services import cross_form_autofill as _canon

globals().update({k: v for k, v in vars(_canon).items() if k.startswith("_") and not k.startswith("__")})
