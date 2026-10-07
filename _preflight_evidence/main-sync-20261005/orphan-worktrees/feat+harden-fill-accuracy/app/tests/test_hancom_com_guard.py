"""test_hancom_com_guard.py — COM 2024 차단·스냅샷 검증."""

from __future__ import annotations

import pytest

from auto_write.services.hancom_com_guard import (
    HancomComGuardError,
    HancomComSnapshot,
    assert_safe_hwp_com_or_raise,
)


def test_snapshot_properties():
    s = HancomComSnapshot(
        hwpframe_localserver32=r"C:\Hnc\Office 2022\HOffice120\Bin\Hwp.exe -Automation",
        hwp_document_130_localserver32=r"C:\Hnc\Office 2024\HOffice130\Bin\Hwp.exe",
        dot_hwp_progid="Hwp.Document.130",
        dot_hwpx_progid="Hwp.Document.hwpx.130",
    )
    assert s.hwpframe_is_2022
    assert not s.hwpframe_is_2024


def test_blocks_hoffice130(monkeypatch):
    snap = HancomComSnapshot(
        hwpframe_localserver32=r"C:\Hnc\Office 2024\HOffice130\Bin\Hwp.exe -Automation",
        hwp_document_130_localserver32=None,
        dot_hwp_progid="Hwp.Document.130",
        dot_hwpx_progid=None,
    )
    monkeypatch.setattr(
        "auto_write.services.hancom_com_guard.snapshot_hancom_com",
        lambda: snap,
    )
    monkeypatch.setattr(
        "auto_write.services.hancom_com_guard.allow_hancom_2024_com",
        lambda: False,
    )
    with pytest.raises(HancomComGuardError, match="HOffice130"):
        assert_safe_hwp_com_or_raise()


def test_allow_2024_opt_in(monkeypatch):
    snap = HancomComSnapshot(
        hwpframe_localserver32=r"C:\Hnc\Office 2024\HOffice130\Bin\Hwp.exe -Automation",
        hwp_document_130_localserver32=None,
        dot_hwp_progid=None,
        dot_hwpx_progid=None,
    )
    monkeypatch.setattr(
        "auto_write.services.hancom_com_guard.snapshot_hancom_com",
        lambda: snap,
    )
    assert assert_safe_hwp_com_or_raise(allow_hancom_2024=True) is snap
