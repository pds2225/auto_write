"""13-3 결함 주입: 의도적 결함 PDF 를 만들어 기술 검사(structural)가 잡는지 확인한다(가짜 데이터).

AI 시각 검사로만 잡히는 항목(체크박스 모양 등)은 visual_qa 테스트가, 직인·체크박스·가림·첨부 누락은
각 모듈 테스트가 담당한다. 여기서는 PDF 단계에서 숫자로 잡히는 결함을 모은다.
"""
from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image

from auto_write.services.submit_finish.pdf_checks import check_pdf_layout
from auto_write.services.submit_finish.status import Status, find_forbidden


def _png(w=300, h=200, color=(200, 0, 0)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "PNG")
    return b.getvalue()


def _pdf(tmp: Path, pages: list[dict]) -> Path:
    doc = fitz.open()
    for spec in pages:
        pg = doc.new_page(width=595, height=842)
        for (x, y, text) in spec.get("texts", []):
            pg.insert_text((x, y), text, fontname="korea", fontsize=11)
        for rect, data in spec.get("images", []):
            pg.insert_image(fitz.Rect(*rect), stream=data, keep_proportion=False)  # 결함 주입: 비율 강제 변경 허용
    path = tmp / "t.pdf"
    doc.save(path)
    return path


def codes(findings):
    return [f.code for f in findings]


BODY = [(60, 100 + 20 * i, f"본문 문장 {i} 가짜 데이터입니다") for i in range(6)]


def test_clean_pdf_passes(tmp_path):
    p = _pdf(tmp_path, [{"texts": BODY, "images": [((100, 300, 190, 360), _png())]}])
    fs = check_pdf_layout(p)
    assert codes(fs) == ["PDF_LAYOUT"] and fs[0].status is Status.PASS


def test_text_cut_off_page(tmp_path):
    p = _pdf(tmp_path, [{"texts": BODY + [(560, 300, "쪽 밖으로 넘치는 아주 긴 글자열입니다")]}])
    assert "PDF_TEXT_OFFPAGE" in codes(check_pdf_layout(p))


def test_seal_position_off_page(tmp_path):
    p = _pdf(tmp_path, [{"texts": BODY, "images": [((540, 300, 640, 366), _png())]}])
    assert "PDF_IMAGE_OFFPAGE" in codes(check_pdf_layout(p))


def test_image_aspect_distortion(tmp_path):
    p = _pdf(tmp_path, [{"texts": BODY, "images": [((100, 300, 300, 330), _png(300, 200))]}])  # 3:2 → 6.7:1
    assert "PDF_IMAGE_DISTORT" in codes(check_pdf_layout(p))


def test_duplicate_seal_overlap(tmp_path):
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    for t in BODY:
        pg.insert_text((t[0], t[1]), t[2], fontname="korea", fontsize=11)
    xref = pg.insert_image(fitz.Rect(100, 300, 190, 360), stream=_png())
    pg.insert_image(fitz.Rect(101, 301, 191, 361), xref=xref)  # 같은 이미지를 거의 같은 자리에 한 번 더
    path = tmp_path / "dup.pdf"
    doc.save(path)
    assert "PDF_IMAGE_DUP" in codes(check_pdf_layout(path))


def test_abnormal_empty_page_and_orphan_heading(tmp_path):
    texts_end = BODY + [(60, 780, "2. 시장 분석")]
    p = _pdf(tmp_path, [{"texts": texts_end}, {}, {"texts": BODY}])
    cs = codes(check_pdf_layout(p))
    assert "PDF_PAGE_EMPTY" in cs and "PDF_ORPHAN_HEADING" in cs


def test_page_order_wrong_and_missing_attachment(tmp_path):
    p = _pdf(tmp_path, [{"texts": [(60, 100, "참가신청서")]}, {"texts": [(60, 100, "개인정보 동의서")]},
                        {"texts": [(60, 100, "주민등록초본")]}])
    ok = check_pdf_layout(p, expected_order=["참가신청서", "개인정보 동의서", "주민등록초본"])
    assert "PDF_ORDER_WRONG" not in codes(ok) and "PDF_ORDER_MISSING" not in codes(ok)
    assert "PDF_ORDER_WRONG" in codes(check_pdf_layout(p, expected_order=["주민등록초본", "참가신청서"]))
    assert "PDF_ORDER_MISSING" in codes(check_pdf_layout(p, expected_order=["참가신청서", "사업자등록증"]))


def test_messages_have_no_forbidden_phrases(tmp_path):
    p = _pdf(tmp_path, [{"texts": BODY + [(560, 300, "넘치는 글자 열 넘치는 글자 열")],
                         "images": [((540, 300, 640, 366), _png())]}])
    for f in check_pdf_layout(p):
        assert not find_forbidden(f.message)
        assert f.source == "structural"


def _pdf_sized(tmp: Path, pages: list[list[tuple]]) -> Path:
    """pages: 쪽마다 [(x, y, text, fontsize), ...]."""
    doc = fitz.open()
    for items in pages:
        pg = doc.new_page(width=595, height=842)
        for x, y, text, size in items:
            pg.insert_text((x, y), text, fontname="korea", fontsize=size)
    out = tmp / "sized.pdf"
    doc.save(str(out))
    return out


def _body(start: int, n: int = 8) -> list[tuple]:
    return [(60, start + 16 * k, f"본문 줄 {k}", 10) for k in range(n)]


def test_unnumbered_title_left_at_page_bottom_is_flagged(tmp_path):
    """실양식 AI 시각검수에서 발견: 번호 없는 큰 제목이 쪽 중간에 홀로 남고 본문은 다음 쪽으로 넘어간 경우."""
    p = _pdf_sized(tmp_path, [_body(80) + [(60, 330, "개인정보 수집 이용 및 제3자 제공 동의서", 16)], _body(80)])
    findings = check_pdf_layout(p)
    orphan = [f for f in findings if f.code == "PDF_ORPHAN_HEADING"]
    assert len(orphan) == 1 and orphan[0].page == 1 and orphan[0].status is Status.REVIEW


def test_title_followed_by_body_on_same_page_is_not_flagged(tmp_path):
    p = _pdf_sized(tmp_path, [[(60, 80, "개인정보 동의서", 16)] + _body(110, 40), _body(80)])
    assert "PDF_ORPHAN_HEADING" not in codes(check_pdf_layout(p))


def test_closing_line_at_page_end_is_not_a_title(tmp_path):
    """'… 귀하' 같은 맺음 줄은 글자가 커도 제목이 아니다."""
    p = _pdf_sized(tmp_path, [_body(80) + [(60, 330, "서울특별시 마포구청장 귀하", 14)], _body(80)])
    assert "PDF_ORPHAN_HEADING" not in codes(check_pdf_layout(p))
