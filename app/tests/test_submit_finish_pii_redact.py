"""F5 주민번호 뒷자리 가림 테스트. 명백한 가짜 번호만 쓴다."""
import hashlib

import fitz
import pytest

from auto_write.services.submit_finish.pii_redact import redact_pdf, verify_redacted
from auto_write.services.submit_finish.status import Status

FRONT, TAIL = "900101", "1234567"


def _make_pdf(path, mode="full"):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Name: Hong Gildong", fontsize=14)
    if mode == "split":  # 앞부분과 뒷부분을 별도 텍스트 조각으로 배치
        page.insert_text((72, 140), FRONT + "-", fontsize=14)
        page.insert_text((72 + 60, 140), TAIL, fontsize=14)
    elif mode == "full":
        page.insert_text((72, 140), f"{FRONT}-{TAIL}", fontsize=14)
    doc.save(str(path))
    doc.close()


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _dark_ratio(pdf, rect, dpi=250):
    with fitz.open(str(pdf)) as d:
        pix = d[0].get_pixmap(dpi=dpi, alpha=False, clip=rect)
    px, n = pix.samples, pix.n
    dark = sum(1 for i in range(0, len(px), n) if px[i] < 60)
    return dark / (len(px) // n)


def test_뒷자리_가림_및_텍스트_미노출(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _make_pdf(src)
    before = _sha(src)
    r = redact_pdf(src, dst)
    assert r.redacted_boxes == 1 and r.undetected_pages == [] and r.pages == 1
    assert r.status == Status.PASS
    with fitz.open(str(dst)) as d:
        assert TAIL not in d[0].get_text()
    assert not any(f.status == Status.FAIL for f in verify_redacted(dst))
    assert _sha(src) == before  # 원본 불변


def test_박스는_뒷자리만_덮는다(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _make_pdf(src)
    with fitz.open(str(src)) as d:
        tail_r = d[0].search_for(TAIL)[0]
        front_r = d[0].search_for(FRONT)[0]
        name_r = d[0].search_for("Hong")[0]
    redact_pdf(src, dst)
    assert _dark_ratio(dst, tail_r) > 0.95
    assert _dark_ratio(dst, front_r) < 0.6  # 글자는 보이되 박스로 덮이지 않음
    assert _dark_ratio(dst, name_r) < 0.6


def test_쪼개진_조각도_가림(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _make_pdf(src, mode="split")
    r = redact_pdf(src, dst)
    assert r.redacted_boxes >= 1
    with fitz.open(str(src)) as d:
        tail_r = d[0].search_for(TAIL)[0]
    assert _dark_ratio(dst, tail_r) > 0.95


def test_같은_경로_및_기존_출력_거부(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _make_pdf(src)
    with pytest.raises(ValueError):
        redact_pdf(src, src)
    redact_pdf(src, dst)
    with pytest.raises(ValueError):
        redact_pdf(src, dst)
    redact_pdf(src, dst, overwrite=True)


def test_주민번호_없으면_박스0_NA(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _make_pdf(src, mode="none")
    r = redact_pdf(src, dst)
    assert r.redacted_boxes == 0 and r.status == Status.NA
    assert any(f.status == Status.NA for f in r.findings)


def test_텍스트레이어_없는_이미지PDF는_REVIEW(tmp_path):
    base, src, dst = tmp_path / "t.pdf", tmp_path / "scan.pdf", tmp_path / "o.pdf"
    _make_pdf(base)
    with fitz.open(str(base)) as d:
        png = d[0].get_pixmap(dpi=100).tobytes("png")
    doc = fitz.open()
    pg = doc.new_page()
    pg.insert_image(pg.rect, stream=png)
    doc.save(str(src))
    doc.close()
    r = redact_pdf(src, dst, use_ocr=False)
    assert r.undetected_pages == [0] and r.redacted_boxes == 0
    assert r.status == Status.REVIEW
    assert any(f.status == Status.REVIEW for f in r.findings)


def test_verify는_남은_뒷자리를_FAIL(tmp_path):
    src = tmp_path / "a.pdf"
    _make_pdf(src)
    assert any(f.status == Status.FAIL for f in verify_redacted(src))
    assert any(f.status == Status.FAIL for f in verify_redacted(src, [TAIL]))


# ---------------------------------------------------------------- 스캔 PDF OCR 가림
import io
import shutil
import sys

from auto_write.services.submit_finish.pii_redact import OcrWord, windows_ocr


def _scan_pdf(path, text="주민등록번호 900101-1234567 홍길동", size=60):
    """텍스트 레이어 없는 이미지 전용 PDF(가짜 문장). 반환: 이미지 PIL 기준 없이 PDF 경로."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (2067, 600), "white")  # A4 폭 250dpi 상당
    ImageDraw.Draw(img).text((100, 200), text, fill="black",
                             font=ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", size))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    doc = fitz.open()
    pg = doc.new_page(width=2067 * 72 / 250, height=600 * 72 / 250)
    pg.insert_image(pg.rect, stream=buf.getvalue())
    doc.save(str(path))
    doc.close()


def _pix_dark(pdf, x0, y0, x1, y1, dpi=250):
    """결과 PDF 첫 페이지의 픽셀 사각형(250dpi 기준)에서 검은 픽셀 비율."""
    with fitz.open(str(pdf)) as d:
        pix = d[0].get_pixmap(dpi=dpi, alpha=False)
    sub = fitz.IRect(int(x0), int(y0), int(x1), int(y1)) & pix.irect
    dark = n = 0
    for y in range(sub.y0, sub.y1):
        for x in range(sub.x0, sub.x1):
            n += 1
            dark += pix.pixel(x, y)[0] < 40
    return dark / max(n, 1)


def test_가짜OCR_하이픈포함_한덩어리_뒷자리만_박스(tmp_path):
    src, dst = tmp_path / "s.pdf", tmp_path / "o.pdf"
    _scan_pdf(src, text="x")
    # 단어 'ABCDEF'+'900101-1234567' 한 덩어리: 폭 1400px, 글자 14자(하이픈 0.5 가중)
    words = [OcrWord("주민등록번호", 100, 200, 400, 80), OcrWord("900101-1234567", 600, 200, 1350, 80),
             OcrWord("홍길동", 2000, 200, 60, 80)]
    r = redact_pdf(src, dst, ocr_fn=lambda png, dpi: words)
    assert r.redacted_boxes == 1 and r.undetected_pages == [] and r.status == Status.PASS
    total = 13.5  # 숫자13 + 하이픈0.5
    tail_x0 = 600 + 1350 * 6.5 / total
    assert _pix_dark(dst, tail_x0 + 20, 215, 1950, 265) > 0.95  # 뒷자리 안쪽
    assert _pix_dark(dst, 610, 215, 600 + 1350 * 5.5 / total, 265) < 0.05  # 앞 6자리 안 덮임
    assert _pix_dark(dst, 100, 215, 500, 265) < 0.05  # 다른 단어 안 덮임
    assert any("OCR" in (f.evidence or "") for f in r.findings)


def test_가짜OCR_뒷자리_별도_단어와_공백_하이픈변형(tmp_path):
    src, dst = tmp_path / "s.pdf", tmp_path / "o.pdf"
    _scan_pdf(src, text="x")
    words = [OcrWord("900101", 100, 200, 300, 80), OcrWord("–", 420, 200, 20, 80),
             OcrWord("1234567", 460, 200, 500, 80), OcrWord("홍길동", 1200, 200, 200, 80)]
    r = redact_pdf(src, dst, ocr_fn=lambda png, dpi: words)
    assert r.redacted_boxes == 1 and r.status == Status.PASS
    assert _pix_dark(dst, 480, 215, 940, 265) > 0.95
    assert _pix_dark(dst, 110, 215, 390, 265) < 0.05


def test_OCR_사용불가_예외_use_ocr_False는_REVIEW(tmp_path):
    src = tmp_path / "s.pdf"
    _scan_pdf(src, text="x")
    for i, kw in enumerate(({"ocr_fn": lambda *a: None}, {"ocr_fn": lambda *a: 1 / 0}, {"use_ocr": False})):
        dst = tmp_path / f"o{i}.pdf"
        r = redact_pdf(src, dst, **kw)
        assert r.undetected_pages == [0] and r.redacted_boxes == 0 and r.status == Status.REVIEW


def test_OCR_글자_거의_없음_및_앞6자리만_보이면_REVIEW(tmp_path):
    src = tmp_path / "s.pdf"
    _scan_pdf(src, text="x")
    few = [OcrWord("a", 0, 0, 10, 10), OcrWord("b", 20, 0, 10, 10)]
    r = redact_pdf(src, tmp_path / "a.pdf", ocr_fn=lambda *a: few)
    assert r.undetected_pages == [0] and r.status == Status.REVIEW
    front = [OcrWord("성명", 0, 0, 100, 40), OcrWord("생년월일", 120, 0, 200, 40),
             OcrWord("900101-12", 400, 0, 300, 40), OcrWord("홍길동", 800, 0, 100, 40)]
    r2 = redact_pdf(src, tmp_path / "b.pdf", ocr_fn=lambda *a: front)
    assert r2.undetected_pages == [0] and r2.status == Status.REVIEW


def test_OCR_충분히_읽혔고_패턴없으면_NA_증거에_OCR기반(tmp_path):
    src = tmp_path / "s.pdf"
    _scan_pdf(src, text="x")
    words = [OcrWord(t, i * 100, 0, 90, 40) for i, t in enumerate(["성명", "홍길동", "주소", "서울시"])]
    r = redact_pdf(src, tmp_path / "o.pdf", ocr_fn=lambda *a: words)
    assert r.undetected_pages == [] and r.redacted_boxes == 0 and r.status == Status.NA
    assert any("OCR 기반" in (f.evidence or "") for f in r.findings)


_HAS_WIN_OCR = (sys.platform == "win32" and shutil.which("powershell.exe") is not None
                and __import__("os").path.exists(r"C:\Windows\Fonts\malgun.ttf"))


@pytest.mark.skipif(not _HAS_WIN_OCR, reason="Windows + powershell.exe + malgun.ttf 필요")
def test_실제_WindowsOCR로_스캔PDF_뒷자리_가림(tmp_path):
    src, dst = tmp_path / "s.pdf", tmp_path / "o.pdf"
    _scan_pdf(src)
    with fitz.open(str(src)) as d:
        png = d[0].get_pixmap(dpi=250, alpha=False).tobytes("png")
    before = windows_ocr(png, 250)
    if before is None:
        pytest.skip("Windows OCR 엔진 사용 불가")
    tail_w = [w for w in before if "1234567" in w.text.replace("l", "1")]
    assert tail_w, f"OCR 이 뒷자리를 못 읽음: {[w.text for w in before]}"
    r = redact_pdf(src, dst)
    assert r.redacted_boxes >= 1 and r.status == Status.PASS, [f.message for f in r.findings]
    w = tail_w[0]
    # ① 뒷자리 영역(단어 오른쪽 60%)이 검게 칠해짐
    assert _pix_dark(dst, w.x + w.w * 0.6, w.y + w.h * 0.3, w.x + w.w * 0.95, w.y + w.h * 0.7) > 0.9
    # ② 앞 6자리(단어 왼쪽 25%)와 이름은 칠해지지 않음
    assert _pix_dark(dst, w.x, w.y + 2, w.x + w.w * 0.3, w.y + w.h - 2) < 0.6
    names = [x for x in before if "홍" in x.text]
    if names:
        assert _pix_dark(dst, names[0].x, names[0].y + 2, names[0].x + names[0].w, names[0].y + names[0].h - 2) < 0.6
    # ③ 가림 결과를 다시 OCR 하면 뒷자리 7자리가 더 이상 읽히지 않음
    with fitz.open(str(dst)) as d:
        png2 = d[0].get_pixmap(dpi=250, alpha=False).tobytes("png")
    after = windows_ocr(png2, 250) or []
    assert not any("1234567" in x.text.replace("l", "1") for x in after), [x.text for x in after]
