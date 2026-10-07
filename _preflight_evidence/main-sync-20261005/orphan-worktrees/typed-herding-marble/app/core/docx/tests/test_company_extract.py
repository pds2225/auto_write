"""P3 테스트 — 기업정보 자산화(company_extract).

- 파서: 동의어 라벨 정규화·숫자 사실값 보존·대표자 역할서술 가드·값=라벨 폐기.
- 병합: 일치→high(2파일)/medium(1파일), 불일치→conflict+candidates, missing 표기.
- E2E: 실제 파일(.txt) 여러 개 → company_master(충돌 검출).
- 날조0: 없는 필드는 만들지 않고 missing.
"""

from __future__ import annotations

from pathlib import Path

from auto_write.services import company_extract as ce


# --- 파서 --------------------------------------------------------------------

def test_synonym_labels_and_numeric_values_preserved() -> None:
    text = (
        "신청기업명 | 밸류업파트너스 | 대표자 | 박다솜\n"
        "사업자등록번호: 123-45-67890\n"
        "자본금 : 5,000만원\n"
        "상시근로자수 | 12명"
    )
    p = ce.parse_company_fields(text)
    assert p["기업명"]["value"] == "밸류업파트너스"        # 신청기업명→기업명 정규화
    assert p["대표자"]["value"] == "박다솜"
    assert p["사업자등록번호"]["value"] == "123-45-67890"  # 숫자 사실값 보존
    assert p["자본금"]["value"] == "5,000만원"
    assert p["직원수"]["value"] == "12명"                   # 상시근로자수→직원수


def test_representative_role_description_rejected() -> None:
    # '대표자 : 기술개발, 사업화 총괄' 같은 역할서술은 이름칸에 넣지 않는다.
    text = "대표자 : 기술개발, 특허전략 및 사업화 총괄"
    p = ce.parse_company_fields(text)
    assert "대표자" not in p


def test_value_that_is_a_label_is_dropped() -> None:
    text = "기업명 | 대표자"  # 값 셀이 '대표자'(라벨) → 폐기
    p = ce.parse_company_fields(text)
    assert "기업명" not in p


def test_missing_fields_not_fabricated() -> None:
    master = ce.merge_company([("a.txt", {"기업명": {"value": "A사", "raw_label": "기업명"}})])
    assert "사업자등록번호" in master.missing   # 없는 필드는 missing(날조 0)
    assert "사업자등록번호" not in master.fields


# --- 병합·충돌 ---------------------------------------------------------------

def _pf(value: str, label: str = "기업명") -> dict:
    return {"value": value, "raw_label": label}


def test_agreeing_two_files_high_confidence() -> None:
    master = ce.merge_company([
        ("a.txt", {"기업명": _pf("밸류업파트너스")}),
        ("b.txt", {"기업명": _pf("밸류업파트너스")}),
    ])
    assert master.fields["기업명"]["confidence"] == "high"
    assert len(master.fields["기업명"]["sources"]) == 2
    assert master.conflicts == []


def test_single_file_medium_confidence() -> None:
    master = ce.merge_company([("a.txt", {"기업명": _pf("밸류업파트너스")})])
    assert master.fields["기업명"]["confidence"] == "medium"


def test_disagreeing_values_become_conflict() -> None:
    master = ce.merge_company([
        ("new.txt", {"사업자등록번호": _pf("111-11-11111", "사업자등록번호")}),
        ("old.txt", {"사업자등록번호": _pf("222-22-22222", "사업자등록번호")}),
    ])
    assert master.fields["사업자등록번호"]["confidence"] == "conflict"
    assert master.fields["사업자등록번호"]["confirmed"] is False
    assert master.fields["사업자등록번호"]["value"] == "111-11-11111"  # 우선순위 1위 tentative
    conf = [c for c in master.conflicts if c["field"] == "사업자등록번호"]
    assert len(conf) == 1
    assert len(conf[0]["candidates"]) == 2


def test_dash_space_normalized_no_false_conflict() -> None:
    # 000-00-00000 == 0000000000 (하이픈·공백 무시) → 충돌 아님
    master = ce.merge_company([
        ("a.txt", {"사업자등록번호": _pf("123-45-67890", "사업자등록번호")}),
        ("b.txt", {"사업자등록번호": _pf("1234567890", "사업자등록번호")}),
    ])
    assert master.fields["사업자등록번호"]["confidence"] == "high"
    assert master.conflicts == []


# --- E2E (실제 파일) ---------------------------------------------------------

def test_build_master_from_files_e2e(tmp_path: Path) -> None:
    (tmp_path / "new.txt").write_text(
        "기업명: 밸류업파트너스\n대표자: 박다솜\n사업자등록번호: 123-45-67890\n"
        "업종: 경영컨설팅\n직원수: 12명",
        encoding="utf-8",
    )
    (tmp_path / "old.txt").write_text(
        "회사명: 밸류업파트너스\n대표자: 박다솜\n자본금: 5000만원",
        encoding="utf-8",
    )
    master, partials, _notes = ce.build_company_master(
        [tmp_path / "new.txt", tmp_path / "old.txt"], company_key="밸류업파트너스",
    )
    assert master.company_key == "밸류업파트너스"
    assert master.fields["기업명"]["confidence"] == "high"        # 두 파일 일치
    assert master.fields["사업자등록번호"]["value"] == "123-45-67890"  # new.txt 만 보유
    assert master.fields["자본금"]["value"] == "5000만원"          # old.txt 만 보유
    assert "홈페이지" in master.missing                            # 둘 다 없음 → missing
    assert len(partials) == 2
    # JSON 직렬화 가능
    import json
    data = json.loads(ce.master_to_json(master))
    assert data["fields"]["기업명"]["confirmed"] is False
