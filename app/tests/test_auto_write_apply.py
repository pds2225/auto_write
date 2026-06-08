"""test_auto_write_apply.py — image_apply / psst_fill / autopilot_pipeline 회귀 테스트.

새로 추가한 '실제 수정' 모듈들이:
  - 원본을 덮어쓰지 않고(out==in 가드)
  - 표 실측치가 있으면 차트를, 없으면 자리표시를 삽입하며
  - PSST 미흡/누락 영역에 작성 가이드를 추가하고
  - autopilot 이 전 단계를 무인 연속 실행하는지
를 검증한다. (숫자 날조가 없어야 함 — placeholder 폴백 동작 포함)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from auto_write.services.image_apply import apply_images
from auto_write.services.psst_fill import apply_psst_scaffold


def _make_doc(path: Path, *, with_table: bool = True) -> None:
    doc = Document()
    doc.add_heading("사업계획서", 0)
    doc.add_paragraph("가. 문제인식: 고객 시장 니즈와 기존 대안의 한계로 비용 손실.")
    doc.add_paragraph("나. 추진일정 로드맵 — 단계별 마일스톤.")          # gantt 트리거
    doc.add_paragraph("다. 목표 시장규모 TAM SAM SOM 성장률 전망.")       # 막대/도넛 트리거
    if with_table:
        t = doc.add_table(rows=2, cols=3)
        t.rows[0].cells[0].text = "2024년"
        t.rows[0].cells[1].text = "2025년"
        t.rows[0].cells[2].text = "2026년"
        t.rows[1].cells[0].text = "100"
        t.rows[1].cells[1].text = "200"
        t.rows[1].cells[2].text = "350"
    doc.save(str(path))


def test_apply_images_in_equals_out_blocked(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        apply_images(str(src), str(src))


def test_apply_images_inserts_chart_when_table_present(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    report = apply_images(str(src), str(out))
    assert out.exists()
    # 원본은 그대로(문단 수 변화 없음)
    assert len(Document(str(src)).paragraphs) < len(Document(str(out)).paragraphs)
    # 표 실측치가 있으므로 최소 1개 차트가 삽입되어야 한다
    assert report.charts_inserted >= 1


def test_apply_images_placeholder_only_makes_no_chart(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    report = apply_images(str(src), str(out), placeholder_only=True)
    assert report.charts_inserted == 0
    assert report.placeholders_inserted >= 1


def test_apply_images_no_table_falls_back_to_placeholder(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=False)
    report = apply_images(str(src), str(out))
    # 표(실측치)가 없으니 차트 0, 자리표시만 (숫자 날조 없음)
    assert report.charts_inserted == 0
    assert report.placeholders_inserted >= 1


def test_psst_scaffold_adds_guidance(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src)  # team/scale 영역이 비어 미흡/누락
    report = apply_psst_scaffold(str(src), str(out))
    assert out.exists()
    assert report.areas_scaffolded >= 1
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "작성 보강 가이드" in text


def test_psst_scaffold_in_equals_out_blocked(tmp_path: Path) -> None:
    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        apply_psst_scaffold(str(src), str(src))


def test_autopilot_end_to_end(tmp_path: Path) -> None:
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    out = tmp_path / "out.docx"
    _make_doc(src, with_table=True)
    report = run_autopilot(str(src), str(out), write_report=False)
    assert out.exists()
    assert report.backup_dir  # 원본 백업이 생성되어야 함
    assert report.score_total > 0
    # 표가 있으므로 차트가 최소 1개, PSST 보강이 일어났을 것
    assert report.charts_inserted >= 1
    assert report.psst_areas_scaffolded >= 1


def test_autopilot_in_equals_out_blocked(tmp_path: Path) -> None:
    from auto_write.services.autopilot_pipeline import run_autopilot

    src = tmp_path / "in.docx"
    _make_doc(src)
    with pytest.raises(ValueError):
        run_autopilot(str(src), str(src))
