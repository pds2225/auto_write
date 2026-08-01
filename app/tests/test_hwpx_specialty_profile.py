"""test_hwpx_specialty_profile.py — 모집분야 confirm-only."""

from __future__ import annotations

import pytest

from auto_write.services.hwpx_specialty_profile import (
    SpecialtyConfirmError,
    resolve_specialty_checks,
)


def test_empty_confirm_means_no_checks():
    assert resolve_specialty_checks([]) == []


def test_confirm_maps_to_coordinates():
    cols = resolve_specialty_checks(["경영활동", "특화분야"])
    labels = [c[2] for c in cols]
    assert "경영활동 전문상담" in labels
    assert "특화분야 전문상담" in labels
    assert all(isinstance(c[0], int) and isinstance(c[1], int) for c in cols)


def test_unknown_confirm_raises():
    with pytest.raises(SpecialtyConfirmError):
        resolve_specialty_checks(["없는분야"])
