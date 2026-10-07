# test_l151_no_posix_backup_path.py — L151 mechanized guard
"""L151: Windows Python에서 POSIX 경로(/tmp)를 백업 위치로 사용하지 않는다.

백업 경로 생성 코드가 POSIX 경로(/tmp, /var 등)를 사용하지 않음을 검증하는 회귀테스트.
"""
from __future__ import annotations

import pytest


class TestL151NoPosixBackupPath:
    def test_no_posix_tmp_in_backup_code(self):
        """백업 관련 코드에 POSIX /tmp 경로가 하드코딩되어 있지 않아야 한다."""
        import auto_write.services.doc_quality_ops as mod
        source = open(mod.__file__, "r", encoding="utf-8").read()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # /tmp 또는 /var/tmp 경로 사용 금지
            assert '"/tmp' not in stripped and "'/tmp" not in stripped, (
                f"L151 위반: doc_quality_ops.py:{i}에 POSIX /tmp 경로: {stripped[:80]}"
            )

    def test_no_posix_tmp_in_orchestrator(self):
        """orchestrator 코드에 POSIX /tmp 경로가 하드코딩되어 있지 않아야 한다."""
        import auto_write.services.document_quality_orchestrator as mod
        source = open(mod.__file__, "r", encoding="utf-8").read()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert '"/tmp' not in stripped and "'/tmp" not in stripped, (
                f"L151 위반: orchestrator.py:{i}에 POSIX /tmp 경로: {stripped[:80]}"
            )

    def test_no_posix_tmp_in_backup_rollback(self):
        """백업/롤백 코드에 POSIX /tmp 경로가 하드코딩되어 있지 않아야 한다."""
        try:
            import auto_write.services.backup_rollback as mod
        except ImportError:
            pytest.skip("backup_rollback 모듈 없음")
        source = open(mod.__file__, "r", encoding="utf-8").read()
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert '"/tmp' not in stripped and "'/tmp" not in stripped, (
                f"L151 위반: backup_rollback.py:{i}에 POSIX /tmp 경로: {stripped[:80]}"
            )
