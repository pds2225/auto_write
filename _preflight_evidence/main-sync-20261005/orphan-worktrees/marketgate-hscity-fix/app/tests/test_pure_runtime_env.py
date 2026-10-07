"""test_pure_runtime_env.py — 실행 환경 capability 계약 안전망 (COM 미호출).

"이 PC(또는 원격·모바일)에서 무엇을 할 수 있는가"를 한 가지 JSON 스키마로 보고하는
모듈이다. 본선 엔진은 항상 **RHWP**(순수 파이썬 HWPX 채움)이고, 한글 COM 은
Windows + 한글2022 에서만 보조로 쓴다. 한글2024(HOffice130)는 로그인 팝업 때문에
정책상 차단한다.

한글 COM 검사는 **실제로 호출하지 않고** 가짜 함수로 갈아끼워 분기만 검증한다.
레지스트리·Dispatch 접근 없음. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- COM 이 있든 없든 ``recommended_engine()`` 은 항상 RHWP — COM 으로 흘러가지 않는다.
- 한글2024 는 COM 가용으로 보고되더라도 ``com_hwp=False`` 로 강등되고 사유가 남는다.
- COM 검사 자체가 터져도 예외가 새지 않고 notes 에 기록된다(진단이 죽지 않음).
- ``assert_engine_allowed`` 는 쓸 수 없는 COM 엔진 강제 지정을 막는다.
"""

from __future__ import annotations

import platform

import pytest

from auto_write.services import hancom_com_guard as guard_mod
from auto_write.services import hwp_docx_convert as convert_mod
from auto_write.services import runtime_env as mod
from auto_write.services.hancom_com_guard import HancomComSnapshot
from auto_write.services.runtime_env import (
    RuntimeCapabilities,
    assert_engine_allowed,
    detect_capabilities,
)

_MOBILE_ENVS = ("TERMUX_VERSION", "ANDROID_ROOT")


def _snapshot(localserver32: str | None) -> HancomComSnapshot:
    return HancomComSnapshot(
        hwpframe_localserver32=localserver32,
        hwp_document_130_localserver32=None,
        dot_hwp_progid=None,
        dot_hwpx_progid=None,
    )


@pytest.fixture
def no_mobile_env(monkeypatch):
    for name in _MOBILE_ENVS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def as_windows(monkeypatch, no_mobile_env):
    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")


@pytest.fixture
def as_linux(monkeypatch, no_mobile_env):
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")


def _fake_com(monkeypatch, *, available: bool, localserver32: str | None = None):
    """한글 COM 검사 2종을 가짜로 대체(실제 레지스트리·Dispatch 미접근)."""
    monkeypatch.setattr(convert_mod, "hancom_com_available", lambda: available)
    monkeypatch.setattr(
        guard_mod, "snapshot_hancom_com", lambda: _snapshot(localserver32)
    )


# --- RuntimeCapabilities 자체 (순수 데이터) ----------------------------------

def _caps(**kw) -> RuntimeCapabilities:
    base = dict(os_name="TestOS", python="3.11.9", is_windows=False, is_mobile_like=False)
    base.update(kw)
    return RuntimeCapabilities(**base)


def test_portable_core_true_by_default():
    # 기본값은 '어디서나 되는 핵심 기능이 전부 살아 있음'.
    assert _caps().portable_core is True


@pytest.mark.parametrize(
    "flag", ["rhwp_fill", "rhwp_read", "diagnose_docx", "diagnose_hwpx"]
)
def test_portable_core_false_if_any_core_capability_missing(flag):
    assert _caps(**{flag: False}).portable_core is False


def test_recommended_engine_is_rhwp_even_when_com_is_available():
    # 본선은 항상 RHWP — COM 이 있어도 COM 엔진을 권하지 않는다(정책).
    assert _caps().recommended_engine() == "rhwp-hwpx-fill"
    assert _caps(com_hwp=True, com_safe_2022=True).recommended_engine() == "rhwp-hwpx-fill"


def test_as_dict_schema_is_stable_for_ui_and_cli():
    data = _caps(notes=("메모",)).as_dict()
    assert set(data) == {
        "os_name", "python", "is_windows", "is_mobile_like", "portable_core",
        "capabilities", "recommended_engine", "notes", "contract",
    }
    assert set(data["capabilities"]) == {
        "rhwp_fill", "rhwp_read", "diagnose_docx", "diagnose_hwpx",
        "com_hwp", "com_safe_2022",
    }
    assert data["notes"] == ["메모"]  # tuple → list (JSON 직렬화 가능)


def test_contract_declares_hwpx_only_output():
    contract = _caps().as_dict()["contract"]
    assert "HWPX" in contract["everywhere"]
    assert "DOCX" in contract["not_allowed"]     # 승인 없는 DOCX 산출 금지
    assert "COM" in contract["windows_only"]


def test_capabilities_are_immutable():
    caps = _caps()
    with pytest.raises(Exception):     # frozen dataclass
        caps.com_hwp = True            # type: ignore[misc]


# --- detect_capabilities: 비-Windows -----------------------------------------

def test_linux_reports_no_com_but_keeps_portable_core(as_linux):
    caps = detect_capabilities()
    assert caps.is_windows is False
    assert caps.com_hwp is False and caps.com_safe_2022 is False
    assert caps.portable_core is True
    assert any("COM 미지원" in n for n in caps.notes)


def test_engine_note_is_always_appended(as_linux):
    assert detect_capabilities().notes[-1].startswith("본선 엔진=rhwp-hwpx-fill")


def test_python_version_is_reported(as_linux):
    assert detect_capabilities().python == platform.python_version()


def test_termux_environment_is_detected_as_mobile(monkeypatch):
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")
    caps = detect_capabilities()
    assert caps.is_mobile_like is True
    assert caps.com_hwp is False
    assert caps.portable_core is True   # 모바일에서도 HWPX 채움·진단은 그대로


# --- detect_capabilities: Windows + 한글 COM 분기 -----------------------------

def test_windows_with_hancom_2022_enables_com(as_windows, monkeypatch):
    _fake_com(monkeypatch, available=True, localserver32=r"C:\HOffice120\Bin\Hwp.exe")
    caps = detect_capabilities()
    assert caps.com_safe_2022 is True and caps.com_hwp is True
    assert caps.recommended_engine() == "rhwp-hwpx-fill"   # 그래도 본선은 RHWP


def test_windows_with_hancom_2024_is_blocked(as_windows, monkeypatch):
    # HOffice130(2024)은 한컴계정 로그인 팝업 때문에 Dispatch 차단 대상.
    _fake_com(monkeypatch, available=True, localserver32=r"C:\HOffice130\Bin\Hwp.exe")
    caps = detect_capabilities()
    assert caps.com_hwp is False
    assert any("2024" in n for n in caps.notes)


def test_windows_with_unknown_hancom_version_is_not_trusted(as_windows, monkeypatch):
    _fake_com(monkeypatch, available=True, localserver32=r"C:\HOffice110\Bin\Hwp.exe")
    caps = detect_capabilities()
    assert caps.com_hwp is False and caps.com_safe_2022 is False
    assert any("한글2022가 아님" in n for n in caps.notes)


def test_windows_without_registered_progid(as_windows, monkeypatch):
    _fake_com(monkeypatch, available=False)
    caps = detect_capabilities()
    assert caps.com_hwp is False
    assert any("ProgID 미등록" in n for n in caps.notes)


def test_com_probe_failure_is_swallowed_into_notes(as_windows, monkeypatch):
    def _boom():
        raise OSError("레지스트리 접근 불가")

    monkeypatch.setattr(convert_mod, "hancom_com_available", _boom)
    caps = detect_capabilities()          # 예외가 새면 진단 전체가 죽는다
    assert caps.com_hwp is False
    assert any("COM 검사 실패" in n and "OSError" in n for n in caps.notes)
    assert caps.portable_core is True     # RHWP 경로는 그대로 살아 있어야 한다


# --- assert_engine_allowed ---------------------------------------------------

def test_rhwp_engine_is_always_allowed(as_linux):
    assert assert_engine_allowed("rhwp-hwpx-fill") is None
    assert assert_engine_allowed("") is None


def test_com_engine_is_rejected_when_unavailable(as_linux):
    for engine in ("com-hwpx-fill", "hancom_com", "HANCOM_COM"):
        with pytest.raises(RuntimeError) as exc:
            assert_engine_allowed(engine)
        assert "rhwp-hwpx-fill" in str(exc.value)   # 대안을 함께 안내


def test_com_engine_is_allowed_on_hancom_2022(as_windows, monkeypatch):
    _fake_com(monkeypatch, available=True, localserver32=r"C:\HOffice120\Bin\Hwp.exe")
    assert assert_engine_allowed("hancom_com") is None


def test_com_engine_is_rejected_on_hancom_2024(as_windows, monkeypatch):
    _fake_com(monkeypatch, available=True, localserver32=r"C:\HOffice130\Bin\Hwp.exe")
    with pytest.raises(RuntimeError):
        assert_engine_allowed("com-hwpx-fill")
