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


def test_backup_existing_output_stays_beside_target(tmp_path):
    """백업은 산출물과 같은 폴더에 둔다 — POSIX /tmp 하드코딩이 아니다."""
    from pathlib import Path

    from auto_write.services.usage_acceptance import backup_existing_output

    target = tmp_path / "out.docx"
    target.write_text("이전 산출물", encoding="utf-8")
    bak = Path(backup_existing_output(target))
    assert bak.parent == tmp_path
    assert bak.name.startswith("out_prev") and bak.suffix == ".docx"
    assert bak.exists() and not target.exists()
    assert bak.read_text(encoding="utf-8") == "이전 산출물"


def test_orchestrator_backup_under_results_backup(tmp_path):
    """품질 하네스 원본 백업은 results/backup/<ts>/ 이다."""
    from docx import Document

    from auto_write.services.document_quality_orchestrator import (
        DocumentQualityOrchestrator,
    )

    src = tmp_path / "in.docx"
    Document().save(str(src))
    results = tmp_path / "results"
    orch = DocumentQualityOrchestrator(results)
    assert orch.backup_root == results / "backup"
    bak_dir = orch.backup_original(src)
    assert bak_dir.parent == orch.backup_root
    assert (bak_dir / src.name).is_file()
