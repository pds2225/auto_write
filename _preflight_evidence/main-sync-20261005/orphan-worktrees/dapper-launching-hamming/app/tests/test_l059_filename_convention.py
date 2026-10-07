# test_l059_filename_convention.py — L059 mechanized guard
"""L059: 파일명 접미사는 상태만 표기(_DRAFT 등), 작업서술·_converted 등 금지.

제출 파일명에 허용되지 않는 접미사가 포함되어 있지 않음을 검증하는 회귀테스트.
"""
from __future__ import annotations

import pytest


# 금지 접미사 패턴 (작업서술·중간산출물)
_FORBIDDEN_SUFFIXES = (
    "_converted",
    "_고도화",
    "_통합",
    "_노트북LM",
    "_notebooklm",
    "_auto",
    "_draft_backup",
)

# 허용 접미사
_ALLOWED_SUFFIXES = ("_DRAFT", "_DRAFT2")


class TestL059FilenameConvention:
    def test_force_draft_name_uses_only_allowed_suffixes(self):
        """force_draft_name은 허용된 접미사만 사용해야 한다."""
        from auto_write.services.usage_acceptance import force_draft_name
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            test_path = Path(td) / "test.docx"
            test_path.write_bytes(b"test")

            result_path, _reason = force_draft_name(test_path)
            stem = result_path.stem

            # 허용된 접미사만 있어야 함
            has_allowed = any(stem.endswith(s) for s in _ALLOWED_SUFFIXES)
            assert has_allowed, f"허용 접미사 없음: {stem}"

            # 금지 접미사가 없어야 함
            for forbidden in _FORBIDDEN_SUFFIXES:
                assert forbidden not in stem, (
                    f"L059 위반: 금지 접미사 '{forbidden}' 포함: {stem}"
                )

    def test_no_forbidden_suffixes_in_output_naming(self):
        """output_naming 모듈에 금지 접미사가 하드코딩되어 있지 않아야 한다."""
        try:
            from auto_write.services import output_naming as mod
        except ImportError:
            pytest.skip("output_naming 모듈 없음")
        source = open(mod.__file__, "r", encoding="utf-8").read()
        for suffix in _FORBIDDEN_SUFFIXES:
            assert suffix not in source, (
                f"L059 위반: output_naming.py에 금지 접미사 '{suffix}' 존재"
            )
