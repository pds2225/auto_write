"""test_pure_doc_text_extract.py — doc_text_extract 로컬 추출 로직 회귀.

COM/HWP/네트워크 없이 로컬 파일(txt/md/docx)과 실패-노트 경로만 결정론으로 검증한다.
- 텍스트 파일 인코딩 폴백(utf-8 → cp949 → euc-kr → replace).
- .docx 문단 + 표 셀(" | " 결합) 추출.
- 없는 파일 / 알 수 없는 확장자 / 손상 docx / 비-PDF(.pdf) 는 예외 없이 (text, notes) 반환.

주의: 실제 HWP/PDF 변환은 외부 의존이라 호출하지 않는다 — .pdf 는 '유효하지 않은 내용'을
넣어 추출 실패 노트 경로만 확인한다(pypdf 설치 여부와 무관하게 "" + 안내노트).
"""

from __future__ import annotations

from docx import Document

from auto_write.services.doc_text_extract import _read_textfile, _docx_text, extract_text


# --------------------------------------------------------------------------
# _read_textfile — 인코딩 폴백
# --------------------------------------------------------------------------

def test_read_textfile_utf8_roundtrip(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("한글 본문 내용\n둘째 줄", encoding="utf-8")
    assert _read_textfile(p) == "한글 본문 내용\n둘째 줄"


def test_read_textfile_cp949_fallback(tmp_path):
    p = tmp_path / "b.txt"
    # cp949 로만 저장(utf-8 로 읽으면 실패 → cp949 폴백 경로 검증).
    p.write_bytes("가나다 사업계획서".encode("cp949"))
    assert _read_textfile(p) == "가나다 사업계획서"


def test_read_textfile_never_raises_on_binary(tmp_path):
    p = tmp_path / "c.bin"
    p.write_bytes(b"\xff\xfe\x00\x01garbage")
    # 어떤 인코딩으로도 못 읽으면 errors="replace" 로라도 문자열을 돌려준다(예외 금지).
    out = _read_textfile(p)
    assert isinstance(out, str)


# --------------------------------------------------------------------------
# _docx_text — 문단 + 표
# --------------------------------------------------------------------------

def _make_docx(tmp_path, name="d.docx"):
    doc = Document()
    doc.add_paragraph("첫 문단")
    doc.add_paragraph("   ")  # 공백뿐 → 제외되어야 함
    doc.add_paragraph("둘째 문단")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "라벨"
    table.rows[0].cells[1].text = "값"
    table.rows[1].cells[0].text = ""      # 빈 셀
    table.rows[1].cells[1].text = "홀로"
    path = tmp_path / name
    doc.save(str(path))
    return path


def test_docx_text_joins_paragraphs_and_table_cells(tmp_path):
    text = _docx_text(_make_docx(tmp_path))
    lines = text.split("\n")
    assert lines[0] == "첫 문단"
    assert "둘째 문단" in lines
    # 공백뿐인 문단은 빠진다.
    assert "   " not in lines
    # 표 행은 비어있지 않은 셀만 " | " 로 결합.
    assert "라벨 | 값" in text
    assert "홀로" in text


# --------------------------------------------------------------------------
# extract_text — 디스패치 + 안내노트
# --------------------------------------------------------------------------

def test_extract_txt_returns_text_no_notes(tmp_path):
    p = tmp_path / "e.txt"
    p.write_text("공고 본문", encoding="utf-8")
    text, notes = extract_text(p)
    assert text == "공고 본문"
    assert notes == []


def test_extract_md_returns_text(tmp_path):
    p = tmp_path / "e.md"
    p.write_text("# 제목\n내용", encoding="utf-8")
    text, notes = extract_text(str(p))  # str 경로도 허용
    assert "제목" in text
    assert notes == []


def test_extract_missing_file_returns_note(tmp_path):
    text, notes = extract_text(tmp_path / "nope.txt")
    assert text == ""
    assert notes and "파일이 없습니다" in notes[0]


def test_extract_unknown_extension_reads_as_text_with_note(tmp_path):
    p = tmp_path / "f.xyz"
    p.write_text("정체불명 형식", encoding="utf-8")
    text, notes = extract_text(p)
    assert text == "정체불명 형식"
    assert notes and "알 수 없는 형식" in notes[0]


def test_extract_docx_extracts_content(tmp_path):
    text, notes = extract_text(_make_docx(tmp_path, "g.docx"))
    assert "첫 문단" in text
    assert "라벨 | 값" in text
    assert notes == []


def test_extract_corrupt_docx_returns_failure_note(tmp_path):
    p = tmp_path / "bad.docx"
    p.write_bytes(b"not a real docx zip")
    text, notes = extract_text(p)
    assert text == ""
    assert notes and "DOCX 읽기 실패" in notes[0]


def test_extract_invalid_pdf_returns_failure_note(tmp_path):
    # 실제 PDF 없이 실패-노트 경로만 검증(외부 변환 미호출).
    p = tmp_path / "scan.pdf"
    p.write_bytes(b"%PDF-broken not really a pdf")
    text, notes = extract_text(p)
    assert text == ""
    assert notes and "PDF 텍스트 추출 실패" in notes[0]
