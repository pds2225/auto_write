from __future__ import annotations

from pathlib import Path

from tools.step2_extraction_baseline import ERROR_KO, render_markdown, run_baseline


def _golden(assertions: list[dict]) -> dict:
    return {
        "name": "synthetic-step2-golden",
        "documents": {"D1": {"name": "sample.txt", "date": "2026-08-16"}},
        "assertions": assertions,
    }


def _assertion(**overrides):
    base = {
        "id": "D1-A01",
        "doc": "D1",
        "category": "COMPANY",
        "category_ko": "기업 기본정보",
        "field": "applicant_name",
        "field_ko": "신청자/대표자 성명",
        "value": "홍길동",
        "semantic_state": "ACTUAL",
        "semantic_state_ko": "현재 사실·실적",
        "expected_behavior": "extract_exact",
        "source_location": "synthetic line 1",
    }
    base.update(overrides)
    return base


def test_supported_value_without_locator_is_source_lost_not_full_pass(tmp_path: Path):
    source = tmp_path / "sample.txt"
    original = "대표자: 홍길동\n"
    source.write_text(original, encoding="utf-8")

    report = run_baseline(_golden([_assertion()]), {"D1": source})

    assert report["summary"]["pass"] == 0
    assert report["results"][0]["value_match"] is True
    assert report["results"][0]["status"] == "SOURCE_LOST"
    assert source.read_text(encoding="utf-8") == original  # read-only contract


def test_missing_structured_extractor_is_reported_not_guessed(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("아이템명: 테스트 수출 SaaS\n", encoding="utf-8")
    assertion = _assertion(
        category="ITEM",
        category_ko="창업아이템/서비스",
        field="item_name",
        field_ko="아이템명",
        value="테스트 수출 SaaS",
    )

    report = run_baseline(_golden([assertion]), {"D1": source})
    row = report["results"][0]

    assert row["raw_presence"] == "FOUND"
    assert row["status"] == "STRUCTURED_EXTRACTION_MISSING"
    assert row["structured_value"] is None


def test_raw_ingest_miss_is_distinguished_from_structured_gap(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("아이템명: 다른 값\n", encoding="utf-8")
    assertion = _assertion(
        category="ITEM",
        category_ko="창업아이템/서비스",
        field="item_name",
        field_ko="아이템명",
        value="기대 아이템",
    )

    report = run_baseline(_golden([assertion]), {"D1": source})

    assert report["results"][0]["status"] == "READ_MISS"


def test_missing_file_is_fatal_measurement_state():
    report = run_baseline(_golden([_assertion()]), {"D1": None})

    assert report["documents"]["D1"]["status"] == "FILE_MISSING"
    assert report["results"][0]["status"] == "FILE_MISSING"


def test_markdown_explains_codes_in_korean(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("아이템명: 테스트 수출 SaaS\n", encoding="utf-8")
    assertion = _assertion(
        category="ITEM",
        category_ko="창업아이템/서비스",
        field="item_name",
        field_ko="아이템명",
        value="테스트 수출 SaaS",
    )
    report = run_baseline(_golden([assertion]), {"D1": source})

    markdown = render_markdown(report)

    code = "STRUCTURED_EXTRACTION_MISSING"
    assert code in markdown
    assert ERROR_KO[code] in markdown
    assert "창업아이템/서비스" in markdown
