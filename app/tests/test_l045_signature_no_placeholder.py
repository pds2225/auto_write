# test_l045_signature_no_placeholder.py — L045 mechanized guard
"""L045: 서명란은 실이미지, '(인)' 텍스트 임의추가 금지.

cross_form_autofill.autofill_from_source / hwpx_fill.fill 경로가
리터럴 '(인)' 을 절대 기입하지 않음을 단언하는 회귀테스트.
"""
from __future__ import annotations

import pytest


class TestL045SignatureNoPlaceholder:
    def test_no_in_placeholder_in_cross_form_autofill_source(self):
        """cross_form_autofill 모듈에 '(인)' 리터럴이 하드코딩되어 있지 않아야 한다."""
        from auto_write.services import cross_form_autofill as mod
        source = open(mod.__file__, "r", encoding="utf-8").read()
        lines = source.split("\n")
        in_docstring = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if '"""' in stripped:
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            assert '(인)' not in stripped, (
                f"L045 위반: cross_form_autofill.py:{i}에 '(인)' 리터럴 존재: {stripped[:80]}"
            )

    def test_no_in_placeholder_in_hwpx_fill_source(self):
        """hwpx_fill 모듈에 '(인)' 리터럴이 하드코딩되어 있지 않아야 한다."""
        from auto_write.services import hwpx_fill as mod
        source = open(mod.__file__, "r", encoding="utf-8").read()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert '(인)' not in stripped, (
                f"L045 위반: hwpx_fill.py:{i}에 '(인)' 리터럴 존재: {stripped[:80]}"
            )

    def test_no_in_placeholder_in_submittable_filler_source(self):
        """submittable_filler 모듈에 '(인)' 리터럴이 하드코딩되어 있지 않아야 한다."""
        from auto_write.services import submittable_filler as mod
        source = open(mod.__file__, "r", encoding="utf-8").read()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert '(인)' not in stripped, (
                f"L045 위반: submittable_filler.py:{i}에 '(인)' 리터럴 존재: {stripped[:80]}"
            )
