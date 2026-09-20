from __future__ import annotations

import zipfile
from pathlib import Path

from auto_write.services.infographic_suggest import (
    suggest_images_ai_hwpx,
    suggest_images_hwpx,
)
from auto_write.services.psst_check import check_psst_hwpx
from core.docx.services.hwpx_analysis_adapter import read_hwpx_analysis

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _make_hwpx(path: Path) -> None:
    sections = [
        (
            "Contents/section0.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">
  <hp:p><hp:run><hp:t>1. 문제인식 (Problem)</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>고객 시장 문제와 기존 대안 한계, 심각한 비용 30% 증가</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>2. 실현가능성 (Solution)</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>핵심기능 차별성 구현 검증 고객사 적용 시나리오</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:pic id="img1"/></hp:run></hp:p>
</hs:sec>""",
        ),
        (
            "Contents/section1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">
  <hp:p><hp:run><hp:t>3. 성장전략 (Scale-up)</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>시장규모 TAM SAM SOM 성장률, 수익모델, 판로 확대, 매출 KPI 로드맵</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>4. 팀구성 (Team)</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>대표 경력과 팀 구성, 외부 협력 파트너, 수행 경험</hp:t></hp:run></hp:p>
</hs:sec>""",
        ),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        for name, xml in sections:
            archive.writestr(name, xml.encode("utf-8"))


def test_hwpx_analysis_adapter_reads_directly_without_mutation(tmp_path: Path):
    src = tmp_path / "plan.hwpx"
    _make_hwpx(src)
    before = src.read_bytes()

    analysis = read_hwpx_analysis(src)

    assert analysis.section_count == 2
    assert analysis.existing_images == 1
    assert "문제인식" in analysis.text
    assert "시장규모" in analysis.text
    assert src.read_bytes() == before


def test_psst_checker_reuses_logic_for_hwpx(tmp_path: Path):
    src = tmp_path / "plan.hwpx"
    _make_hwpx(src)

    report = check_psst_hwpx(src)

    assert report.applicable
    assert len(report.areas) == 4
    assert all(area.section_present for area in report.areas)
    assert report.overall_ratio >= 0.75


def test_infographic_suggestion_reuses_logic_for_hwpx(tmp_path: Path):
    src = tmp_path / "plan.hwpx"
    _make_hwpx(src)

    report = suggest_images_hwpx(src)
    fallback = suggest_images_ai_hwpx(src, openai_service=None)

    assert report.existing_images == 1
    assert len(report.suggestions) >= 2
    assert any(s.keyword in {"시장규모", "TAM", "로드맵"} for s in report.suggestions)
    assert fallback.as_dict() == report.as_dict()
