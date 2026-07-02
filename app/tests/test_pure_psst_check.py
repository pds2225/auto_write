"""test_pure_psst_check.py — PSST 등급 판정 순수 함수 안전망.

_grade(found, total) 의 4단계 등급(누락/미흡/적정/우수) 경계값을 직접 검증한다.
외부 의존 없음(정수 2개 → 문자열). 야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

import pytest

from auto_write.services.psst_check import _grade


@pytest.mark.parametrize(
    "found,total,expected",
    [
        (0, 4, "누락"),   # found == 0 → 무조건 누락
        (3, 0, "누락"),   # total <= 0 → 누락
        (0, 0, "누락"),
        (4, 4, "우수"),   # 1.0
        (9, 10, "우수"),  # 0.9 경계 (>= 0.9)
        (6, 10, "적정"),  # 0.6 경계 (>= 0.6)
        (3, 4, "적정"),   # 0.75
        (5, 10, "미흡"),  # 0.5
        (1, 4, "미흡"),   # 0.25
    ],
)
def test_grade_boundaries(found, total, expected):
    assert _grade(found, total) == expected


def test_grade_just_below_excellent():
    # 0.89 < 0.9 → 우수 아님, 적정
    assert _grade(89, 100) == "적정"


def test_grade_just_below_adequate():
    # 0.59 < 0.6 → 적정 아님, 미흡
    assert _grade(59, 100) == "미흡"
