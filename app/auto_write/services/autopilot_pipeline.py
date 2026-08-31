# autopilot_pipeline.py -- re-export from core.docx.services
from core.docx.services.autopilot_pipeline import *  # noqa: F401,F403
from core.docx.services import autopilot_pipeline as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})


def run_autopilot(*args, **kwargs):
    """Call the canonical pipeline while honoring facade-level replacements."""
    patched = ("run_acceptance", "force_draft_name")
    originals = {name: getattr(_canonical, name) for name in patched}
    try:
        for name in patched:
            setattr(_canonical, name, globals()[name])
        return _canonical.run_autopilot(*args, **kwargs)
    finally:
        for name, value in originals.items():
            setattr(_canonical, name, value)
