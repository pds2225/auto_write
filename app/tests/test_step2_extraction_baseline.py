from __future__ import annotations

from pathlib import Path

from tools.step2_extraction_baseline import (
    ERROR_KO,
    render_markdown,
    run_baseline,
)


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


def test_supported_value_without_locator_is_source_lost_but_value_match_is_counted(
    tmp_path: Path,
):
    source = tmp_path / "sample.txt"
    original = "대표자: 홍길동\n"
    source.write_text(original, encoding="utf-8")

    report = run_baseline(_golden([_assertion()]), {"D1": source})

    row = report["results"][0]
    assert row["value_match"] is True
    assert row["status"] == "SOURCE_LOST"
    assert report["summary"]["structured"]["value_match"] == 1
    assert report["summary"]["full_contract_pass"] == 0
    assert source.read_text(encoding="utf-8") == original


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
    assert row["structured_supported"] is False
    assert row["structured_value"] is None
    assert report["summary"]["raw_probe"]["found"] == 1


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
    assert report["summary"]["raw_probe"]["missing"] == 1


def test_complex_expected_uses_explicit_raw_terms_for_table_ingest(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text(
        "바이어 1건 | 100 C | 100,000원\n",
        encoding="utf-8",
    )
    assertion = _assertion(
        category="PRICING",
        category_ko="가격/과금",
        field="buyer_flow_total",
        field_ko="바이어 1건 기준 총 과금",
        value={"credits": 100, "amount_krw": 100000},
        raw_terms=["100 C", "100,000원"],
        expected_behavior="preserve_table_row_pairing",
    )

    report = run_baseline(_golden([assertion]), {"D1": source})
    row = report["results"][0]

    assert row["raw_presence"] == "FOUND"
    assert row["raw_terms"] == ["100 C", "100,000원"]
    assert row["status"] == "STRUCTURED_EXTRACTION_MISSING"


def test_complex_expected_raw_terms_missing_one_is_read_miss(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("바이어 1건 | 100 C\n", encoding="utf-8")
    assertion = _assertion(
        category="PRICING",
        field="buyer_flow_total",
        value={"credits": 100, "amount_krw": 100000},
        raw_terms=["100 C", "100,000원"],
        expected_behavior="preserve_table_row_pairing",
    )

    report = run_baseline(_golden([assertion]), {"D1": source})

    assert report["results"][0]["status"] == "READ_MISS"


def test_partial_hwp_preview_is_not_reported_as_clean_pass(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("placeholder", encoding="utf-8")

    def partial_extractor(_path):
        return (
            "대표자: 홍길동\n",
            ["HWP 미리보기 텍스트(PrvText)만 추출 — 본문 일부가 누락될 수 있음."],
        )

    report = run_baseline(
        _golden([_assertion()]),
        {"D1": source},
        extractor=partial_extractor,
    )

    doc = report["documents"]["D1"]
    assert doc["status"] == "PARTIAL_INGEST"
    assert "일부" in doc["status_ko"]


def test_missing_file_is_fatal_measurement_state():
    report = run_baseline(_golden([_assertion()]), {"D1": None})

    assert report["documents"]["D1"]["status"] == "FILE_MISSING"
    assert report["results"][0]["status"] == "FILE_MISSING"


def test_markdown_explains_codes_and_stage_metrics_in_korean(tmp_path: Path):
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
    assert "원문 단서 검사" in markdown
    assert "구조화 기능 미지원" in markdown


def test_duplicate_assertion_id_is_rejected(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("대표자: 홍길동\n", encoding="utf-8")
    assertion = _assertion()

    try:
        run_baseline(_golden([assertion, assertion]), {"D1": source})
    except ValueError as exc:
        assert "중복" in str(exc)
    else:
        raise AssertionError("duplicate assertion id must be rejected")
