"""runtime_env — 어디서든(로컬/원격/다른PC/모바일) 동일한 capability 계약.

본선은 **RHWP**(순수 Python: hwpx_fill / unhwp / diagnose).
한글 COM 은 Windows+한글2022 에서만 선택적. 없으면 정직히 unavailable.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuntimeCapabilities:
    """환경이 무엇을 할 수 있는지 — UI/CLI 가 같은 JSON 스키마로 본다."""

    os_name: str
    python: str
    is_windows: bool
    is_mobile_like: bool
    rhwp_fill: bool = True          # HWPX ZIP/XML 직접 채움
    rhwp_read: bool = True          # unhwp / hwpx_xml 읽기
    diagnose_docx: bool = True
    diagnose_hwpx: bool = True
    com_hwp: bool = False           # 한글 Automation
    com_safe_2022: bool = False     # HOffice120
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def portable_core(self) -> bool:
        """로컬·원격·모바일에서 동일하게 동작하는 핵심."""
        return self.rhwp_fill and self.rhwp_read and self.diagnose_hwpx and self.diagnose_docx

    def recommended_engine(self) -> str:
        if self.com_hwp and self.com_safe_2022:
            return "rhwp-hwpx-fill"  # 본선은 여전히 RHWP; COM은 변환 보조만
        return "rhwp-hwpx-fill"

    def as_dict(self) -> dict[str, Any]:
        return {
            "os_name": self.os_name,
            "python": self.python,
            "is_windows": self.is_windows,
            "is_mobile_like": self.is_mobile_like,
            "portable_core": self.portable_core,
            "capabilities": {
                "rhwp_fill": self.rhwp_fill,
                "rhwp_read": self.rhwp_read,
                "diagnose_docx": self.diagnose_docx,
                "diagnose_hwpx": self.diagnose_hwpx,
                "com_hwp": self.com_hwp,
                "com_safe_2022": self.com_safe_2022,
            },
            "recommended_engine": self.recommended_engine(),
            "notes": list(self.notes),
            "contract": {
                "same_cli": "py -3.11 auto_write_hub.py …",
                # 본선 산출=HWPX만. DOCX로 만들면 안 됨(명시적 docx-crossform+승인 제외).
                "everywhere": "RHWP HWPX 채움 + HWPX 진단",
                "not_allowed": "승인 없는 DOCX 산출·DOCX-only 우회",
                "windows_only": "한글 COM (.hwp↔.hwpx 네이티브 변환)",
                "mobile": "Python 있으면 HWPX 채움·진단 동일. COM 없음. DOCX 만들지 않음.",
            },
        }


def _mobile_like() -> bool:
    """Android/iOS/Termux 등 — COM 불가, RHWP만."""
    sysname = platform.system().lower()
    if sysname in {"android", "ios", "darwin"} and (
        "ANDROID_ROOT" in os.environ or "TERMUX_VERSION" in os.environ
    ):
        return True
    # Termux often reports Linux
    if "TERMUX_VERSION" in os.environ or "ANDROID_ROOT" in os.environ:
        return True
    return False


def detect_capabilities() -> RuntimeCapabilities:
    notes: list[str] = []
    is_win = platform.system().lower() == "windows"
    mobile = _mobile_like()
    com = False
    safe_2022 = False

    if not is_win or mobile:
        notes.append("한글 COM 미지원 환경 — RHWP(hwpx) 경로만 사용")
    else:
        try:
            from .hwp_docx_convert import hancom_com_available
            from .hancom_com_guard import snapshot_hancom_com

            com = bool(hancom_com_available())
            if com:
                snap = snapshot_hancom_com()
                safe_2022 = snap.hwpframe_is_2022
                if snap.hwpframe_is_2024:
                    notes.append("COM이 2024(HOffice130) — Dispatch 차단, RHWP 사용")
                    com = False  # 정책상 사용 불가로 보고
                elif not safe_2022:
                    notes.append("COM LocalServer32가 한글2022가 아님 — RHWP 권장")
            else:
                notes.append("한글 COM ProgID 미등록")
        except Exception as exc:
            notes.append(f"COM 검사 실패: {type(exc).__name__}")

    notes.append("본선 엔진=rhwp-hwpx-fill (로컬/원격/모바일 동일)")
    return RuntimeCapabilities(
        os_name=platform.platform(),
        python=sys.version.split()[0],
        is_windows=is_win,
        is_mobile_like=mobile,
        com_hwp=com and safe_2022,
        com_safe_2022=safe_2022,
        notes=tuple(notes),
    )


def assert_engine_allowed(engine: str) -> None:
    """환경에 맞지 않는 엔진을 막는다(승인 없는 COM 강제 금지)."""
    caps = detect_capabilities()
    eng = (engine or "").lower()
    if eng in {"com-hwpx-fill", "hancom_com"} and not caps.com_hwp:
        raise RuntimeError(
            "이 환경에서는 한글 COM 엔진을 쓸 수 없습니다. "
            "--engine rhwp-hwpx-fill 을 사용하세요. "
            f"notes={list(caps.notes)}"
        )
