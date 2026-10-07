"""PR #211 Round-3: 합성 HWPX의 실제 채움/제출 경로 회귀."""
from pathlib import Path

import pytest

from auto_write.services.hwpx_fill import fill_hwpx
from auto_write.services.hwpx_submit import submit_hwpx
from test_hwpx_round2_fill import _cell, _root, _row, _run, _sec, _tables, _write, _P


@pytest.fixture(autouse=True)
def no_external_pdf(monkeypatch):
    # 합성 XML 회귀가 실 한글을 기동하지 않도록 외부 exporter만 차단한다.
    monkeypatch.setattr("core.docx.services.hwp_docx_convert.hancom_com_available", lambda: False)


def test_dips_mixed_example_guidance_and_date(tmp_path: Path):
    guidance = "(법인등기부등본 및 사업자등록증 상의 본사(점) 명칭과 동일하게 기입)"
    rows = (
        '<hp:tr>' + _cell(0, 0, _run("기업명"))
        + _cell(1, 0, _run("OOOOO", "34") + _run(" " + guidance, "34")) + '</hp:tr>'
        + _row(1, "사업장 소재지", "OO도 OO시·군")
        + _row(2, "개업연월일", "0000년 00월 00일")
    )
    src, out = tmp_path / "dips.hwpx", tmp_path / "out.hwpx"
    _write(src, _sec(f'<hp:p>{_run("별도 안내는 유지")}</hp:p><hp:p><hp:run>'
                    f'<hp:tbl rowCnt="3" colCnt="2">{rows}</hp:tbl></hp:run></hp:p>'))
    original = src.read_bytes()
    report = fill_hwpx(src, out, identity={"기업명": "검증회사", "주소": "서울시 검증로 1", "설립일": "2020-01-15"})
    assert _tables(out)[0] == [["기업명", "검증회사"], ["사업장 소재지", "서울시 검증로 1"], ["개업연월일", "2020-01-15"]]
    assert len(report.filled) == 3
    assert "별도 안내는 유지" in "".join(_root(out).itertext())
    assert guidance not in "".join(_root(out).itertext())
    assert src.read_bytes() == original


def test_onlab_explicit_examples_and_oath_blank(tmp_path: Path):
    rows = ''.join(_row(i, label, example) for i, (label, example) in enumerate([
        ("팀명", "예시) 앙트프러너십팀"), ("휴대전화", "예) 010-1234-5678"),
        ("E-mail", "예시: sample@example.com"), ("주소", "예) 서울시 강남구 예시로 1"),
    ]))
    src, out = tmp_path / "onlab.hwpx", tmp_path / "out.hwpx"
    _write(src, _sec(f'<hp:p><hp:run><hp:tbl rowCnt="4" colCnt="2">{rows}</hp:tbl></hp:run></hp:p>'
                    f'<hp:p>{_run("팀 명 :")}</hp:p>'))
    report = submit_hwpx(src, out, identity={"팀명": "검증팀", "연락처": "010-2222-3333", "이메일": "check@example.com", "주소": "부산시 검증로 2"},
                         preserve_template=True, normalize_colors=False, submission_cleanup=False)
    final = Path(report.final)
    assert _tables(final)[0] == [["팀명", "검증팀"], ["휴대전화", "010-2222-3333"], ["E-mail", "check@example.com"], ["주소", "부산시 검증로 2"]]
    assert "팀 명 : 검증팀" in "".join(_root(final).itertext())


@pytest.mark.parametrize("value", ["GOOGLE", "앙트프러너십팀", "real@example.com", "OOOOO 실제회사 기입완료"])
def test_round3_real_values_are_preserved(tmp_path: Path, value: str):
    src, out = tmp_path / "real.hwpx", tmp_path / "out.hwpx"
    _write(src, _sec(f'<hp:p><hp:run><hp:tbl rowCnt="1" colCnt="2">{_row(0, "기업명", value)}</hp:tbl></hp:run></hp:p>'))
    report = fill_hwpx(src, out, identity={"기업명": "새회사"})
    assert report.filled == {}
    assert _tables(out)[0][0][1] == value
