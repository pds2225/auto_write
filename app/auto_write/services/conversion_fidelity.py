# conversion_fidelity.py -- backward-compatible re-export from core.docx.services
# Canonical source: core.docx.services.conversion_fidelity
from core.docx.services.conversion_fidelity import *  # noqa: F401,F403
from core.docx.services import conversion_fidelity as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})


def measure_roundtrip_fidelity(docx_path, *, use_com=True, work_dir=None):
    """Compatibility facade that honors monkeypatches on auto_write's converter."""
    from pathlib import Path
    from . import hwp_docx_convert as converter

    source = Path(docx_path)
    if not source.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {source}")
    if not (use_com and converter.hancom_com_available()):
        report = FidelityReport(method="roundtrip")
        report.notes.append(
            "DOCX→HWP COM 대화형 전용 — roundtrip 측정 불가, "
            "이 PC 인터랙티브에서만. (CI/백그라운드 세션에서는 한글 COM 이 안 뜸)"
        )
        return report
    return _canonical.measure_roundtrip_fidelity(
        docx_path, use_com=use_com, work_dir=work_dir
    )


from core.docx.services import conversion_fidelity as _canonical
globals().update({k: v for k, v in vars(_canonical).items() if k.startswith("_") and not k.startswith("__")})
del _canonical
