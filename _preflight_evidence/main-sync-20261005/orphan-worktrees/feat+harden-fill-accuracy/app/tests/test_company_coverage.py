"""P3 슬라이스2 테스트 — ②필요정보 역설계(company_extract.coverage).

이 기업 마스터로 양식의 사실 칸을 얼마나 채울 수 있는지 대조:
- fillable(값 있음)·conflict(마스터 충돌)·missing_in_master(양식 요구·마스터 없음)·unmapped(기업필드 아님)
- coverage_pct = fillable / mappable
- 동의어 라벨 정규화(신청기업명→기업명), 같은 필드 중복 라벨 1회 집계
- CLI --coverage: 실제 양식(DOCX) 대조 → coverage.json 생성 E2E
"""

from __future__ import annotations

from pathlib import Path

from docx import Document

from auto_write.services import company_extract as ce


def _master() -> ce.CompanyMaster:
    return ce.merge_company([
        ("new.txt", {
            "기업명": {"value": "밸류업파트너스", "raw_label": "기업명"},
            "대표자": {"value": "박다솜", "raw_label": "대표자"},
            "사업자등록번호": {"value": "123-45-67890", "raw_label": "사업자등록번호"},
        }),
        ("old.txt", {  # 사업자번호 불일치 → conflict
            "사업자등록번호": {"value": "999-99-99999", "raw_label": "사업자등록번호"},
        }),
    ])


def test_coverage_buckets_and_percentage() -> None:
    labels = ["신청기업명", "대표자", "사업자등록번호", "연락처", "사업 개요 및 필요성"]
    cov = ce.coverage(_master(), labels)
    by = {f["field"]: f for f in cov["fillable"]}
    assert set(by) == {"기업명", "대표자"}              # 값 있고 충돌 아님
    assert by["기업명"]["value"] == "밸류업파트너스"
    assert [c["field"] for c in cov["conflict"]] == ["사업자등록번호"]  # 마스터 충돌
    assert [m["field"] for m in cov["missing_in_master"]] == ["연락처"]  # 양식 요구·마스터 없음
    assert cov["unmapped"] == ["사업 개요 및 필요성"]    # 기업 정체성 필드 아님
    assert cov["counts"]["mappable"] == 4               # 사업개요는 mappable 제외
    assert cov["coverage_pct"] == 50.0                  # 2/4


def test_duplicate_field_label_counted_once() -> None:
    cov = ce.coverage(_master(), ["기업명", "회사명", "상호"])  # 전부 기업명 클러스터
    assert cov["counts"]["fillable"] == 1               # 중복 라벨 1회만
    assert cov["counts"]["mappable"] == 1


def test_coverage_accepts_dict_master() -> None:
    import json
    d = json.loads(ce.master_to_json(_master()))
    cov = ce.coverage(d, ["기업명"])                    # dict 입력도 지원
    assert cov["counts"]["fillable"] == 1


def test_empty_form_zero_coverage() -> None:
    cov = ce.coverage(_master(), [])
    assert cov["coverage_pct"] == 0.0
    assert cov["counts"]["mappable"] == 0


def test_cli_coverage_e2e(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import company_master as cli
    import json

    # 소스 문서(기업 자료) 2개 — .txt
    (tmp_path / "회사소개.txt").write_text(
        "기업명: 밸류업파트너스\n대표자: 박다솜\n사업자등록번호: 123-45-67890\n업종: 경영컨설팅",
        encoding="utf-8",
    )
    # 대조할 빈 양식(DOCX): 신청기업명·대표자·연락처(사실칸) + 사업개요(서술칸)
    form = tmp_path / "지원양식.docx"
    doc = Document()
    tb = doc.add_table(rows=4, cols=2)
    tb.cell(0, 0).text = "신청기업명"; tb.cell(0, 1).text = ""
    tb.cell(1, 0).text = "대표자"; tb.cell(1, 1).text = ""
    tb.cell(2, 0).text = "연락처"; tb.cell(2, 1).text = ""
    tb.cell(3, 0).text = "사업 개요 및 추진 필요성을 서술하시오"; tb.cell(3, 1).text = ""
    doc.save(form)

    out = tmp_path / "company_master.json"
    rc = cli.main([str(tmp_path / "회사소개.txt"), "-o", str(out),
                   "--no-partials", "--coverage", str(form)])
    assert rc == 0
    cov_path = tmp_path / "coverage.json"
    assert cov_path.exists()
    cov = json.loads(cov_path.read_text(encoding="utf-8"))
    filled = {f["field"] for f in cov["fillable"]}
    assert "기업명" in filled and "대표자" in filled     # 마스터로 채울 수 있음
    missing = {m["field"] for m in cov["missing_in_master"]}
    assert "연락처" in missing                            # 양식 요구·마스터 없음
