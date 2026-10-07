"""test_resume_form_fill.py — 이력서 양식 반복행 채움(P2) 검증.

합성 HWPX(헤더행 + 빈 데이터행)로 다음을 증명한다: 반복행 순서 기입·빈 행 유지·
격자 검증 통과·원본 미수정·실값 셀 보존·헤더 없는 표 스킵·행 부족 캐스케이드(미수록
리포트)·섹션 인식(education/career/certs)·CLI fill 스모크(exit 0).
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.resume_fill_service import fill_resume_form
from auto_write.services.resume_form_map import map_form_sections

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _cell(col: int, row: int, text: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    )


def _table(headers: list[str], data_rows: list[list[str]]) -> str:
    """헤더행 1개 + 데이터행 N개짜리 OWPML 표. data_rows 각 원소는 열 값 리스트."""
    ncol = len(headers)
    rows = ["<hp:tr>" + "".join(_cell(c, 0, headers[c]) for c in range(ncol)) + "</hp:tr>"]
    for ri, dr in enumerate(data_rows, start=1):
        rows.append(
            "<hp:tr>"
            + "".join(_cell(c, ri, dr[c] if c < len(dr) else "") for c in range(ncol))
            + "</hp:tr>"
        )
    total = 1 + len(data_rows)
    return f'<hp:tbl rowCnt="{total}" colCnt="{ncol}">{"".join(rows)}</hp:tbl>'


def _section_xml(tables: list[str]) -> bytes:
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
    )
    for t in tables:
        body += f'<hp:p><hp:run charPrIDRef="0">{t}</hp:run></hp:p>'
    body += "</hs:sec>"
    return body.encode("utf-8")


_HEADER_XML = b'<?xml version="1.0"?><hh:head xmlns:hh="x">FONTS</hh:head>'
_MIMETYPE = b"application/hwp+zip"


def _make_hwpx(path: Path, tables: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("version.xml", b"<version/>")
        z.writestr("Contents/header.xml", _HEADER_XML)
        z.writestr("Contents/section0.xml", _section_xml(tables))


def _rows_texts(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    q = lambda t: f"{{{_HP}}}{t}"  # noqa: E731
    out = []
    for tr in root.iter(q("tr")):
        cells = [c for c in tr if c.tag == q("tc")]
        out.append(["".join(t.text or "" for t in c.iter(q("t"))).strip() for c in cells])
    return out


_CAREER_HDR = ["기간", "직장명", "직위", "담당업무"]


# --------------------------------------------------------------------------- #


def test_fill_career_rows_and_keep_extra_empty(tmp_path):
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [_table(_CAREER_HDR, [["", "", "", ""] for _ in range(3)])])
    before = hashlib.sha256(src.read_bytes()).hexdigest()

    out = tmp_path / "out.hwpx"
    prof = {"identity": {}, "career": [
        {"period": "2020.01~2022.12", "company": "가나회사", "position": "팀장", "duty": "기획"},
        {"period": "2018.01~2019.12", "company": "다라회사", "position": "대리", "duty": "영업"},
    ]}
    rep = fill_resume_form(src, out, prof)

    assert rep.ok is True
    rows = _rows_texts(out)
    assert rows[0] == _CAREER_HDR                       # 헤더 보존
    assert rows[1] == ["2020.01~2022.12", "가나회사", "팀장", "기획"]
    assert rows[2] == ["2018.01~2019.12", "다라회사", "대리", "영업"]
    assert rows[3] == ["", "", "", ""]                  # 세 번째 빈 행 유지
    # 원본 미수정
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    sec = [s for s in rep.sections if s["kind"] == "career"][0]
    assert sec["filled"] == 2 and sec["overflow"] == 0


def test_header_none_table_skipped():
    root = etree.fromstring(_section_xml([_table(["항목", "값"], [["", ""]])]))
    assert map_form_sections(root) == []


def test_row_shortage_cascades_to_residual(tmp_path):
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [_table(_CAREER_HDR, [["", "", "", ""] for _ in range(2)])])
    out = tmp_path / "out.hwpx"
    prof = {"career": [
        {"period": str(2010 + i), "company": f"회사{i}", "position": "직위", "duty": "업무"}
        for i in range(4)
    ]}
    rep = fill_resume_form(src, out, prof, identity_fill=False)

    sec = [s for s in rep.sections if s["kind"] == "career"][0]
    assert sec["filled"] == 2
    assert sec["overflow"] == 2
    assert len(rep.residual) == 2
    rows = _rows_texts(out)
    assert rows[1][1] == "회사0" and rows[2][1] == "회사1"


def test_real_value_row_preserved(tmp_path):
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [_table(_CAREER_HDR, [
        ["2000", "기존회사", "부장", "관리"],   # 실값 행 → 보존
        ["", "", "", ""],                       # 빈 행 → 채움
    ])])
    out = tmp_path / "out.hwpx"
    prof = {"career": [{"period": "2021", "company": "신규", "position": "사원", "duty": "개발"}]}
    rep = fill_resume_form(src, out, prof, identity_fill=False)

    assert rep.ok is True
    rows = _rows_texts(out)
    assert rows[1] == ["2000", "기존회사", "부장", "관리"]   # 덮어쓰기 금지
    assert rows[2] == ["2021", "신규", "사원", "개발"]


def test_map_recognizes_education_career_certs():
    tables = [
        _table(["기간", "학교명", "전공", "학위"], [["", "", "", ""]]),
        _table(_CAREER_HDR, [["", "", "", ""]]),
        _table(["취득일", "자격증명", "발급번호", "발급기관"], [["", "", "", ""]]),
    ]
    root = etree.fromstring(_section_xml(tables))
    secs = map_form_sections(root)
    assert [s.kind for s in secs] == ["education", "career", "certs"]
    edu = secs[0]
    assert set(edu.col_field_map.values()) == {"period", "school", "major", "degree"}
    certs = secs[2]
    assert set(certs.col_field_map.values()) == {"date", "name", "number", "issuer"}


def test_identity_and_rows_combined(tmp_path):
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [
        _table(["성명", ""], []),                    # 신상정보 라벨-값(헤더행만)
        _table(_CAREER_HDR, [["", "", "", ""]]),
    ])
    out = tmp_path / "out.hwpx"
    prof = {"identity": {"name": "홍길동"},
            "career": [{"period": "2020", "company": "A", "position": "P", "duty": "D"}]}
    rep = fill_resume_form(src, out, prof)

    assert rep.ok is True
    assert rep.identity_filled                       # 성명 채워짐
    rows = _rows_texts(out)
    assert rows[0] == ["성명", "홍길동"]
    # career 표(두 번째 표) 채움
    assert ["2020", "A", "P", "D"] in rows


def test_cli_fill_smoke(tmp_path):
    from resume_fill import main

    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [_table(_CAREER_HDR, [["", "", "", ""] for _ in range(2)])])
    prof_path = tmp_path / "profile.json"
    prof_path.write_text(json.dumps(
        {"identity": {}, "career": [
            {"period": "2020", "company": "A", "position": "P", "duty": "D"}]},
        ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out.hwpx"

    rc = main(["fill", str(src), "--profile", str(prof_path), "-o", str(out)])
    assert rc == 0
    assert out.exists()


def test_fill_rejects_overwrite_original(tmp_path):
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [_table(_CAREER_HDR, [["", "", "", ""]])])
    try:
        fill_resume_form(src, src, {"career": []})
    except ValueError:
        pass
    else:
        raise AssertionError("out==in 인데 ValueError 가 발생하지 않았습니다.")


def test_multi_table_same_kind_no_false_residual(tmp_path):
    """같은 kind(career) 표가 2개면 뒤 표가 이어 채우고 채운 항목을 '미수록'으로
    거짓 신고하지 않는다(표 단위 이중계산 방지)."""
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [
        _table(_CAREER_HDR, [["", "", "", ""] for _ in range(2)]),   # 표 A: 빈행 2
        _table(_CAREER_HDR, [["", "", "", ""] for _ in range(2)]),   # 표 B: 빈행 2
    ])
    out = tmp_path / "out.hwpx"
    prof = {"career": [
        {"period": str(2010 + i), "company": f"회사{i}", "position": "직위", "duty": "업무"}
        for i in range(4)
    ]}
    rep = fill_resume_form(src, out, prof, identity_fill=False)
    assert sum(s["filled"] for s in rep.sections) == 4
    assert rep.residual == []                              # 미수록 거짓경고 없음
    rows = _rows_texts(out)
    filled = [r[1] for r in rows if r[1].startswith("회사")]
    assert filled == ["회사0", "회사1", "회사2", "회사3"]


def test_trainings_reported_as_residual(tmp_path):
    """L046 연계: 교육수료(trainings)는 자격 표에 자동 기입하지 않고 미수록으로 명시."""
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [_table(["취득일", "자격증명", "발급번호", "발급기관"], [["", "", "", ""]])])
    out = tmp_path / "out.hwpx"
    prof = {
        "certs": [{"date": "2020", "name": "정보처리기사", "number": "1", "issuer": "산인공"}],
        "trainings": [{"date": "2019", "name": "투자심사역 과정 이수",
                       "number": None, "issuer": "한국VC협회"}],
    }
    rep = fill_resume_form(src, out, prof, identity_fill=False)
    assert any("교육수료" in r and "투자심사역" in r for r in rep.residual)
    names = [r[1] for r in _rows_texts(out)]
    assert "정보처리기사" in names
    assert not any("투자심사역" in n for n in names)   # 자격 표에 미기입


def test_cli_fill_identity_only_exit0(tmp_path):
    """반복행 표 없이 신상정보만 채우는 양식도 채움 성공이면 exit 0."""
    from resume_fill import main

    src = tmp_path / "form.hwpx"
    _make_hwpx(src, [_table(["성명", ""], [])])          # 신상 라벨-값만, 반복행 표 없음
    prof_path = tmp_path / "p.json"
    prof_path.write_text(json.dumps({"identity": {"name": "홍길동"}}, ensure_ascii=False),
                         encoding="utf-8")
    out = tmp_path / "out.hwpx"
    rc = main(["fill", str(src), "--profile", str(prof_path), "-o", str(out)])
    assert rc == 0
    assert out.exists()
