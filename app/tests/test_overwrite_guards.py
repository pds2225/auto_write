"""test_overwrite_guards.py — 무경고 덮어쓰기 방지 회귀 (재발방지 2-F).

hwp_docx_convert._resolve_paths 와 DocumentQualityOrchestrator.run 이 기존 출력
파일(사용자가 수정했을 수 있는 이전 결과·_DRAFT)을 무경고로 덮어쓰지 않고,
usage_acceptance.backup_existing_output 단일출처로 타임스탬프 백업하는지 고정한다.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document as Docx

from auto_write.services.document_quality_orchestrator import (
    DocumentQualityOrchestrator,
)
from auto_write.services.hwp_docx_convert import _resolve_paths


def _mini_docx(path: Path) -> None:
    d = Docx()
    d.add_paragraph("사업 개요와 추진 계획을 기술한다.")
    d.save(str(path))


def test_resolve_paths_backs_up_existing_output(tmp_path: Path):
    """출력 경로에 기존 파일이 있으면 타임스탬프 백업 후 (src, dst, 백업경로)를 돌려준다."""
    src = tmp_path / "in.hwpx"
    src.write_bytes(b"PK\x03\x04fake")  # 존재만 하면 됨
    dst = tmp_path / "out.docx"
    dst.write_text("사용자가 수정한 이전 결과", encoding="utf-8")

    s, d, backup = _resolve_paths(src, dst, ".docx")
    assert s == src and d == dst
    assert backup, "기존 출력 백업 경로가 비어 있음"
    assert not dst.exists(), "기존 파일이 백업으로 이동되지 않음(무경고 덮어쓰기 위험)"
    assert Path(backup).read_text(encoding="utf-8") == "사용자가 수정한 이전 결과"


def test_resolve_paths_no_backup_when_absent(tmp_path: Path):
    """출력 파일이 없으면 백업하지 않고 빈 문자열을 돌려준다(불필요 백업 금지)."""
    src = tmp_path / "in.hwpx"
    src.write_bytes(b"x")
    dst = tmp_path / "new_out.docx"  # 존재 안 함
    s, d, backup = _resolve_paths(src, dst, ".docx")
    assert backup == ""
    assert not dst.exists()


def test_orchestrator_run_backs_up_existing_output(tmp_path: Path):
    """run(output_docx=기존파일)은 저장 직전 기존 결과를 _prev 로 백업한다."""
    src = tmp_path / "in.docx"
    _mini_docx(src)
    out = tmp_path / "fixed.docx"
    _mini_docx(out)  # 사용자가 이미 갖고 있던 이전 결과 모사

    orch = DocumentQualityOrchestrator(tmp_path / "results")
    orch.run(src, out)

    assert list(tmp_path.glob("fixed_prev*.docx")), "기존 출력이 백업되지 않음"
    assert out.exists()  # 새 결과가 out 에 저장됨
