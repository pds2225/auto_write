"""HWPX 자가진단 게이트 — '인적사항' 판정이 문서 종류를 구분하는지 고정.

배경(실측 결함): 인적사항 표가 **아예 없는** 문서(사업계획서·계획서형 HWPX)를
진단하면 `filled=0` 이라는 이유로 인적 게이트가 fail → `ok=False`(exit 2,
'제출불가')로 오판했다. 또 기준이 3칸 고정이라 인적 칸이 1~2개뿐인 양식은
전부 채워도 영원히 fail 이었다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import hwpx_self_diagnose as diag
from auto_write.services.hwpx_fill_coverage import CoverageReport, SectionCoverage

_MINIMAL_SECTION = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"></hs:sec>'
)


def _hwpx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/hwp+zip")
        z.writestr("Contents/section0.xml", _MINIMAL_SECTION)
    return path


def _patch_coverage(monkeypatch, sections: list[SectionCoverage]) -> None:
    def fake(path):  # noqa: ANN001 - 테스트 스텁
        return CoverageReport(path=str(path), sections=sections)

    monkeypatch.setattr(diag, "score_hwpx_coverage", fake)


def _gate(rep, rule: str):
    return next(g for g in rep.gates if g.rule == rule)


def test_no_personal_table_is_not_submission_blocker(tmp_path: Path, monkeypatch):
    """인적사항 표가 없는 문서는 '해당 없음' — 제출불가로 막지 않는다."""
    _patch_coverage(monkeypatch, [SectionCoverage(name="인적", filled=0, empty=0)])
    rep = diag.diagnose_hwpx(_hwpx(tmp_path / "plan.hwpx"))
    assert _gate(rep, "인적").status == "warn"
    assert rep.ok is True


def test_small_personal_table_can_pass_when_fully_filled(tmp_path: Path, monkeypatch):
    """인적 칸이 2개뿐이면 2개를 다 채운 것으로 통과한다(3칸 고정 기준 제거)."""
    _patch_coverage(monkeypatch, [SectionCoverage(name="인적", filled=2, empty=0)])
    rep = diag.diagnose_hwpx(_hwpx(tmp_path / "form.hwpx"))
    assert _gate(rep, "인적").status == "pass"
    assert rep.ok is True


def test_unfilled_application_form_still_fails(tmp_path: Path, monkeypatch):
    """빈 신청서(칸은 있는데 안 채움)는 예전대로 fail — 완화가 아니라 구분이다."""
    _patch_coverage(monkeypatch, [SectionCoverage(name="인적", filled=0, empty=6)])
    rep = diag.diagnose_hwpx(_hwpx(tmp_path / "empty.hwpx"))
    assert _gate(rep, "인적").status == "fail"
    assert rep.ok is False


@pytest.mark.parametrize("filled,total,expected", [(1, 5, "fail"), (3, 5, "pass"), (5, 5, "pass")])
def test_threshold_is_min_three_or_total(tmp_path: Path, monkeypatch, filled, total, expected):
    _patch_coverage(monkeypatch, [SectionCoverage(name="인적", filled=filled, empty=total - filled)])
    rep = diag.diagnose_hwpx(_hwpx(tmp_path / f"f{filled}.hwpx"))
    assert _gate(rep, "인적").status == expected
