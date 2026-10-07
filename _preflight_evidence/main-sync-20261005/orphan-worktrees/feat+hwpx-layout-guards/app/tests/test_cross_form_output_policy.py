"""test_cross_form_output_policy.py — 출력 형식·엔진 정책 검증."""

from __future__ import annotations

import pytest

from auto_write.services.cross_form_output_policy import (
    FillEngine,
    OutputFormat,
    OutputPlan,
    OutputPolicyError,
    validate_output_plan,
)


def _plan(outputs: list[str], engine: str, confirmed: bool = True) -> OutputPlan:
    return OutputPlan.parse(
        output_names=outputs, engine_name=engine, user_confirmed=confirmed
    )


def test_requires_confirm_flag():
    with pytest.raises(OutputPolicyError, match="confirm-output-plan"):
        validate_output_plan(_plan(["docx"], "docx-crossform", confirmed=False))


def test_rhwp_hwpx_requires_hwpx_output():
    with pytest.raises(OutputPolicyError, match="hwpx"):
        validate_output_plan(_plan(["docx"], "rhwp-hwpx-fill"))


def test_rhwp_hwpx_ok():
    validate_output_plan(_plan(["hwpx"], "rhwp-hwpx-fill"))


def test_docx_crossform_cannot_output_hwpx():
    with pytest.raises(OutputPolicyError, match="docx-crossform"):
        validate_output_plan(_plan(["hwpx"], "docx-crossform"))


def test_com_hwpx_requires_hwpx_or_hwp():
    with pytest.raises(OutputPolicyError, match="com-hwpx-fill"):
        validate_output_plan(_plan(["docx"], "com-hwpx-fill"))


def test_com_hwpx_ok():
    validate_output_plan(_plan(["hwpx", "hwp"], "com-hwpx-fill"))
