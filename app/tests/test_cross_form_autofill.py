"""test_cross_form_autofill.py — cross-form value autofill(v1) 회귀 테스트.

검증 항목:
  ① 정확일치 라벨("기업명") 전사
  ② 동의어 전사("대표자" → "성명")  ← 핵심
  ③ 동의어 전사("사업자등록번호" → "사업자번호")
  ④ 소스에 없는 라벨("사업명")은 미매칭 → 빈칸 유지(날조 0)
  ⑤ 원본 source·target 파일 미수정
  ⑥ out==source / out==target → ValueError
  ⑦ 전사 값이 정확히 소스 값과 동일(날조 없음), 무관 라벨엔 값 안 들어감(보수적)

적대 반례(오매칭 차단):
  ⑧ '사업명' ↛ '사업자명' 자동전사 금지(퍼지 → needs_confirm)
  ⑨ '주소' ↛ '주소지정' 자동전사 금지
  ⑩ 클러스터 충돌(기업명+회사명 → 상호) → needs_confirm·전사 0
  ⑪ 마스킹 값 '○○○'·'OOO-OO-OOOOO' 전사 후 보존(훼손 없음)
  ⑫ 4컬럼 label|value|label|value 행 정확 전사
  ⑬ 추출 오염 없음(값 셀이 라벨로 안 들어감)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from auto_write.services.cross_form_autofill import (
    autofill_from_source,
    extract_source_fields,
    find_target_fields,
    match_fields,
)


def _make_source(path: Path) -> None:
    """소스: 라벨|값 2열 표."""
    doc = Document()
    doc.add_heading("사업계획서", 0)
    t = doc.add_table(rows=3, cols=2)
    t.rows[0].cells[0].text = "기업명"
    t.rows[0].cells[1].text = "밸류업(주)"
    t.rows[1].cells[0].text = "대표자"
    t.rows[1].cells[1].text = "홍길동"
    t.rows[2].cells[0].text = "사업자등록번호"
    t.rows[2].cells[1].text = "123-45-67890"
    doc.save(str(path))


def _make_target(path: Path) -> None:
    """타깃: 라벨|<빈칸> 2열 표 (값칸 비어 있음)."""
    doc = Document()
    doc.add_heading("지원신청서", 0)
    t = doc.add_table(rows=4, cols=2)
    labels = ["기업명", "성명", "사업자번호", "사업명"]
    for i, lab in enumerate(labels):
        t.rows[i].cells[0].text = lab
        t.rows[i].cells[1].text = ""  # 빈 값칸
    doc.save(str(path))


def _value_for(docx_path: Path, label: str) -> str:
    """타깃 문서에서 라벨 행의 값칸 텍스트를 읽는다."""
    doc = Document(str(docx_path))
    for table in doc.tables:
        for row in table.rows:
            cells = row.cells
            if cells and cells[0].text.strip() == label:
                return cells[1].text.strip()
    return ""


# --- 단위: 추출/탐지/매칭 -----------------------------------------------------

def test_extract_source_fields(tmp_path: Path) -> None:
    src = tmp_path / "a.docx"
    _make_source(src)
    fields = extract_source_fields(src)
    assert fields["기업명"] == "밸류업(주)"
    assert fields["대표자"] == "홍길동"
    assert fields["사업자등록번호"] == "123-45-67890"


def test_find_target_fields_only_blank(tmp_path: Path) -> None:
    tgt = tmp_path / "b.docx"
    _make_target(tgt)
    targets = find_target_fields(tgt)
    norms = {t["normalized"] for t in targets}
    assert {"기업명", "성명", "사업자번호", "사업명"} <= norms
    # 값셀 인덱스는 라벨 다음 칸(1)
    assert all(t["value_cell"] == 1 for t in targets)


def test_match_synonym_daepyoja_to_seongmyeong(tmp_path: Path) -> None:
    """동의어 매칭 핵심: 소스 '대표자' → 타깃 '성명'."""
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    _make_source(src)
    _make_target(tgt)
    source = extract_source_fields(src)
    targets = find_target_fields(tgt)
    matches = match_fields(source, targets)
    by_norm = {m.normalized: m for m in matches}
    assert by_norm["성명"].source_label == "대표자"
    assert by_norm["성명"].value == "홍길동"
    assert by_norm["성명"].confidence == "high"
    # 소스에 없는 사업명은 매칭 안 됨
    assert by_norm["사업명"].source_label == ""
    assert by_norm["사업명"].value == ""


# --- end-to-end: 전사 --------------------------------------------------------

def test_autofill_exact_synonym_and_no_fabrication(tmp_path: Path) -> None:
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    _make_source(src)
    _make_target(tgt)

    report = autofill_from_source(src, tgt, out, use_ai=False)
    assert report.ok
    assert out.exists()

    # ① 정확일치 전사
    assert _value_for(out, "기업명") == "밸류업(주)"
    # ② 동의어 전사(핵심): 대표자 → 성명
    assert _value_for(out, "성명") == "홍길동"
    # ③ 동의어 전사: 사업자등록번호 → 사업자번호
    assert _value_for(out, "사업자번호") == "123-45-67890"
    # ④ 소스에 없는 사업명은 미매칭 → 빈칸 유지(날조 0)
    assert _value_for(out, "사업명") == ""

    # 전사 건수 = 3 (기업명/성명/사업자번호)
    assert report.transcribed == 3
    assert {m.normalized for m in report.matches} == {"기업명", "성명", "사업자번호"}
    # 사업명은 unmatched 로 보고
    assert any(u["normalized"] == "사업명" for u in report.unmatched_targets)


def test_autofill_preserves_originals(tmp_path: Path) -> None:
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    _make_source(src)
    _make_target(tgt)
    src_before = src.read_bytes()
    tgt_before = tgt.read_bytes()

    autofill_from_source(src, tgt, out, use_ai=False)

    assert src.read_bytes() == src_before  # 소스 미수정
    assert tgt.read_bytes() == tgt_before  # 타깃 미수정
    # 타깃 값칸은 여전히 비어 있어야 함(원본 보존)
    assert _value_for(tgt, "성명") == ""


def test_autofill_out_equals_source_or_target_raises(tmp_path: Path) -> None:
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    _make_source(src)
    _make_target(tgt)
    with pytest.raises(ValueError):
        autofill_from_source(src, tgt, src, use_ai=False)
    with pytest.raises(ValueError):
        autofill_from_source(src, tgt, tgt, use_ai=False)


def test_autofill_conservative_no_unrelated_fill(tmp_path: Path) -> None:
    """보수적: 무관한 라벨('주소' 등 소스에 없는 항목)엔 값이 들어가지 않는다."""
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    _make_source(src)
    # 타깃에 소스와 무관한 라벨을 추가
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "기업명"
    t.rows[0].cells[1].text = ""
    t.rows[1].cells[0].text = "추진목표"   # 소스에 없음, 동의어도 아님
    t.rows[1].cells[1].text = ""
    doc.save(str(tgt))

    report = autofill_from_source(src, tgt, out, use_ai=False)
    assert _value_for(out, "기업명") == "밸류업(주)"
    assert _value_for(out, "추진목표") == ""
    assert report.transcribed == 1


# --- 적대 반례: 오매칭 차단 --------------------------------------------------

def test_사업명_does_not_autofill_사업자명(tmp_path: Path) -> None:
    """접미사 다른 합성어: 소스 '사업명'이 타깃 '사업자명'으로 자동전사되면 안 된다.

    퍼지로 후보 제안(needs_confirm)은 가능하나, 전사·confident 0 이어야 한다.
    """
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    t = doc.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "사업명"
    t.rows[0].cells[1].text = "AI 인재실증 사업"
    doc.save(str(src))
    doc2 = Document()
    t2 = doc2.add_table(rows=1, cols=2)
    t2.rows[0].cells[0].text = "사업자명"
    t2.rows[0].cells[1].text = ""
    doc2.save(str(tgt))

    report = autofill_from_source(src, tgt, out, use_ai=False)
    # 자동전사 안 됨 → 빈칸 유지
    assert _value_for(out, "사업자명") == ""
    assert report.transcribed == 0
    assert all(m.normalized != "사업자명" for m in report.matches)
    # 퍼지 후보로 needs_confirm 에 잡혀야 함(제안만)
    assert any(n["normalized"] == "사업자명" for n in report.needs_confirm)


def test_주소_does_not_autofill_주소지정(tmp_path: Path) -> None:
    """소스 '주소'가 타깃 '주소지정'으로 자동전사되면 안 된다(퍼지 → needs_confirm)."""
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    t = doc.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text = "주소"
    t.rows[0].cells[1].text = "서울시 강남구"
    doc.save(str(src))
    doc2 = Document()
    t2 = doc2.add_table(rows=1, cols=2)
    t2.rows[0].cells[0].text = "주소지정"
    t2.rows[0].cells[1].text = ""
    doc2.save(str(tgt))

    report = autofill_from_source(src, tgt, out, use_ai=False)
    assert _value_for(out, "주소지정") == ""
    assert report.transcribed == 0
    assert any(n["normalized"] == "주소지정" for n in report.needs_confirm)


def test_cluster_conflict_goes_to_needs_confirm(tmp_path: Path) -> None:
    """동의어 클러스터 충돌: 소스에 '기업명'+'회사명' 둘 다 → 타깃 '상호'는 전사 보류.

    한 타깃에 같은 클러스터 소스가 복수면 conflict → 전사 0, needs_confirm.
    """
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "기업명"
    t.rows[0].cells[1].text = "밸류업(주)"
    t.rows[1].cells[0].text = "회사명"
    t.rows[1].cells[1].text = "밸류업 주식회사"
    doc.save(str(src))
    doc2 = Document()
    t2 = doc2.add_table(rows=1, cols=2)
    t2.rows[0].cells[0].text = "상호"   # 같은 클러스터(기업명/회사명/상호)
    t2.rows[0].cells[1].text = ""
    doc2.save(str(tgt))

    report = autofill_from_source(src, tgt, out, use_ai=False)
    assert _value_for(out, "상호") == ""
    assert report.transcribed == 0
    conf = next(n for n in report.needs_confirm if n["normalized"] == "상호")
    assert conf["confidence"] == "conflict"
    assert set(conf["candidates"]) == {"기업명", "회사명"}


def test_masked_value_preserved_after_transcribe(tmp_path: Path) -> None:
    """전사값 보존: 마스킹 이름 '○○○'·'OOO-OO-OOOOO' 가 지워지거나 망가지지 않는다."""
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    t = doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "대표자"
    t.rows[0].cells[1].text = "○○○"
    t.rows[1].cells[0].text = "사업자등록번호"
    t.rows[1].cells[1].text = "OOO-OO-OOOOO"
    doc.save(str(src))
    doc2 = Document()
    t2 = doc2.add_table(rows=2, cols=2)
    t2.rows[0].cells[0].text = "성명"          # 동의어(대표자)
    t2.rows[0].cells[1].text = ""
    t2.rows[1].cells[0].text = "사업자등록번호"  # 정확일치
    t2.rows[1].cells[1].text = ""
    doc2.save(str(tgt))

    report = autofill_from_source(src, tgt, out, use_ai=False)
    # 마스킹 값이 원형 그대로 보존(blind-review 규칙 위반 없음)
    assert _value_for(out, "성명") == "○○○"
    assert _value_for(out, "사업자등록번호") == "OOO-OO-OOOOO"
    assert report.transcribed == 2


def test_four_column_label_value_row(tmp_path: Path) -> None:
    """4컬럼 label|value|label|value 행을 정확히 전사한다(짝수 인덱스만 라벨)."""
    src = tmp_path / "a.docx"
    tgt = tmp_path / "b.docx"
    out = tmp_path / "out.docx"
    doc = Document()
    t = doc.add_table(rows=1, cols=4)
    t.rows[0].cells[0].text = "기업명"
    t.rows[0].cells[1].text = "밸류업(주)"
    t.rows[0].cells[2].text = "대표자"
    t.rows[0].cells[3].text = "홍길동"
    doc.save(str(src))
    fields = extract_source_fields(src)
    # 값 셀(밸류업/홍길동)이 라벨로 오염되지 않아야 함
    assert fields["기업명"] == "밸류업(주)"
    assert fields["대표자"] == "홍길동"
    assert "밸류업" not in fields
    assert "홍길동" not in fields

    doc2 = Document()
    t2 = doc2.add_table(rows=1, cols=4)
    t2.rows[0].cells[0].text = "기업명"
    t2.rows[0].cells[1].text = ""
    t2.rows[0].cells[2].text = "성명"   # 동의어(대표자)
    t2.rows[0].cells[3].text = ""
    doc2.save(str(tgt))

    report = autofill_from_source(src, tgt, out, use_ai=False)
    doc_out = Document(str(out))
    row = doc_out.tables[0].rows[0]
    assert row.cells[1].text.strip() == "밸류업(주)"
    assert row.cells[3].text.strip() == "홍길동"
    assert report.transcribed == 2


def test_extract_no_value_cell_pollution(tmp_path: Path) -> None:
    """추출 오염 없음: 값 셀이 라벨 키로 들어가지 않는다(짝수 인덱스만 라벨)."""
    src = tmp_path / "a.docx"
    doc = Document()
    t = doc.add_table(rows=1, cols=3)
    t.rows[0].cells[0].text = "항목"
    t.rows[0].cells[1].text = "연락처"
    t.rows[0].cells[2].text = "010-1234-5678"
    doc.save(str(src))
    fields = extract_source_fields(src)
    # 짝수 인덱스(0,2)만 라벨: (0,1)=항목→연락처. (2,3) 없음.
    # 값 셀 '연락처'(idx1)·'010-…'(idx2의 값 없음)이 라벨로 등록되면 안 됨.
    assert fields.get("항목") == "연락처"
    assert "연락처" not in fields  # 값 셀이 라벨로 오염 안 됨
    assert "010-1234-5678" not in fields
