# -*- coding: utf-8 -*-
"""실양식(마포) 실환경 검증에서 나온 일반 결함의 회귀 테스트 — 전부 가짜 데이터.

- 떠 있는 표 분리 / 원본 쪽 시작 제목 고정 / 쪽 넘침 꼬리 줄이기(layout_guard)
- 날짜 줄 기입(date_fill, 탭이 낀 실양식 모양)
- 역할 바인딩 직인(bind_roles) · 렌더 실측 직인 위치(seal_align)
- 문서 순서 vs PDF 배치 순서(check_reading_order)
- 쪽 단위 AI 전송 허용(confirmed_pages) · 주민번호 앞자리 오탐(날짜·이미 가림) 정리
"""
from __future__ import annotations

import datetime as dt
import io
import zipfile
from pathlib import Path

import fitz
import pytest
from lxml import etree
from PIL import Image

from auto_write.services.submit_finish.date_fill import fill_date_lines
from auto_write.services.submit_finish.layout_guard import (
    anchors_of, apply_page_starts, baseline_page_start_titles, compact_overflow, find_overflow_sections,
    repair_layout, section_spans, split_floating_tables,
)
from auto_write.services.submit_finish.pdf_checks import check_reading_order
from auto_write.services.submit_finish.pii_redact import OcrWord, _ocr_scan
from auto_write.services.submit_finish.seal_align import align_to_markers, make_probe
from auto_write.services.submit_finish.seal_stamp import SealSpec, stamp_seals
from auto_write.services.submit_finish.status import Status
from test_submit_finish_seal_checkbox import _HP, _p, _pics, _section, _tbl, _write_hwpx

HPX = f"{{{_HP}}}"


# ── 빌더 ────────────────────────────────────────────────────────
def _ftbl(text: str, treat_as_char: int = 0) -> str:
    """떠 있는(기본) 1x1 표 run 한 개."""
    return (f'<hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="1">'
            f'<hp:sz width="1000" height="500"/><hp:pos treatAsChar="{treat_as_char}" vertRelTo="PARA"/>'
            f'<hp:tr><hp:tc><hp:subList><hp:p paraPrIDRef="0"><hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p></hp:subList>'
            f'<hp:cellAddr colAddr="0" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/></hp:tc></hp:tr>'
            f'</hp:tbl></hp:run>')


def _two_floating_paragraph() -> str:
    return ('<hp:p id="1" paraPrIDRef="3" pageBreak="0">' + _ftbl("머리표") + _ftbl("본문표")
            + '<hp:run charPrIDRef="9"><hp:t></hp:t></hp:run></hp:p>')


def _top_paragraphs(path: Path) -> list:
    return [p for p in _section(path) if etree.QName(p).localname == "p"]


def _png(w: int = 300, h: int = 200, color=(200, 0, 0)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "PNG")
    return b.getvalue()


def _pdf(tmp: Path, name: str, pages: list[list[tuple[float, float, str]]], images=None) -> Path:
    doc = fitz.open()
    for i, texts in enumerate(pages):
        pg = doc.new_page(width=595, height=842)
        for x, y, text in texts:
            pg.insert_text((x, y), text, fontname="korea", fontsize=11)
        for rect, data in (images or {}).get(i, []):
            pg.insert_image(fitz.Rect(*rect), stream=data)
    path = tmp / name
    doc.save(path)
    return path


# ── 떠 있는 표 분리 ──────────────────────────────────────────────
def test_floating_tables_in_one_paragraph_are_split_in_order(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("앞 문단") + _two_floating_paragraph() + _p("뒤 문단"))
    out = tmp_path / "out.hwpx"
    res = repair_layout(src, out)
    assert res["split"] == 1 and [f.code for f in res["findings"]] == ["LAYOUT_SPLIT_FLOATING"]
    paras = _top_paragraphs(out)
    assert len(paras) == 4
    assert ["".join(p.itertext()) for p in paras] == ["앞 문단", "머리표", "본문표", "뒤 문단"]
    assert paras[1].get("paraPrIDRef") == paras[2].get("paraPrIDRef") == "3"  # 문단 모양 유지
    # 원본 불변·재실행 멱등
    assert len(_top_paragraphs(src)) == 3
    again = tmp_path / "again.hwpx"
    assert repair_layout(out, again)["split"] == 0


def test_inline_tables_are_not_split(tmp_path):
    src = tmp_path / "in.hwpx"
    body = ('<hp:p paraPrIDRef="0">' + _ftbl("가", 1) + _ftbl("나", 1) + '</hp:p>')  # 글자처럼 취급 → 그대로
    _write_hwpx(src, body)
    out = tmp_path / "out.hwpx"
    assert repair_layout(src, out)["split"] == 0
    assert len(_top_paragraphs(out)) == 1


# ── 원본 쪽 시작 제목 고정 ────────────────────────────────────────
def test_baseline_page_start_titles_pin_only_short_titles_that_start_a_page(tmp_path):
    base = tmp_path / "base.hwpx"
    _write_hwpx(base, _p("가짜 신청서 1쪽 본문") + _p("사업 계획서") + _p("본문 한 줄") + _p("참가 서약서")
                + _p("서약 문장입니다 " * 8))
    base_pdf = _pdf(tmp_path, "base.pdf", [
        [(60, 100, "가짜 신청서 1쪽 본문")],
        [(60, 100, "사업 계획서"), (60, 130, "본문 한 줄")],
        [(60, 100, "참가 서약서"), (60, 130, "서약 문장입니다")],
    ])
    titles = baseline_page_start_titles(base, base_pdf)
    assert titles == ["사업계획서", "참가서약서"]
    filled = tmp_path / "filled.hwpx"
    _write_hwpx(filled, _p("가짜 신청서 1쪽 본문") + _p("사업 계획서") + _p("본문 한 줄 + 길어진 값") + _p("참가 서약서"))
    out = tmp_path / "out.hwpx"
    res = repair_layout(filled, out, page_start_titles=titles)
    assert res["page_breaks"] == 2
    flags = [p.get("pageBreak") for p in _top_paragraphs(out)]
    assert flags == [None, "1", None, "1"]  # 제목 문단만, 본문·1쪽 문단은 그대로
    assert anchors_of(out) == ["사업계획서", "참가서약서"]


def test_apply_page_starts_ignores_unknown_titles(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("본문"))
    root = etree.fromstring(zipfile.ZipFile(src).read("Contents/section0.xml"))
    assert apply_page_starts(root, ["없는제목"]) == 0


# ── 쪽 넘침 꼬리 ────────────────────────────────────────────────
def test_overflow_tail_detected_and_one_spacer_removed_per_step(tmp_path):
    spacer = '<hp:p paraPrIDRef="0"><hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p>'
    pic_para = ('<hp:p paraPrIDRef="0"><hp:run charPrIDRef="0"><hp:pic id="9"><hp:sz width="10" height="10"/>'
                '</hp:pic></hp:run></hp:p>')  # 빈 글자라도 그림이 있으면 spacer 아님
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("신청서 본문") + spacer + pic_para + spacer + _p("다음 부")
                .replace('paraPrIDRef="0"', 'paraPrIDRef="0" pageBreak="1"') + spacer)
    base_pdf = _pdf(tmp_path, "b.pdf", [[(60, 100, "신청서 본문")], [(60, 100, "다음부")]])
    over_pdf = _pdf(tmp_path, "o.pdf", [[(60, 100, "신청서 본문")], [(60, 100, "넘친 꼬리 줄")], [(60, 100, "다음부")]])
    anchors = anchors_of(src)
    assert anchors == ["다음부"]
    base, over = section_spans(base_pdf, anchors), section_spans(over_pdf, anchors)
    assert base == [(1, 1, base[0][2]), (2, 2, base[1][2])]
    assert [s[:2] for s in over] == [(1, 2), (3, 3)]
    assert find_overflow_sections(over, base) == [0]          # 첫 부만 넘침
    assert find_overflow_sections(base, base) == []
    out = tmp_path / "out.hwpx"
    assert compact_overflow(src, out, 0)["removed"] is True
    texts = [("".join(p.itertext()), len(list(p.iter(HPX + "pic")))) for p in _top_paragraphs(out)]
    assert len(texts) == 5 and texts.count(("", 0)) == 2 and texts[2] == ("", 1)  # 부0 의 마지막 spacer 1개만 제거
    assert texts[-1] == ("", 0)  # 다음 부(뒤쪽)의 spacer 는 그대로


def test_overflow_not_flagged_when_last_page_is_full(tmp_path):
    body = [(60, 100 + 14 * i, f"줄 {i}") for i in range(52)]  # 쪽 하단까지 채움
    p = _pdf(tmp_path, "f.pdf", [[(60, 100, "본문")], body])
    base = _pdf(tmp_path, "b.pdf", [[(60, 100, "본문")]])
    assert find_overflow_sections(section_spans(p, []), section_spans(base, [])) == []


# ── 날짜 줄 ─────────────────────────────────────────────────────
def _date_para(inner: str) -> str:
    return f'<hp:p paraPrIDRef="0"><hp:run charPrIDRef="0"><hp:t>{inner}</hp:t></hp:run></hp:p>'


def test_blank_date_lines_filled_with_tabs_between_pieces(tmp_path):
    src = tmp_path / "in.hwpx"
    body = (_date_para('2026년<hp:tab width="831" leader="0" type="1"/> 월  일')
            + _date_para('2026년<hp:tab width="831" leader="0" type="1"/> 월<hp:tab width="1200" leader="0" type="1"/> 일')
            + _date_para("2026년 월 일")
            + _date_para("2026년 3월 4일")                                   # 이미 있는 날짜는 덮어쓰지 않음
            + _date_para("본 협약은 2026년 월 일 체결되었으며 그 효력은 다음과 같이 길게 이어지는 문장 속 날짜다"))
    _write_hwpx(src, body)
    out = tmp_path / "out.hwpx"
    r = fill_date_lines(src, out, dt.date(2026, 10, 6))
    assert r["filled"] == 3
    texts = ["".join(t.itertext()) for t in _section(out).iter(HPX + "t")]
    assert texts[0].replace("\t", "").split() == ["2026년", "10월", "6일"] or "10월" in texts[0] and "6일" in texts[0]
    assert "10월" in texts[1] and "6일" in texts[1]
    assert texts[2] == "2026년 10월 6일"
    assert texts[3] == "2026년 3월 4일"
    assert "10월" not in texts[4]                                              # 긴 문장 속 날짜는 대상 아님
    assert fill_date_lines(out, tmp_path / "again.hwpx", dt.date(2026, 10, 6))["filled"] == 0  # 멱등


def test_date_year_mismatch_is_review_not_filled(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _date_para("2025년 월 일"))
    r = fill_date_lines(src, tmp_path / "out.hwpx", dt.date(2026, 10, 6))
    assert r["filled"] == 0
    assert [f.code for f in r["findings"]] == ["DATE_YEAR_MISMATCH"] and r["findings"][0].status is Status.REVIEW


# ── 역할 바인딩 직인 ─────────────────────────────────────────────
def _seal_img(tmp_path: Path) -> Path:
    path = tmp_path / "seal.png"
    path.write_bytes(_png(300, 300))
    return path


def test_role_bound_seal_stamps_every_representative_line_not_members(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("신청자(대표자)            (서명/인)") + _p("신청자(대표자)            (서명/인)")
                + _p("팀원1        (서명/인)") + _p("팀원2        (서명/인)"))
    out = tmp_path / "out.hwpx"
    spec = SealSpec(owner="홍길동", image=_seal_img(tmp_path), user_approved=True,
                    bind_roles=("representative", "applicant"), width_mm=17)
    res = stamp_seals(src, out, [spec], write_names=True)
    assert res["inserted"] == 2 and len(_pics(out)) == 2
    codes = [f.code for f in res["findings"]]
    assert codes.count("F1_SEAL_INSERTED") == 2 and codes.count("F1_SEAL_OTHER_PARTY") == 2
    texts = ["".join(p.itertext()) for p in _top_paragraphs(out)]
    assert "홍길동" in texts[0] and "홍길동" in texts[1]       # 이름도 표식 앞에 기입
    assert "홍길동" not in texts[2] and "홍길동" not in texts[3]


def test_role_binding_requires_user_approval(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("신청자(대표자) (서명/인)"))
    spec = SealSpec(owner="홍길동", image=_seal_img(tmp_path), user_approved=False,
                    bind_roles=("representative",), width_mm=17)
    res = stamp_seals(src, tmp_path / "out.hwpx", [spec])
    assert res["inserted"] == 0 and [f.code for f in res["findings"]] == ["F1_SEAL_OWNER_UNKNOWN"]


def test_two_role_specs_conflict_instead_of_guessing(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("신청자(대표자) (서명/인)"))
    specs = [SealSpec(owner=n, image=_seal_img(tmp_path), user_approved=True, bind_roles=("representative",))
             for n in ("가나다", "라마바")]
    res = stamp_seals(src, tmp_path / "out.hwpx", specs)
    assert res["inserted"] == 0 and [f.code for f in res["findings"]] == ["F1_SEAL_BINDING_CONFLICT"]


# ── 직인 위치 실측 보정 ──────────────────────────────────────────
def test_seal_probe_then_align_to_marker_center(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("신청자(대표자)  (서명/인)"))
    stamped = tmp_path / "stamped.hwpx"
    spec = SealSpec(owner="홍길동", image=_seal_img(tmp_path), user_approved=True, bind_roles=("representative",),
                    width_mm=10)
    stamp_seals(src, stamped, [spec])
    probe = tmp_path / "probe.hwpx"
    assert make_probe(stamped, probe)["seals"] == 1
    pos = next(_section(probe).iter(HPX + "pos"))
    assert (pos.get("horzAlign"), pos.get("horzOffset"), pos.get("vertAlign")) == ("LEFT", "0", "CENTER")
    # probe 렌더를 흉내: 문단 왼쪽 기준 x0=60pt 에 직인(28.35pt), 표식 글자는 x≈300pt
    w = 10 / 25.4 * 72
    pdf = _pdf(tmp_path, "probe.pdf", [[(60, 100, "신청자(대표자)"), (300, 100, "(서명/인)")]],
               images={0: [((60, 85, 60 + w, 85 + w), _png(300, 300))]})
    with fitz.open(str(pdf)) as d:
        marker = d[0].search_for("(서명/인)")[0]
    out = tmp_path / "aligned.hwpx"
    res = align_to_markers(probe, pdf, out)
    assert res["aligned"] == 1 and res["findings"][0].code == "SEAL_ALIGNED"
    off = int(next(_section(out).iter(HPX + "pos")).get("horzOffset"))
    center_after = 60 + off / 100 + w / 2
    assert abs(center_after - (marker.x0 + marker.x1) / 2) < 1.0


def test_seal_align_skips_when_count_mismatch(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("신청자(대표자) (서명/인)"))
    stamped = tmp_path / "stamped.hwpx"
    stamp_seals(src, stamped, [SealSpec(owner="홍길동", image=_seal_img(tmp_path), user_approved=True,
                                        bind_roles=("representative",), width_mm=10)])
    pdf = _pdf(tmp_path, "none.pdf", [[(60, 100, "신청자(대표자) (서명/인)")]])  # 렌더에 직인 그림이 없음
    res = align_to_markers(stamped, pdf, tmp_path / "out.hwpx")
    assert res["aligned"] == 0 and res["findings"][0].code == "SEAL_ALIGN_COUNT"


# ── 문서 순서 vs 배치 순서 ────────────────────────────────────────
def test_reading_order_detects_body_pushed_after_following_section(tmp_path):
    src = tmp_path / "in.hwpx"
    _write_hwpx(src, _p("사업계획서 제목입니다") + _p("아이디어 제안배경 본문") + _p("참가 서약서 제목입니다"))
    good = _pdf(tmp_path, "good.pdf", [[(60, 100, "사업계획서 제목입니다"), (60, 140, "아이디어 제안배경 본문")],
                                       [(60, 100, "참가 서약서 제목입니다")]])
    bad = _pdf(tmp_path, "bad.pdf", [[(60, 100, "사업계획서 제목입니다"), (60, 140, "참가 서약서 제목입니다")],
                                     [(60, 100, "아이디어 제안배경 본문")]])
    ok = check_reading_order(good, src)
    assert [f.status for f in ok] == [Status.PASS]
    nok = check_reading_order(bad, src)
    assert nok[0].status is Status.FAIL and nok[0].code == "PDF_READING_ORDER"


# ── 쪽 단위 외부 전송 허용 ────────────────────────────────────────
def test_visual_qa_sends_only_confirmed_pages(tmp_path):
    from auto_write.services.submit_finish.status import Finding
    from auto_write.services.submit_finish.visual_qa import run_visual_qa

    class Ext:
        name, model, external = "fake-ext", "m", True

        def __init__(self):
            self.stats = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
            self.sent: list[int] = []

        def inspect_page(self, png, page_no, ctx):
            self.sent.append(page_no)
            return [Finding("VISUAL_NO_ISSUE", Status.PASS, "자동 검사에서 추가 이상 미발견", source="visual-ai", page=page_no)]

    pdf = _pdf(tmp_path, "m.pdf", [[(60, 100, "신청서")], [(60, 100, "첨부 1쪽")], [(60, 100, "첨부 2쪽")]])
    prov = Ext()
    rep = run_visual_qa(pdf, tmp_path / "v", prov, redaction_confirmed=False, confirmed_pages={1, 3})
    assert prov.sent == [1, 3]
    blocked = [f.page for f in rep.findings if f.code == "VISUAL_EXTERNAL_BLOCKED"]
    assert blocked == [2]


# ── 주민번호 앞자리 오탐 정리 ──────────────────────────────────────
def _words(text: str) -> list[OcrWord]:
    out, x = [], 10.0
    for i, w in enumerate(text.split()):
        out.append(OcrWord(text=w, x=x, y=20.0, w=len(w) * 10.0, h=12.0, line=0))
        x += len(w) * 10.0 + 6
    return out


@pytest.mark.parametrize("text,flagged", [
    ("전입일 190515-05-15 세대주", False),     # 날짜 문맥
    ("신고일 19.05.190515 확인", False),       # 앞이 날짜 구분자
    ("주민등록번호 920101-******* 입니다", False),  # 이미 가려진 표기
    ("주민등록번호 920101-1****** 입니다", False),
    ("주민등록번호 920101- 입니다", True),       # 앞자리만 보이고 뒤가 안 읽힘 → 계속 REVIEW
    ("920101 홍길동", True),
])
def test_front_candidates_ignore_dates_and_masked_tails(text, flagged):
    boxes, front = _ocr_scan(_words(text))
    assert bool(front) is flagged
    assert boxes == []
