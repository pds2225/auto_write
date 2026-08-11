"""test_pure_company_extract.py — 기업정보 자산화(P3) 순수 로직 안전망.

company_extract 는 참고자료 텍스트에서 기업 '정체성' 필드만 화이트리스트로 뽑아
(우선순위 병합·충돌 needs_confirm) company_master 를 만든다. 파일을 여는 함수
(extract_company_from_file/build_company_master)는 건너뛰고, 텍스트→필드 파싱과
병합·표시 로직(전부 순수)만 직접 검증한다. 야간 안전망(2026-07-16).

여기서 고정하는 계약:
- 표 행(' | ' 결합)·본문 '라벨: 값' 라인 모두에서 (라벨,값) 쌍을 뽑는다.
- 값이 그 자체로 필드 라벨이면 폐기(라벨→라벨 오추출 차단), 대표자 칸의
  역할서술(총괄/담당/콤마 등)은 이름이 아니므로 폐기 — 날조0·오매칭<빈칸.
- 값 비교는 공백·하이픈·점 제거 정규화(사업자번호 000-00-00000 == 0000000000).
- 파일 간 값 불일치는 임의 선택 없이 conflict 로 드러낸다(사람 확인).
"""

from __future__ import annotations

import json

from auto_write.services.company_extract import (
    _iter_label_value_pairs,
    _norm_value,
    _valid_value,
    format_korean,
    master_to_json,
    merge_company,
    parse_company_fields,
)


# --- _iter_label_value_pairs ----------------------------------------------------

def test_pairs_from_table_row_even_odd_cells():
    pairs = list(_iter_label_value_pairs("기업명 | 밸류업파트너스 | 대표자 | 박다솜"))
    assert ("기업명", "밸류업파트너스") in pairs
    assert ("대표자", "박다솜") in pairs


def test_pairs_from_colon_lines_including_fullwidth():
    text = "사업자번호: 123-45-67890\n설립일： 2020.01.02\n\n잡담 라인"
    pairs = list(_iter_label_value_pairs(text))
    assert ("사업자번호", "123-45-67890") in pairs
    assert ("설립일", "2020.01.02") in pairs
    assert all(label != "잡담 라인" for label, _ in pairs)


def test_pairs_skip_empty_cells():
    # 라벨이나 값이 빈 표 칸은 쌍으로 인정하지 않는다.
    pairs = list(_iter_label_value_pairs("기업명 |  | 대표자 | 박다솜"))
    assert pairs == [("대표자", "박다솜")]


# --- _valid_value / _norm_value -------------------------------------------------

def test_valid_value_rejects_label_as_value():
    # 값 칸에 다른 필드 라벨이 들어온 경우(라벨→라벨 오염) 폐기.
    assert _valid_value("기업명", "대표자") is False
    assert _valid_value("기업명", "밸류업파트너스") is True


def test_valid_value_rejects_role_description_for_ceo():
    # 실측 버그 재발 방지: 역할서술("기술개발, 특허전략 및 사업화 총괄")은 이름이 아니다.
    assert _valid_value("대표자", "기술개발, 특허전략 및 사업화 총괄") is False
    assert _valid_value("대표자", "매우 긴 이름이라고 우기는 스물한글자짜리문자열입니다") is False
    assert _valid_value("대표자", "박다솜") is True


def test_valid_value_rejects_empty_and_too_long():
    assert _valid_value("주소", "") is False
    assert _valid_value("주소", "x" * 201) is False


def test_norm_value_business_number_variants_equal():
    assert _norm_value("123-45-67890") == _norm_value("123 45 67890") == "1234567890"
    assert _norm_value("2020.01.02") == _norm_value("2020-01-02")


# --- parse_company_fields -------------------------------------------------------

def test_parse_company_fields_synonym_labels_map_to_canon():
    text = (
        "회사명 | 밸류업파트너스 | 대표자명 | 박다솜\n"
        "사업자번호: 123-45-67890\n"
        "창업일: 2020.01.02\n"
    )
    got = parse_company_fields(text)
    # 동의어(회사명→기업명, 대표자명→대표자, 창업일→설립일)가 대표 라벨로 정규화된다.
    assert got["기업명"] == {"value": "밸류업파트너스", "raw_label": "회사명"}
    assert got["대표자"]["value"] == "박다솜"
    assert got["사업자등록번호"]["value"] == "123-45-67890"
    assert got["설립일"]["value"] == "2020.01.02"


def test_parse_company_fields_first_valid_value_wins():
    text = "기업명: 첫번째상사\n기업명: 두번째상사\n"
    assert parse_company_fields(text)["기업명"]["value"] == "첫번째상사"


def test_parse_company_fields_ignores_non_company_labels():
    # 사업명/과제명은 프로젝트 속성 — 기업 마스터 화이트리스트 밖(추출 금지).
    got = parse_company_fields("사업명: AI 문서 자동화\n기업명: 밸류업\n")
    assert "사업명" not in got
    assert set(got) == {"기업명"}


# --- merge_company ---------------------------------------------------------------

def _p(canon: str, value: str, raw: str = "") -> dict:
    return {canon: {"value": value, "raw_label": raw or canon}}


def test_merge_two_files_same_value_is_high_confidence():
    master = merge_company([("a.docx", _p("기업명", "밸류업")), ("b.hwp", _p("기업명", "밸류업"))])
    fv = master.fields["기업명"]
    assert fv["confidence"] == "high" and fv["confirmed"] is False
    assert master.company_key == "밸류업"          # 기업명 값이 곧 company_key
    assert master.conflicts == []


def test_merge_single_file_is_medium_confidence():
    master = merge_company([("a.docx", _p("기업명", "밸류업"))])
    assert master.fields["기업명"]["confidence"] == "medium"


def test_merge_normalized_equal_values_do_not_conflict():
    # 표기만 다른 같은 사업자번호(하이픈 유무)는 충돌이 아니라 high 일치.
    master = merge_company([
        ("a.docx", _p("사업자등록번호", "123-45-67890")),
        ("b.hwp", _p("사업자등록번호", "1234567890")),
    ])
    assert master.fields["사업자등록번호"]["confidence"] == "high"
    assert master.conflicts == []


def test_merge_conflict_keeps_first_value_and_reports():
    # 값 불일치 → 임의 선택 금지: 1순위 값을 tentative 로 두되 conflict 로 드러낸다.
    master = merge_company([
        ("우선.docx", _p("대표자", "박다솜")),
        ("나중.hwp", _p("대표자", "김철수")),
    ])
    fv = master.fields["대표자"]
    assert fv["value"] == "박다솜" and fv["confidence"] == "conflict"
    assert len(master.conflicts) == 1
    cand_values = [c["value"] for c in master.conflicts[0]["candidates"]]
    assert cand_values == ["박다솜", "김철수"]      # 정규화 중복 없이 순서 보존


def test_merge_missing_lists_unseen_canon_fields():
    master = merge_company([("a.docx", _p("기업명", "밸류업"))])
    assert "기업명" not in master.missing
    assert "사업자등록번호" in master.missing and "대표자" in master.missing


def test_merge_empty_partials_yields_unknown_key():
    master = merge_company([("a.docx", {})])
    assert master.company_key == "unknown"
    assert master.fields == {} and master.conflicts == []


# --- 표시/직렬화 ------------------------------------------------------------------

def test_master_to_json_roundtrip_keeps_hangul():
    master = merge_company([("a.docx", _p("기업명", "밸류업"))], company_key="밸류업")
    data = json.loads(master_to_json(master))
    assert data["company_key"] == "밸류업"
    assert "밸류업" in master_to_json(master)       # ensure_ascii=False — 한글 그대로


def test_format_korean_marks_conflicts_and_missing():
    master = merge_company([
        ("우선.docx", _p("대표자", "박다솜")),
        ("나중.hwp", _p("대표자", "김철수")),
    ])
    text = format_korean(master)
    assert "⚠충돌" in text and "충돌 1건" in text
    assert "미확보(빈칸):" in text and "기업명" in text
