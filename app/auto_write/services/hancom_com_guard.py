"""hancom_com_guard — 한글 COM 기동 전 LocalServer32 검사(2024 로그인·우회 방지).

HWPFrame.HwpObject 가 HOffice130(한컴 2024)을 가리키면 Dispatch 전에 차단한다.
한컴계정 로그인 팝업 재발 방지. RHWP-only 경로로 우회하도록 안내한다.

환경 변수 ``AUTO_WRITE_ALLOW_HANCOM_2024_COM=1`` 로만 2024 COM 허용(명시적 opt-in).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    import winreg  # Windows only — Linux/CI 에서는 레지스트리 조회를 건너뛴다.
except ImportError:  # pragma: no cover
    winreg = None  # type: ignore[assignment]

_COM_CLSID = "{2291CF00-64A1-4877-A9B4-68CFE89612D6}"
_DOC130_CLSID = "{965829DB-438E-4d31-B4FA-F1F8819A35FD}"
_ENV_ALLOW_2024 = "AUTO_WRITE_ALLOW_HANCOM_2024_COM"


class HancomComGuardError(RuntimeError):
    """COM 기동이 정책상 차단될 때."""


@dataclass(frozen=True)
class HancomComSnapshot:
    hwpframe_localserver32: str | None
    hwp_document_130_localserver32: str | None
    dot_hwp_progid: str | None
    dot_hwpx_progid: str | None

    @property
    def hwpframe_is_2022(self) -> bool:
        v = self.hwpframe_localserver32 or ""
        return "HOffice120" in v and "HOffice130" not in v

    @property
    def hwpframe_is_2024(self) -> bool:
        return "HOffice130" in (self.hwpframe_localserver32 or "")

    def as_dict(self) -> dict[str, Any]:
        return {
            "HWPFrame.HwpObject.LocalServer32": self.hwpframe_localserver32,
            "Hwp.Document.130.LocalServer32": self.hwp_document_130_localserver32,
            "dot_hwp_progid": self.dot_hwp_progid,
            "dot_hwpx_progid": self.dot_hwpx_progid,
            "hwpframe_is_2022": self.hwpframe_is_2022,
            "hwpframe_is_2024": self.hwpframe_is_2024,
        }


def _reg_read(path: str) -> str | None:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path) as key:
            return winreg.QueryValue(key, None)
    except OSError:
        return None


def snapshot_hancom_com() -> HancomComSnapshot:
    """레지스트리 스냅샷. non-Windows 는 전부 None(COM 자체 불가)."""
    return HancomComSnapshot(
        hwpframe_localserver32=_reg_read(f"WOW6432Node\\CLSID\\{_COM_CLSID}\\LocalServer32"),
        hwp_document_130_localserver32=_reg_read(
            f"WOW6432Node\\CLSID\\{_DOC130_CLSID}\\LocalServer32"
        ),
        dot_hwp_progid=_reg_read(".hwp"),
        dot_hwpx_progid=_reg_read(".hwpx"),
    )


def allow_hancom_2024_com() -> bool:
    return os.environ.get(_ENV_ALLOW_2024, "").strip() in {"1", "true", "yes"}


def assert_safe_hwp_com_or_raise(*, allow_hancom_2024: bool | None = None) -> HancomComSnapshot:
    """Dispatch 직전 호출. 2024 COM이면 예외(기본). allow 시에만 통과."""
    snap = snapshot_hancom_com()
    allowed = allow_hancom_2024 if allow_hancom_2024 is not None else allow_hancom_2024_com()
    if allowed:
        return snap
    if snap.hwpframe_is_2024:
        raise HancomComGuardError(
            "HWPFrame.HwpObject가 한컴 Office 2024(HOffice130)를 가리킵니다. "
            "한글 2022 [도움말]→[한글 프로그램 등록] 후 재시도하거나, "
            "COM 없이 `cross_form_hwp_pipeline.py --engine rhwp-hwpx-fill --output hwpx` 를 사용하세요. "
            f"2024 COM을 의도적으로 쓰려면 환경변수 {_ENV_ALLOW_2024}=1 을 설정하세요."
        )
    if snap.hwpframe_localserver32 and not snap.hwpframe_is_2022:
        raise HancomComGuardError(
            f"HWPFrame LocalServer32가 한글 2022(HOffice120)가 아닙니다: "
            f"{snap.hwpframe_localserver32!r}. COM 기동을 중단합니다."
        )
    return snap
