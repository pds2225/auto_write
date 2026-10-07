"""test_pure_submission_regression_check.py — 제출 패키지 회귀 점검 안전망.

'직전에 확정한 제출본'과 '지금 만든 제출본'을 대조해, 페이지가 줄었는지·본문이
과하게 지워졌는지·서명 이미지가 빠졌는지를 자동으로 잡는 점검기다(L075/L077).
실제 PDF 를 열지 않고 주입점(``open_pdf``·``pdf_text``·``pdf_image_count``)에 가짜를
넣어 판정 로직만 검증한다 — PyMuPDF·실 제출본 미사용. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- 사양 문자열 파싱은 망가진 항목을 조용히 버린다(전체 점검이 죽지 않게).
- 값 대조는 **공백 무시** — 한글 문서의 자간 벌림('박 다 솜')에 속지 않는다.
- 확정판 대비 본문이 70% 미만으로 줄면 '안내문구 과삭제' 회귀로 본다.
- 파일이 없으면 조용히 통과하지 않고 반드시 회귀 1건으로 센다(fail-closed).
"""

from __future__ import annotations

import os

import pytest

from auto_write.services.submission_regression_check import (
    CheckResult,
    compare_to_baseline,
    find_pdf,
    parse_pages_spec,
    parse_text_spec,
    run_checks,
    text_has_value,
)


# --- 가짜 PDF (PyMuPDF 대체) --------------------------------------------------

class _FakePage:
    def __init__(self, text: str = "", images: int = 0, bold: int = 0):
        self._text, self._images, self._bold = text, images, bold

    def get_text(self, kind: str | None = None):
        if kind == "dict":
            spans = [{"flags": 2 ** 4} for _ in range(self._bold)]
            return {"blocks": [{"lines": [{"spans": spans}]}]}
        return self._text

    def get_images(self, full: bool = False):
        return [("img",)] * self._images


def _doc(*pages: _FakePage) -> list:
    return list(pages)


def _touch(directory, *names: str):
    for n in names:
        (directory / n).write_bytes(b"")
    return directory


# --- CheckResult -------------------------------------------------------------

def test_check_result_counts_only_failures():
    r = CheckResult()
    r.check(True, "통과 항목")
    r.check(False, "실패 항목", "이유")
    assert r.fails == 1
    assert "[OK] 통과 항목" in r.lines[0]
    assert "[!! 회귀] 실패 항목 — 이유" in r.lines[1]


def test_check_detail_is_optional():
    r = CheckResult()
    r.check(True, "라벨")
    assert r.lines[0].strip() == "[OK] 라벨"


# --- 사양 문자열 파싱 ---------------------------------------------------------

def test_parse_pages_spec_reads_pairs():
    assert parse_pages_spec("신청서=2,계획서=5") == [("신청서", 2), ("계획서", 5)]


def test_parse_pages_spec_drops_broken_items():
    # '=' 없는 항목·빈 키·빈 값은 조용히 버린다(점검 전체가 죽지 않게).
    assert parse_pages_spec("신청서,=3,계획서=,,") == []
    assert parse_pages_spec("") == []


def test_parse_pages_spec_rejects_non_numeric_page_count():
    # 쪽수 자리에 숫자가 아닌 값이 오면 사양 오류로 즉시 알린다(조용한 오판 금지).
    with pytest.raises(ValueError):
        parse_pages_spec("신청서=두쪽")


def test_parse_text_spec_splits_values_by_pipe():
    assert parse_text_spec("신청서:박다솜|010,계획서:매출") == [
        ("신청서", ["박다솜", "010"]),
        ("계획서", ["매출"]),
    ]


def test_parse_text_spec_keeps_key_with_no_values():
    assert parse_text_spec("신청서:") == [("신청서", [])]


def test_parse_text_spec_drops_entry_without_key():
    assert parse_text_spec(":값") == []
    assert parse_text_spec("") == []


# --- text_has_value ----------------------------------------------------------

def test_text_match_ignores_spaces():
    # 한글 문서에서 흔한 자간 벌림('박 다 솜')을 같은 값으로 본다.
    assert text_has_value("성명: 박 다 솜", "박다솜") is True
    assert text_has_value("성명: 박다솜", "박 다 솜") is True


def test_text_match_returns_false_for_missing_value():
    assert text_has_value("성명: 홍길동", "박다솜") is False


def test_text_match_tolerates_empty_document():
    assert text_has_value("", "박다솜") is False
    assert text_has_value(None, "박다솜") is False  # type: ignore[arg-type]


# --- find_pdf ----------------------------------------------------------------

def test_find_pdf_matches_keyword_in_filename(tmp_path):
    _touch(tmp_path, "01_참여신청서_박다솜.pdf", "02_사업계획서.pdf")
    got = find_pdf(str(tmp_path), "참여신청서")
    assert got is not None and got.endswith("01_참여신청서_박다솜.pdf")


def test_find_pdf_returns_none_when_absent(tmp_path):
    _touch(tmp_path, "02_사업계획서.pdf")
    assert find_pdf(str(tmp_path), "참여신청서") is None


def test_find_pdf_ignores_non_pdf_files(tmp_path):
    _touch(tmp_path, "참여신청서.hwpx", "참여신청서.docx")
    assert find_pdf(str(tmp_path), "참여신청서") is None


# --- run_checks: 페이지·이미지·텍스트 ----------------------------------------

def test_page_count_match_and_mismatch(tmp_path):
    _touch(tmp_path, "신청서.pdf")
    docs = {"신청서.pdf": _doc(_FakePage(), _FakePage())}
    open_pdf = lambda path: docs[os.path.basename(path)]  # noqa: E731

    assert run_checks(directory=str(tmp_path), pages="신청서=2", open_pdf=open_pdf).fails == 0
    assert run_checks(directory=str(tmp_path), pages="신청서=5", open_pdf=open_pdf).fails == 1


def test_missing_file_is_a_failure_not_a_silent_pass(tmp_path):
    res = run_checks(directory=str(tmp_path), pages="없는서류=1", open_pdf=lambda p: _doc())
    assert res.fails == 1
    assert "PDF 없음" in res.lines[0]


def test_required_signature_image(tmp_path):
    _touch(tmp_path, "신청서.pdf")
    with_sig = run_checks(directory=str(tmp_path), require_image="신청서",
                          pdf_image_count=lambda p: 1)
    without = run_checks(directory=str(tmp_path), require_image="신청서",
                         pdf_image_count=lambda p: 0)
    assert with_sig.fails == 0 and without.fails == 1


def test_required_and_forbidden_text(tmp_path):
    _touch(tmp_path, "신청서.pdf")
    res = run_checks(
        directory=str(tmp_path),
        require_text="신청서:박다솜|010",
        forbid_text="신청서:작성요령|[확인필요]",
        pdf_text=lambda p: "성명 박 다 솜 / 연락처 010",
    )
    assert res.fails == 0


def test_forbidden_text_found_is_a_regression(tmp_path):
    _touch(tmp_path, "신청서.pdf")
    res = run_checks(directory=str(tmp_path), forbid_text="신청서:[확인필요]",
                     pdf_text=lambda p: "성명 [확인필요]")
    assert res.fails == 1
    assert "금지값" in res.lines[0]


def test_required_text_missing_is_a_regression(tmp_path):
    _touch(tmp_path, "신청서.pdf")
    res = run_checks(directory=str(tmp_path), require_text="신청서:박다솜",
                     pdf_text=lambda p: "성명 홍길동")
    assert res.fails == 1
    assert "필수값" in res.lines[0]


def test_zip_entry_count(tmp_path):
    import zipfile

    zp = tmp_path / "제출묶음.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("a.pdf", b"")
        z.writestr("b.pdf", b"")
    assert run_checks(directory=str(tmp_path), zips="제출묶음=2").fails == 0
    assert run_checks(directory=str(tmp_path), zips="제출묶음=3").fails == 1
    assert run_checks(directory=str(tmp_path), zips="없는묶음=1").fails == 1


# --- compare_to_baseline: 직전 확정판 대비 이월 -------------------------------

@pytest.fixture
def baseline_dirs(tmp_path):
    cur = tmp_path / "current"
    base = tmp_path / "baseline"
    cur.mkdir()
    base.mkdir()
    _touch(cur, "신청서.pdf")
    _touch(base, "신청서.pdf")
    return cur, base


def _is_baseline(path) -> bool:
    """확정판 쪽 경로인가 — pytest 임시폴더 이름에 'baseline' 이 섞여도 안전하게
    '바로 위 폴더 이름'으로만 판별한다."""
    return os.path.basename(os.path.dirname(str(path))) == "baseline"


def _opener(cur_doc, base_doc):
    def _open(path: str):
        return base_doc if _is_baseline(path) else cur_doc
    return _open


def _side(cur_value, base_value):
    """현재본/확정본에 서로 다른 값을 주는 주입 함수."""
    return lambda path: base_value if _is_baseline(path) else cur_value


def test_baseline_identical_output_has_no_regression(baseline_dirs):
    cur, base = baseline_dirs
    page = _FakePage("본문" * 50, images=1, bold=4)
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(page), _doc(page)),
    )
    assert res.fails == 0


def test_baseline_detects_lost_page(baseline_dirs):
    cur, base = baseline_dirs
    body = _FakePage("본문" * 50)
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(body), _doc(body, body)),
        pdf_text=_side("본문" * 50, "본문" * 50),      # 쪽수만 다르게
        pdf_image_count=_side(0, 0), check_bold=False,
    )
    assert res.fails == 1
    assert any("페이지 이월" in ln and "회귀" in ln for ln in res.lines)


def test_baseline_detects_over_deleted_body(baseline_dirs):
    cur, base = baseline_dirs
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(_FakePage()), _doc(_FakePage())),
        pdf_text=_side("짧음", "본문" * 100),
        pdf_image_count=_side(0, 0), check_bold=False,
    )
    assert res.fails == 1
    assert any("본문량 이월" in ln and "회귀" in ln for ln in res.lines)


def test_baseline_allows_small_body_shrink(baseline_dirs):
    # 70% 이상 남아 있으면 정상적인 안내문구 정리로 본다.
    cur, base = baseline_dirs
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(_FakePage()), _doc(_FakePage())),
        pdf_text=_side("가" * 80, "가" * 100),
        pdf_image_count=_side(0, 0), check_bold=False,
    )
    assert res.fails == 0


def test_baseline_detects_missing_signature_image(baseline_dirs):
    cur, base = baseline_dirs
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(_FakePage("본문")), _doc(_FakePage("본문"))),
        pdf_text=_side("본문", "본문"),
        pdf_image_count=_side(0, 1), check_bold=False,
    )
    assert res.fails == 1
    assert any("이미지 수 이월" in ln and "회귀" in ln for ln in res.lines)


def test_baseline_allows_extra_image(baseline_dirs):
    # 확정판보다 이미지가 늘어난 것은 회귀가 아니다(최소 동일 수만 요구).
    cur, base = baseline_dirs
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(_FakePage("본문")), _doc(_FakePage("본문"))),
        pdf_text=_side("본문", "본문"),
        pdf_image_count=_side(2, 1), check_bold=False,
    )
    assert res.fails == 0


def test_baseline_detects_lost_bold_hierarchy(baseline_dirs):
    cur, base = baseline_dirs
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(_FakePage("본문", bold=0)), _doc(_FakePage("본문", bold=10))),
        pdf_text=_side("본문", "본문"), pdf_image_count=_side(0, 0),
    )
    assert res.fails == 1
    assert any("볼드 스팬 이월" in ln and "회귀" in ln for ln in res.lines)


def test_baseline_allows_half_of_previous_bold(baseline_dirs):
    # 폰트 위계가 절반 이상 남아 있으면 통과(과민 판정 방지).
    cur, base = baseline_dirs
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(_FakePage("본문", bold=5)), _doc(_FakePage("본문", bold=10))),
        pdf_text=_side("본문", "본문"), pdf_image_count=_side(0, 0),
    )
    assert res.fails == 0


def test_baseline_missing_confirmed_file_is_reported(baseline_dirs):
    cur, base = baseline_dirs
    (base / "신청서.pdf").unlink()
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서",
        open_pdf=_opener(_doc(_FakePage()), _doc(_FakePage())),
    )
    assert res.fails == 1
    assert "baseline PDF 없음" in res.lines[0]


def test_baseline_without_any_pdf_reports_nothing_to_compare(tmp_path):
    cur = tmp_path / "current"
    base = tmp_path / "baseline"
    cur.mkdir()
    base.mkdir()
    res = compare_to_baseline(current_dir=str(cur), baseline_dir=str(base))
    assert res.fails == 1
    assert "현재 폴더에 PDF 없음" in res.lines[0]


def test_baseline_keys_are_deduplicated(baseline_dirs):
    cur, base = baseline_dirs
    page = _FakePage("본문", images=0, bold=0)
    res = compare_to_baseline(
        current_dir=str(cur), baseline_dir=str(base), keys="신청서,신청서",
        open_pdf=_opener(_doc(page), _doc(page)),
    )
    # 같은 서류를 두 번 적어도 한 번만 대조한다(중복 보고 방지).
    assert sum(1 for ln in res.lines if "페이지 이월" in ln) == 1
