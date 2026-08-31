# bizplan_autopilot.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.bizplan_autopilot
from core.docx.services.bizplan_autopilot import *  # noqa: F401,F403
from core.docx.services import bizplan_autopilot as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})


def run_bizplan_autopilot(*args, **kwargs):
    """Call the canonical BP loop while preserving facade monkeypatch hooks."""
    from . import autopilot_pipeline as _autopilot_facade
    patched = {
        "run_autopilot": globals()["run_autopilot"],
    }
    originals = {name: getattr(_canonical, name) for name in patched}
    canonical_autopilot = _autopilot_facade._canonical
    autopilot_originals = {
        name: getattr(canonical_autopilot, name)
        for name in ("run_acceptance", "force_draft_name")
    }
    try:
        for name, value in patched.items():
            setattr(_canonical, name, value)
        canonical_autopilot.run_acceptance = _autopilot_facade.run_acceptance
        canonical_autopilot.force_draft_name = _autopilot_facade.force_draft_name
        return _canonical.run_bizplan_autopilot(*args, **kwargs)
    finally:
        for name, value in autopilot_originals.items():
            setattr(canonical_autopilot, name, value)
        for name, value in originals.items():
            setattr(_canonical, name, value)
