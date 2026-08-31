# hancom_com_guard.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.hancom_com_guard
from core.docx.services.hancom_com_guard import *  # noqa: F401,F403
from core.docx.services import hancom_com_guard as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})


def assert_safe_hwp_com_or_raise(*, allow_hancom_2024=None):
    """Call the canonical guard with facade-level test/runtime hooks."""
    originals = {
        "snapshot_hancom_com": _canonical.snapshot_hancom_com,
        "allow_hancom_2024_com": _canonical.allow_hancom_2024_com,
    }
    try:
        _canonical.snapshot_hancom_com = globals()["snapshot_hancom_com"]
        _canonical.allow_hancom_2024_com = globals()["allow_hancom_2024_com"]
        return _canonical.assert_safe_hwp_com_or_raise(
            allow_hancom_2024=allow_hancom_2024
        )
    finally:
        for name, value in originals.items():
            setattr(_canonical, name, value)
