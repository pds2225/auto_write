# -*- coding: utf-8 -*-
"""P0-2: known dangerous positions are protected and never auto-writeable."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    classify_protected_regions,
    is_guidance_paragraph,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_REAL = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "(별첨1) 2024년도 창업중심대학 예비창업자 사업계획서 양식.hwpx"
)


def _hwpx(path: Path, body: str) -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )
    hpf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/section0.xml", xml.encode("utf-8"))
        archive.writestr("Contents/content.hpf", hpf.encode("utf-8"))


def _decisions_for(report, raw_snippet: str):
    return [item for item in report.decisions if raw_snippet in item.observed_text]


def test_guidance_detection_does_not_use_keyword_alone() -> None:
    assert is_guidance_paragraph("※ 사업계획서는 15페이지 이내로 작성")
    assert is_guidance_paragraph("※" + ("안내" * 80))
    assert is_guidance_paragraph("작성요령")
    assert is_guidance_paragraph("삭제 후 작성하십시오")
    assert is_guidance_paragraph("작성방법: 기능을 개발한 경위와 성과를 기재하십시오")
    assert not is_guidance_paragraph("우리는 작성방법을 개발했다")
    assert not is_guidance_paragraph("당사는 삭제 후 작성 기능을 개발했다")
    assert not is_guidance_paragraph("작성방법을 기재한 매뉴얼을 배포했다")
    assert not is_guidance_paragraph("예시 고객 분석")


def test_known_hazards_are_not_auto_writable(tmp_path: Path) -> None:
    body = """
    <hp:p><hp:run><hp:t>※ 사업계획서는 목차(1페이지)를 제외하고 15페이지 이내로 작성</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t></hp:t></hp:run><hp:run><hp:t>대표이사 : (인)</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>성 명 : (서명)</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>기 업 명 :</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>2025년 월 일</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>해 당</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>□예</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>□ 기업개요 및 문제점</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>우리는 작성방법을 개발했다</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>예시 고객 분석</hp:t></hp:run></hp:p>
    <hp:p/>
    """
    src = tmp_path / "protected.hwpx"
    _hwpx(src, body)
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    report = classify_protected_regions(index)
    assert src.read_bytes() == before
    assert report.auto_write_allowed_count == 0
    assert all(item.auto_write_allowed is False for item in report.decisions)
    assert all(item.field_label is None for item in report.decisions)

    guidance = _decisions_for(report, "※ 사업계획서")
    assert guidance
    assert guidance[0].decision == "NO_TARGET"
    assert guidance[0].role == "GUIDANCE"
    assert guidance[0].review_reasons == ("GUIDANCE_ONLY",)
    assert guidance[0].observed_text.startswith("※")

    signature_line = _decisions_for(report, "대표이사 : (인)")
    assert signature_line[0].run_index == 1
    assert signature_line[0].decision == "REVIEW_REQUIRED"
    assert "SIGNATURE_PROTECTED" in signature_line[0].review_reasons
    spacer = next(item for item in report.decisions if item.paragraph_index == signature_line[0].paragraph_index and item.run_index == 0)
    assert spacer.role == "SPACER"
    assert spacer.decision == "NO_TARGET"
    assert spacer.observed_text == ""

    name = _decisions_for(report, "성 명 : (서명)")
    assert name[0].decision == "REVIEW_REQUIRED"
    assert name[0].role == "SIGNATURE"
    assert name[0].observed_text == "성 명 : (서명)"

    company = _decisions_for(report, "기 업 명 :")
    assert company[0].decision == "NO_TARGET"
    assert company[0].role == "LABEL"

    date = _decisions_for(report, "2025년 월 일")
    assert date[0].decision == "REVIEW_REQUIRED"
    assert date[0].role == "DATE_SCAFFOLD"

    header = _decisions_for(report, "해 당")
    assert header[0].decision == "REVIEW_REQUIRED"
    assert header[0].role == "UNCONFIRMED_CHOICE"
    assert header[0].field_label is None

    mark = _decisions_for(report, "□예")
    assert mark[0].role == "UNCONFIRMED_CHOICE"
    assert mark[0].decision == "REVIEW_REQUIRED"

    square = _decisions_for(report, "□ 기업개요")
    assert square[0].role == "HEADING"
    assert square[0].decision == "NO_TARGET"

    narrative = _decisions_for(report, "작성방법을 개발")
    assert narrative[0].role == "EXISTING_VALUE"
    assert narrative[0].decision == "NO_TARGET"

    example_label = _decisions_for(report, "예시 고객 분석")
    assert example_label[0].role != "GUIDANCE"
    assert example_label[0].decision == "NO_TARGET"


def _cell(text: str, row: int, col: int, *, col_span: int = 1, row_span: int = 1) -> str:
    return (
        "<hp:tc><hp:subList><hp:p><hp:run><hp:t>"
        + text
        + "</hp:t></hp:run></hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + f'<hp:cellSpan rowSpan="{row_span}" colSpan="{col_span}"/></hp:tc>'
    )


def test_audit_fail_cases_stay_unconfirmed(tmp_path: Path) -> None:
    body = """
    <hp:p>
      <hp:run><hp:t>기업명 :</hp:t></hp:run>
      <hp:run><hp:t></hp:t></hp:run>
      <hp:run><hp:t>대표자명 :</hp:t></hp:run>
    </hp:p>
    <hp:p>
      <hp:run><hp:t>성 명 : </hp:t></hp:run>
      <hp:run><hp:t>(서명)</hp:t></hp:run>
    </hp:p>
    <hp:p>
      <hp:run><hp:t>2025년 </hp:t></hp:run>
      <hp:run><hp:t>월 일</hp:t></hp:run>
    </hp:p>
    <hp:p><hp:run><hp:t>당사는 삭제 후 작성 기능을 개발했다</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>작성방법: 개발 내용을 기재하십시오</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>삭제 후 작성 관련 내용을 참고한다</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>확인</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>□ 개인정보 수집 및 이용에 동의함</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:tbl>
      <hp:tr>
        """ + _cell("예", 0, 0) + _cell("아니오", 0, 1) + """
      </hp:tr>
      <hp:tr>
        """ + _cell("휴폐업 중인 경우", 1, 0) + _cell("□예", 1, 1) + """
      </hp:tr>
    </hp:tbl></hp:run></hp:p>
    """
    src = tmp_path / "audit.hwpx"
    _hwpx(src, body)
    report = classify_protected_regions(index_hwpx_structure(src))
    assert report.auto_write_allowed_count == 0
    assert all(item.auto_write_allowed is False and item.field_label is None for item in report.decisions)

    gap = next(item for item in report.decisions if item.observed_text == "" and item.role == "EMPTY")
    assert gap.decision == "REVIEW_REQUIRED"
    assert gap.role != "SPACER"
    labels = [item for item in report.decisions if item.paragraph_index == gap.paragraph_index and item.role == "LABEL"]
    assert len(labels) == 2

    signature = [item for item in report.decisions if item.observed_text in {"성 명 : ", "(서명)"}]
    assert len(signature) == 2
    assert all(item.role == "SIGNATURE" and item.decision == "REVIEW_REQUIRED" for item in signature)

    date = [item for item in report.decisions if item.observed_text in {"2025년 ", "월 일"}]
    assert len(date) == 2
    assert all(item.role == "DATE_SCAFFOLD" and item.decision == "REVIEW_REQUIRED" for item in date)

    narrative = _decisions_for(report, "삭제 후 작성 기능을 개발했다")
    assert narrative[0].role == "EXISTING_VALUE"
    assert narrative[0].decision == "NO_TARGET"
    instruction = _decisions_for(report, "작성방법: 개발 내용을 기재하십시오")
    assert instruction[0].role == "GUIDANCE"
    assert instruction[0].decision == "NO_TARGET"
    ambiguous = _decisions_for(report, "삭제 후 작성 관련 내용을 참고한다")
    assert ambiguous[0].role == "AMBIGUOUS"
    assert ambiguous[0].decision == "REVIEW_REQUIRED"

    outside = _decisions_for(report, "확인")
    assert outside[0].role != "CHOICE_HEADER"
    assert outside[0].decision == "REVIEW_REQUIRED"
    consent = _decisions_for(report, "개인정보 수집")
    assert consent[0].role != "HEADING"
    assert consent[0].decision == "REVIEW_REQUIRED"
    structured = _decisions_for(report, "아니오")
    assert structured[0].role == "CHOICE_HEADER"
    assert structured[0].decision == "NO_TARGET"


def test_guidance_context_and_logical_choice_columns(tmp_path: Path) -> None:
    body = """
    <hp:p><hp:run><hp:t>작성방법: 기능을 개발한 경위와 성과를 기재하십시오</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>작성방법을 기재한 매뉴얼을 배포했다</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:tbl>
      <hp:tr>
        """ + _cell("□ 자가소유", 0, 0) + _cell("□ 임차사용", 0, 1) + """
      </hp:tr>
    </hp:tbl></hp:run></hp:p>
    <hp:p><hp:run><hp:tbl>
      <hp:tr>
        <hp:tc><hp:subList><hp:p><hp:run><hp:t>예</hp:t></hp:run></hp:p></hp:subList>
          <hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/>
        </hp:tc>
      </hp:tr>
      <hp:tr>
        <hp:tc><hp:subList><hp:p><hp:run><hp:t>□ 자가소유</hp:t></hp:run></hp:p></hp:subList>
          <hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/>
        </hp:tc>
      </hp:tr>
    </hp:tbl></hp:run></hp:p>
    """
    src = tmp_path / "blockers.hwpx"
    _hwpx(src, body)
    report = classify_protected_regions(index_hwpx_structure(src))
    assert report.auto_write_allowed_count == 0

    instruction = _decisions_for(report, "경위와 성과를 기재하십시오")
    assert instruction
    assert instruction[0].role == "GUIDANCE"
    assert instruction[0].decision == "NO_TARGET"

    manual = _decisions_for(report, "매뉴얼을 배포했다")
    assert manual
    assert manual[0].role != "GUIDANCE"
    assert manual[0].role == "EXISTING_VALUE"

    owned = _decisions_for(report, "□ 자가소유")
    rented = _decisions_for(report, "□ 임차사용")
    assert owned and rented
    assert all(item.role != "HEADING" for item in owned + rented)
    paired = [item for item in owned + rented if item.role == "CHOICE_MARK"]
    assert len(paired) == 2
    assert all(item.decision == "NO_TARGET" for item in paired)

    mismatched = [item for item in owned if item.role != "CHOICE_MARK"]
    assert len(mismatched) == 1
    assert mismatched[0].role == "UNCONFIRMED_CHOICE"
    assert mismatched[0].decision == "REVIEW_REQUIRED"


def test_plan_options_are_not_headings_and_title_row_stays_heading(tmp_path: Path) -> None:
    body = """
    <hp:p><hp:run><hp:tbl>
      <hp:tr>
        """ + _cell("향후 채용 계획", 0, 0, col_span=3) + """
      </hp:tr>
      <hp:tr>
        """ + _cell("향후 채용 계획 유무", 1, 0) + _cell("□ 계획 있음", 1, 1) + _cell("□ 계획 없음", 1, 2) + """
      </hp:tr>
    </hp:tbl></hp:run></hp:p>
    """
    src = tmp_path / "plan-choice.hwpx"
    _hwpx(src, body)
    report = classify_protected_regions(index_hwpx_structure(src))
    assert report.auto_write_allowed_count == 0

    title = [item for item in report.decisions if item.observed_text == "향후 채용 계획"]
    assert len(title) == 1
    assert title[0].role == "HEADING"
    assert title[0].decision == "NO_TARGET"
    question = [item for item in report.decisions if item.observed_text == "향후 채용 계획 유무"]
    assert question
    assert question[0].role != "HEADING"

    yes = _decisions_for(report, "□ 계획 있음")
    no = _decisions_for(report, "□ 계획 없음")
    assert yes and no
    assert all(item.role != "HEADING" for item in yes + no)
    assert all(item.role == "CHOICE_MARK" and item.decision == "NO_TARGET" for item in yes + no)
    assert all(item.auto_write_allowed is False for item in report.decisions)


def test_section_titles_in_one_column_stay_headings(tmp_path: Path) -> None:
    body = """
    <hp:p><hp:run><hp:tbl>
      <hp:tr>
        """ + _cell("□ 기업개요 및 문제점", 0, 0) + """
      </hp:tr>
      <hp:tr>
        """ + _cell("□ 성장전략", 1, 0) + """
      </hp:tr>
      <hp:tr>
        """ + _cell("소유형태", 2, 0) + _cell("□ 자가소유", 2, 1) + _cell("□ 임차사용", 2, 2) + """
      </hp:tr>
      <hp:tr>
        <hp:tc><hp:subList><hp:p><hp:run><hp:t>□ 계획 있음</hp:t></hp:run></hp:p></hp:subList>
          <hp:cellAddr rowAddr="3" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="2"/>
        </hp:tc>
        <hp:tc><hp:subList><hp:p><hp:run><hp:t>□ 계획 없음</hp:t></hp:run></hp:p></hp:subList>
          <hp:cellAddr rowAddr="3" colAddr="2"/><hp:cellSpan rowSpan="1" colSpan="1"/>
        </hp:tc>
      </hp:tr>
    </hp:tbl></hp:run></hp:p>
    """
    src = tmp_path / "heading-column.hwpx"
    _hwpx(src, body)
    report = classify_protected_regions(index_hwpx_structure(src))
    assert report.auto_write_allowed_count == 0

    overview = [item for item in report.decisions if item.observed_text == "□ 기업개요 및 문제점"]
    strategy = [item for item in report.decisions if item.observed_text == "□ 성장전략"]
    assert overview and strategy
    assert all(item.role == "HEADING" and item.decision == "NO_TARGET" for item in overview + strategy)
    assert all(item.role != "CHOICE_MARK" for item in overview + strategy)

    owned = [item for item in report.decisions if item.observed_text == "□ 자가소유"]
    rented = [item for item in report.decisions if item.observed_text == "□ 임차사용"]
    assert owned and rented
    assert all(item.role == "CHOICE_MARK" and item.decision == "NO_TARGET" for item in owned + rented)

    yes = [item for item in report.decisions if item.observed_text == "□ 계획 있음"]
    no = [item for item in report.decisions if item.observed_text == "□ 계획 없음"]
    assert yes and no
    assert all(item.role == "CHOICE_MARK" and item.role != "HEADING" for item in yes + no)
    assert all(item.auto_write_allowed is False for item in report.decisions)


def test_choice_group_precedes_heading_keywords(tmp_path: Path) -> None:
    body = """
    <hp:p><hp:run><hp:tbl>
      <hp:tr>
        """ + _cell("수출 전략 보유 여부", 0, 0) + _cell("□ 전략 보유", 0, 1) + _cell("□ 전략 미보유", 0, 2) + """
      </hp:tr>
      <hp:tr>
        """ + _cell("□ 기업개요 및 문제점", 1, 0) + """
      </hp:tr>
      <hp:tr>
        """ + _cell("□ 성장전략", 2, 0) + """
      </hp:tr>
      <hp:tr>
        """ + _cell("□ 전략 미보유", 3, 2) + _cell("수출 전략 보유 여부", 3, 0) + _cell("□ 전략 보유", 3, 1) + """
      </hp:tr>
    </hp:tbl></hp:run></hp:p>
    """
    src = tmp_path / "strategy-choice.hwpx"
    _hwpx(src, body)
    report = classify_protected_regions(index_hwpx_structure(src))
    assert report.auto_write_allowed_count == 0
    paired = [item for item in report.decisions if item.observed_text in {"□ 전략 보유", "□ 전략 미보유"}]
    assert len(paired) == 4
    assert all(item.role == "CHOICE_MARK" and item.role != "HEADING" and item.decision == "NO_TARGET" for item in paired)
    overview = [item for item in report.decisions if item.observed_text == "□ 기업개요 및 문제점"]
    growth = [item for item in report.decisions if item.observed_text == "□ 성장전략"]
    assert overview and growth
    assert all(item.role == "HEADING" and item.decision == "NO_TARGET" for item in overview + growth)


def test_real_guidance_paragraph_is_not_an_empty_write_target() -> None:
    if not _REAL.is_file():
        pytest.skip("sample form is not in this workspace")
    index = index_hwpx_structure(_REAL)
    report = classify_protected_regions(index)
    assert report.auto_write_allowed_count == 0
    found = False
    for section in index.sections:
        for paragraph in section.paragraphs:
            if not paragraph.raw_text.strip().startswith("※"):
                continue
            found = True
            related = [
                item for item in report.decisions
                if item.section_index == paragraph.section_index
                and item.paragraph_index == paragraph.paragraph_index
            ]
            assert related
            assert all(item.decision == "NO_TARGET" and item.role == "GUIDANCE" for item in related)
            assert all(item.auto_write_allowed is False and item.field_label is None for item in related)
            assert any(item.observed_text.strip() for item in related)
            assert paragraph.raw_text.strip() != ""
    assert found
