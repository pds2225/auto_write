# -*- coding: utf-8 -*-
"""P1-1: only a unique label plus a completely empty cell may be written."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import find_t02_auto_targets

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_DATA = Path(__file__).resolve().parents[2] / "data"
_TEN = (
    "(서식09) 연구개발기관 대표의 참여의사 확인서_접수번호(기관명).hwpx",
    "(참여신청서, 개인정보동의서) 서울창업허브 성수, 창동×홈앤쇼핑 오픈이노베이션.hwpx",
    "2025전담PM(자기기술서).hwpx",
    "(첨부3) 성장촉진자금(자동화설비) 신청 자가진단표.hwpx",
    "(별첨1) 2024년도 창업중심대학 예비창업자 사업계획서 양식.hwpx",
    "(붙임2) 신용취약소상공인자금 신청 서식.hwpx",
    "3. SBA 액셀러레이팅 정보 수집 및 이용 동의서 양식(2023년).hwpx",
    "(공고)2024년 2030청년창업프로젝트 초기유형 모집 공고문.hwpx",
    "(필수) 2. 연구개발계획서 본문1.hwpx",
    "2026년도 SaaS 개발환경 지원 수요기업 신청서.hwpx",
)
_PASS = {_TEN[0], _TEN[1]}
_UNSAFE = ("해당", "여", "부", "예", "아니오", "확인")


def _hwpx(path: Path, section: str) -> None:
    hpf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", b"<hh:head>LOCKED</hh:head>")
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", hpf.encode("utf-8"))


def _cell(text: str, row: int, col: int, *, runs: int = 1) -> str:
    bodies = "".join("<hp:run><hp:t></hp:t></hp:run>" for _ in range(runs)) if text == "" and runs > 1 else ""
    if text == "" and runs == 1:
        bodies = "<hp:run></hp:run>"
    if text != "":
        bodies = f"<hp:run><hp:t>{text}</hp:t></hp:run>"
    return (
        "<hp:tc><hp:subList><hp:p>"
        + bodies
        + "</hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + '<hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def test_analyzer_candidate_is_not_written_without_authorization(tmp_path: Path) -> None:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}"><hp:p><hp:run><hp:tbl><hp:tr>'
        + _cell("기업명", 0, 0) + _cell("", 0, 1)
        + "</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>"
    )
    src = tmp_path / "t02.hwpx"
    _hwpx(src, section)
    index = index_hwpx_structure(src)
    targets = find_t02_auto_targets(index)
    assert [item.field_label for item in targets] == ["기업명"]
    from core.docx.services.hwpx_protected_regions import assess_fields, authorize_t02_writes
    assessed = [item for item in assess_fields(index) if item.field_label == "기업명"]
    assert assessed and assessed[0].eligible is True and assessed[0].auto_write_allowed is False
    assert assessed[0].decision == "REVIEW_REQUIRED"
    grants = authorize_t02_writes(index)
    assert [item.field_label for item in grants] == ["기업명"]
    assert grants[0].source_sha256 == index.source_sha256
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"기업명": "도보네비"})
    assert report.ok is True and dst.is_file()
    assert _texts(dst)[0] == "기업명"
    assert "도보네비" in _texts(dst)
    refused = tmp_path / "refused.hwpx"
    missed = commit_t02_label_writes(src, refused, {"없는필드": "값"})
    assert missed.ok is False and not refused.exists()


def _table(body: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"<hp:p><hp:run><hp:tbl>{body}</hp:tbl></hp:run></hp:p></hs:sec>"
    )


def test_unsafe_t02_shapes_are_not_auto(tmp_path: Path) -> None:
    spanned = (
        "<hp:tc><hp:subList><hp:p><hp:run><hp:t>대표</hp:t></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="7" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
        "<hp:tc><hp:subList><hp:p><hp:run></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="7" colAddr="1"/><hp:cellSpan rowSpan="2" colSpan="1"/></hp:tc>'
        "</hp:tr><hp:tr>"
        "<hp:tc><hp:subList><hp:p><hp:run><hp:t>총괄</hp:t></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="8" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )
    section = _table(
        "<hp:tr>" + _cell("참고", 0, 0) + _cell("", 0, 1) + _cell("※ 본 페이지는 삭제 후 제출", 0, 2) + "</hp:tr>"
        "<hp:tr>" + _cell("대", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("식", 2, 0) + _cell("", 2, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("2024년", 3, 0) + _cell("", 3, 1) + _cell("월", 3, 2) + _cell("", 3, 3) + _cell("일", 3, 4) + "</hp:tr>"
        "<hp:tr>" + _cell("◯ 동의   ◯ 비동의", 4, 0) + _cell("", 4, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("개인정보 수집 동의서", 5, 0) + _cell("", 5, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("부서명", 6, 0) + _cell("", 6, 1) + "</hp:tr>"
        "<hp:tr>" + spanned + "</hp:tr>"
    )
    src = tmp_path / "unsafe-shapes.hwpx"
    _hwpx(src, section)
    index = index_hwpx_structure(src)
    assert index.analysis_status == "COMPLETE"
    targets = find_t02_auto_targets(index)
    labels = [item.field_label for item in targets]
    assert "부서명" in labels
    assert "참고" not in labels
    assert "대" not in labels and "식" not in labels
    assert "2024년" not in labels and "월" not in labels and "일" not in labels
    assert not any("동의" in item for item in labels)
    assert "대표" not in labels and "총괄" not in labels
    keys = [(item.table_index, item.row, item.col) for item in targets]
    assert len(keys) == len(set(keys))


def test_unsafe_shapes_are_not_t02(tmp_path: Path) -> None:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        "<hp:p><hp:run><hp:t>성 명 : (서명)</hp:t></hp:run></hp:p>"
        "<hp:p><hp:run><hp:t>※ 작성 안내</hp:t></hp:run></hp:p>"
        "<hp:p><hp:run><hp:tbl>"
        "<hp:tr>" + _cell("해당", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("기업명", 1, 0) + _cell("", 1, 1, runs=2) + "</hp:tr>"
        "</hp:tbl></hp:run></hp:p></hs:sec>"
    )
    src = tmp_path / "unsafe.hwpx"
    _hwpx(src, section)
    targets = find_t02_auto_targets(index_hwpx_structure(src))
    assert targets == ()
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"기업명": "도보네비", "성명": "홍길동"})
    assert report.ok is False and not dst.exists()


def test_guidance_titles_are_not_t02_and_note_fields_stay(tmp_path: Path) -> None:
    """Section titles drop out. A single empty value cell beside a notes label stays."""
    section = _table(
        "<hp:tr>" + _cell("참고 9-1", 0, 0) + _cell("", 0, 1) + _cell("민간주도형 청년창업사관학교 사업 개요", 0, 2) + "</hp:tr>"
        "<hp:tr>" + _cell("참 고", 1, 0) + _cell("", 1, 1) + _cell("국세청 세정지원 내용", 1, 2) + "</hp:tr>"
        "<hp:tr>" + _cell("참고사항", 2, 0) + _cell("", 2, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("작성 요령", 3, 0) + _cell("", 3, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("사업안내", 4, 0) + _cell("", 4, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("유의사항", 5, 0) + _cell("", 5, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("유의사항 및 문의처", 6, 0) + _cell("", 6, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("예시 1", 7, 0) + _cell("", 7, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("기업명", 8, 0) + _cell("", 8, 1) + _cell("", 8, 2) + "</hp:tr>"
        "<hp:tr>" + _cell("성과목표 작성요령", 9, 0) + _cell("", 9, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("지원 대상 참고 사항", 10, 0) + _cell("", 10, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("(예시) 미세먼지 밀도 저감", 11, 0) + _cell("", 11, 1) + "</hp:tr>"
    )
    src = tmp_path / "guidance-titles.hwpx"
    _hwpx(src, section)
    labels = [item.field_label for item in find_t02_auto_targets(index_hwpx_structure(src))]
    assert labels == ["참고사항", "유의사항", "기업명", "지원대상참고사항"]


def test_consent_and_pledge_labels_are_not_t02(tmp_path: Path) -> None:
    """Bare 동의/확약/서약 block consent text. Department and notes labels stay."""
    section = _table(
        "<hp:tr>" + _cell("과제사업계획서작성투자동의", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("동의하지않음", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("이행확약서", 2, 0) + _cell("", 2, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("청렴서약", 3, 0) + _cell("", 3, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("부서명", 4, 0) + _cell("", 4, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("겸직인력현황", 5, 0) + _cell("", 5, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("기업명", 6, 0) + _cell("", 6, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("성명", 7, 0) + _cell("", 7, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("주소", 8, 0) + _cell("", 8, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("참고사항", 9, 0) + _cell("", 9, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("유의사항", 10, 0) + _cell("", 10, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("지원대상참고사항", 11, 0) + _cell("", 11, 1) + "</hp:tr>"
    )
    src = tmp_path / "consent.hwpx"
    _hwpx(src, section)
    labels = [item.field_label for item in find_t02_auto_targets(index_hwpx_structure(src))]
    assert labels == [
        "부서명", "겸직인력현황", "기업명", "성명", "주소",
        "참고사항", "유의사항", "지원대상참고사항",
    ]


def test_real_validation_set_keeps_unsafe_auto_at_zero(tmp_path: Path) -> None:
    present = [name for name in _TEN if (_DATA / name).is_file()]
    assert len(present) == 10
    for name in present:
        targets = find_t02_auto_targets(index_hwpx_structure(_DATA / name))
        assert all(item.field_label not in _UNSAFE for item in targets)
        assert all("※" not in item.field_label and "(서명)" not in item.field_label for item in targets)
        assert all(not item.field_label.isdigit() for item in targets)
        if name in _PASS:
            assert targets
    src = tmp_path / "copy.hwpx"
    shutil.copyfile(_DATA / _TEN[0], src)
    before = src.read_bytes()
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(src, dst, {"연구개발과제번호": "AB-1"})
    assert src.read_bytes() == before
    from core.docx.services.hwpx_protected_regions import authorize_t02_writes
    granted = any(item.field_label == "연구개발과제번호" for item in authorize_t02_writes(index_hwpx_structure(src)))
    if granted:
        assert report.ok is True and dst.is_file()
    else:
        assert report.ok is False and not dst.exists()


def test_p1_t02_keeps_only_a_simple_body_cell(tmp_path: Path) -> None:
    from dataclasses import replace
    from core.docx.services.hwpx_protected_regions import assess_fields, t02_write_authorized
    merged = (
        "<hp:tc><hp:subList><hp:p><hp:run><hp:t>병합값</hp:t></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="1" colAddr="0"/><hp:cellSpan rowSpan="2" colSpan="1"/></hp:tc>'
        "<hp:tc><hp:subList><hp:p><hp:run></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="2" colSpan="1"/></hp:tc>'
    )
    wide = (
        "<hp:tr>" + _cell("넓은주소", 3, 0)
        + "<hp:tc><hp:subList><hp:p><hp:run></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="3" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="2"/></hp:tc></hp:tr>'
    )
    nested = (
        "<hp:tr>" + _cell("겉라벨", 8, 0) +
        "<hp:tc><hp:subList><hp:p><hp:run><hp:tbl><hp:tr>"
        + _cell("속기업명", 0, 0) + _cell("", 0, 1) +
        "</hp:tr></hp:tbl></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="8" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc></hp:tr>'
    )
    repeated = (
        "<hp:tr>" + _cell("수행내용", 4, 0) + _cell("", 4, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("", 5, 0) + _cell("", 5, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("", 6, 0) + _cell("", 6, 1) + "</hp:tr>"
    )
    section = _table(
        "<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        + "<hp:tr>" + merged + "</hp:tr>"
        + nested
        + wide
        + repeated
        + "<hp:tr>" + _cell("삭제 후 작성", 7, 0) + _cell("", 7, 1) + "</hp:tr>"
    )
    src = tmp_path / "scope.hwpx"
    _hwpx(src, section)
    index = index_hwpx_structure(src)
    labels = [item.field_label for item in find_t02_auto_targets(index)]
    assert labels == ["기업명"]
    fields = [item for item in assess_fields(index) if item.field_type == "T02" and item.eligible]
    assert [(item.field_label, item.row_span, item.col_span) for item in fields] == [("기업명", 1, 1)]
    wide_cell = next(cell for cell in index.tables[0].cells if cell.col_span == 2)
    assert wide_cell.row_span == 1 and wide_cell.col_span == 2
    assert not any(item.field_label == "넓은주소" for item in fields)
    assert fields[0].decision == "REVIEW_REQUIRED" and fields[0].auto_write_allowed is False
    plain = next(item for item in fields if item.field_label == "기업명")
    forged = replace(plain, table_index=99, auto_write_allowed=True, decision="AUTHORIZED")
    assert plain.auto_write_allowed is False
    assert t02_write_authorized(index, plain) is True
    assert t02_write_authorized(index, forged) is False
    from core.docx.services.hwpx_protected_regions import authorization_is_current, authorize_t02_writes
    grant = authorize_t02_writes(index)[0]
    assert authorization_is_current(index, grant) is True
    assert authorization_is_current(index, replace(grant, source_sha256="0" * 64)) is False
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"기업명": "도보네비", "병합값": "침범"})
    assert report.ok is False and not dst.exists()


def test_ambiguous_guidance_and_repeated_rows_are_not_t02(tmp_path: Path) -> None:
    from core.docx.services.hwpx_protected_regions import assess_fields
    ambiguous = _table(
        "<hp:tr>" + _cell("기재요령 관련 안내사항", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("기업명", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
    )
    src = tmp_path / "ambiguous.hwpx"
    _hwpx(src, ambiguous)
    index = index_hwpx_structure(src)
    labels = [item.field_label for item in find_t02_auto_targets(index)]
    assert labels == ["기업명"]
    fields = assess_fields(index)
    ambiguous_fields = [item for item in fields if item.protection_role == "AMBIGUOUS"]
    assert ambiguous_fields
    assert all(item.eligible is False and item.auto_write_allowed is False for item in ambiguous_fields)
    repeated = _table(
        "<hp:tr>" + _cell("직원명", 0, 0) + _cell("부서", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("홍길동", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("김영희", 2, 0) + _cell("", 2, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("이철수", 3, 0) + _cell("", 3, 1) + "</hp:tr>"
    )
    repeated_path = tmp_path / "repeated.hwpx"
    _hwpx(repeated_path, repeated)
    assert find_t02_auto_targets(index_hwpx_structure(repeated_path)) == ()


def test_noncandidate_assessment_keeps_cell_structure(tmp_path: Path) -> None:
    from core.docx.services.hwpx_protected_regions import assess_fields
    merged = (
        "<hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:t>병합라벨</hp:t></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="2" colSpan="3"/></hp:tc></hp:tr>'
    )
    invalid = (
        "<hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:t>깨진칸</hp:t></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="-1" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc></hp:tr>'
    )
    src = tmp_path / "structure.hwpx"
    _hwpx(src, _table(merged + invalid))
    index = index_hwpx_structure(src)
    fields = assess_fields(index)
    merged_field = next(item for item in fields if item.row_span == 2)
    assert (merged_field.row, merged_field.col, merged_field.col_span) == (0, 0, 3)
    assert merged_field.story_scope == "body"
    assert merged_field.address_status == "PRESENT"
    assert merged_field.physical_tr_index == 0
    assert merged_field.eligible is False
    invalid_field = next(item for item in fields if item.address_status == "INVALID")
    assert invalid_field.row is None and invalid_field.col is None
    assert invalid_field.span_status == "PRESENT"
