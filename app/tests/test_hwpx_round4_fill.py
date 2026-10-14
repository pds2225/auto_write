"""Round-4 실양식 실패 A~G를 합성 HWPX로 재현한다."""
from pathlib import Path
import zipfile

import pytest

from auto_write.models import ProjectInput
from auto_write.services.company_identity import build_direct_fill_identity
from auto_write.services.hwpx_fill import fill_hwpx
from auto_write.services.hwpx_submit import submit_hwpx
from test_hwpx_round2_fill import _cell, _run, _row, _sec, _write, _tables


def _form(tmp_path, rows, *, after="", columns=2):
    src = tmp_path / "form.hwpx"
    _write(src, _sec(
        '<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="{len(rows)}" colCnt="{columns}">{"".join(rows)}</hp:tbl>'
        '</hp:run></hp:p>' + after
    ))
    return src


@pytest.mark.parametrize("label,key,parts,value", [
    ("기업명", "기업명", ["OOOOO", " (법인등기부등본 및 사업자등록증 상의 본사(점) 명칭과 동일하게 기입)"], "테스트주식회사"),
    ("개업연월일", "설립일", ["0000년 00월 00일", "사업자등록증 상의 개업연월일 기준으로 작성"], "2020-01-15"),
    ("주소", "주소", ["서울시 예시구", " 예시로 1"], "서울특별시 테스트구 테스트로 123"),
    ("업태", "업종", ["ex) ", "소프트웨어개발공급…"], "정보서비스업"),
])
def test_round4_mixed_example_and_guidance_cells(tmp_path, label, key, parts, value):
    row = '<hp:tr>' + _cell(0, 0, _run(label)) + _cell(1, 0, ''.join(_run(t, "34") for t in parts)) + '</hp:tr>'
    src = _form(tmp_path, [row, _row(1, "안내", "다른 칸 안내 유지", "2")])
    original = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(src, out, identity={key: value}, force_black=False)
    assert _tables(out)[0] == [[label, value], ["안내", "다른 칸 안내 유지"]]
    assert report.filled[key] == value
    assert src.read_bytes() == original


def test_round4_guidance_does_not_replace_actual_dates_or_black_address(tmp_path):
    src = _form(tmp_path, [
        _row(0, "개업연월일", "2020년 01월 15일 사업자등록증 기준", "0"),
        _row(1, "주소", "서울특별시 강남구 테헤란로 1", "0"),
        _row(2, "업태", "이미 작성된 업태", "0"),
    ])
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity={"설립일": "2021-02-03", "주소": "새주소", "업종": "새업태"})
    assert _tables(out) == _tables(src)


@pytest.mark.parametrize("pledge", ["서약서", "확약서"])
def test_round4_pledge_reuses_team_after_applicant_table(tmp_path, pledge):
    src = _form(tmp_path, [_row(0, "팀명", "", "0")], after=
        f'<hp:p>{_run(pledge)}</hp:p><hp:p>{_run("팀 명 :")}</hp:p>'
    )
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity={"팀명": "테스트팀"}, force_black=False)
    xml = zipfile.ZipFile(out).read("Contents/section0.xml").decode()
    assert _tables(out)[0][0] == ["팀명", "테스트팀"]
    assert "팀 명 : 테스트팀" in xml


def test_round4_same_table_does_not_repeat_colon_value(tmp_path):
    src = _form(tmp_path, [_row(0, "팀명", "", "0"),
        '<hp:tr>' + _cell(0, 1, _run("팀 명 :")) + _cell(1, 1, _run("")) + '</hp:tr>'])
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity={"팀명": "테스트팀"})
    assert _tables(out)[0][1] == ["팀 명 :", ""]


@pytest.mark.parametrize("profile_key", ["사업 개요", "사업개요", "아이템 설명", "business_overview", "item_description"])
def test_round4_profile_overview_fills_synthetic_hwpx(tmp_path, profile_key):
    src = _form(tmp_path, [_row(0, "창업아이템 개요", "", "0")])
    identity = build_direct_fill_identity(ProjectInput(
        template_id="synthetic", organization_profile={profile_key: "사용자가 입력한 사업 설명"}
    ))
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity=identity)
    assert _tables(out)[0][0] == ["창업아이템 개요", "사용자가 입력한 사업 설명"]


@pytest.mark.parametrize("headers,expected", [
    (["(3년전)", "(2년전)", "전년", "현재"], 4),
    (["현재", "전년", "(2년전)", "(3년전)"], 1),
    (["(3년전)", "(2년전)", "전년"], None),
    (["2023년", "2024년", "2025년"], None),
    (["(3년전)", "(2년전)", "(전년)", "(현재)"], 4),
])
def test_round4_employee_count_only_in_current_period(tmp_path, headers, expected):
    rows = ['<hp:tr>' + _cell(0, 0, _run("구분")) + ''.join(_cell(i, 0, _run(h)) for i,h in enumerate(headers, 1)) + '</hp:tr>',
        '<hp:tr>' + _cell(0, 1, _run("종업원수")) + ''.join(_cell(i, 1, _run("")) for i in range(1,len(headers)+1)) + '</hp:tr>']
    src = _form(tmp_path, rows, columns=len(headers)+1)
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(src, out, identity={"직원수": "12명"})
    data = _tables(out)[0][1]
    if expected is None:
        # Round-5: 과거 값 칸에 현재 인원수를 쓰던 기대를 비훼손 검사로 강화한다.
        assert _tables(out) == _tables(src)
        assert report.filled == {}
        assert all(value == "" for value in data[1:])
        assert any("PAST_PERIOD_ONLY" in note for note in report.notes)
        return
    assert data[expected] == "12명"
    assert [v for v in data[1:] if v] == ["12명"]


def test_round4_ambiguous_current_period_is_not_filled(tmp_path):
    src = _form(tmp_path, [
        '<hp:tr>' + _cell(0,0,_run("구분")) + _cell(1,0,_run("현재")) + _cell(2,0,_run("현재")) + '</hp:tr>',
        '<hp:tr>' + _cell(0,1,_run("종업원수")) + _cell(1,1,_run("")) + _cell(2,1,_run("")) + '</hp:tr>',
    ], columns=3)
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity={"직원수": "12명"})
    assert _tables(out) == _tables(src)


@pytest.mark.parametrize("employee_key", ["직원수", "종업원수"])
def test_round4_submit_preserves_team_reuse_and_current_period(tmp_path, employee_key):
    src = _form(tmp_path, [_row(0, "팀명", "", "0")], after=
        f'<hp:p>{_run("서약서")}</hp:p><hp:p>{_run("팀 명 :")}</hp:p>'
        '<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="2" colCnt="3">'
        '<hp:tr>' + _cell(0,0,_run("구분")) + _cell(1,0,_run("(3년전)")) + _cell(2,0,_run("현재")) + '</hp:tr>'
        '<hp:tr>' + _cell(0,1,_run("종업원수")) + _cell(1,1,_run("")) + _cell(2,1,_run("")) + '</hp:tr>'
        '</hp:tbl></hp:run></hp:p>'
    )
    report = submit_hwpx(src, tmp_path / "out.hwpx", identity={"팀명": "테스트팀", employee_key: "12명"},
        acceptance_gate=False, preserve_template=True, submission_cleanup=False, normalize_colors=False)
    result = Path(report.final)
    xml = zipfile.ZipFile(result).read("Contents/section0.xml").decode()
    assert "팀 명 : 테스트팀" in xml
    assert _tables(result)[1][1] == ["종업원수", "", "12명"]


def test_round4_submit_exact_label_ambiguous_period_does_not_write(tmp_path):
    src = _form(tmp_path, [
        '<hp:tr>' + _cell(0,0,_run("구분")) + _cell(1,0,_run("현재")) + _cell(2,0,_run("현재")) + '</hp:tr>',
        '<hp:tr>' + _cell(0,1,_run("종업원수")) + _cell(1,1,_run("")) + _cell(2,1,_run("")) + '</hp:tr>',
    ], columns=3)
    report = submit_hwpx(src, tmp_path / "out.hwpx", identity={"종업원수": "12명"},
        acceptance_gate=False, preserve_template=True, submission_cleanup=False, normalize_colors=False)
    assert _tables(Path(report.final)) == _tables(src)


def test_round4_submit_keeps_same_table_team_colon_empty(tmp_path):
    src = _form(tmp_path, [_row(0, "팀명", "", "0"),
        '<hp:tr>' + _cell(0,1,_run("팀 명 :")) + _cell(1,1,_run("")) + '</hp:tr>'])
    report = submit_hwpx(src, tmp_path / "out.hwpx", identity={"팀명": "테스트팀"},
        acceptance_gate=False, preserve_template=True, submission_cleanup=False, normalize_colors=False)
    assert _tables(Path(report.final))[0][1] == ["팀 명 :", ""]


@pytest.mark.parametrize("other_value", ["", "12명"])
def test_round4_period_routing_does_not_bypass_other_table_duplicate(tmp_path, other_value):
    src = _form(tmp_path, [
        '<hp:tr>' + _cell(0,0,_run("구분")) + _cell(1,0,_run("전년")) + _cell(2,0,_run("현재")) + '</hp:tr>',
        '<hp:tr>' + _cell(0,1,_run("직원수")) + _cell(1,1,_run("")) + _cell(2,1,_run("")) + '</hp:tr>',
    ], columns=3, after=
        '<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="2">'
        + _row(0, "직원수", other_value, "0") + '</hp:tbl></hp:run></hp:p>')
    report = submit_hwpx(src, tmp_path / "out.hwpx", identity={"직원수": "12명"},
        acceptance_gate=False, preserve_template=True, submission_cleanup=False, normalize_colors=False)
    assert _tables(Path(report.final))[0][1][1] == ""


def test_round4_single_current_word_does_not_reroute_protected_address(tmp_path):
    src = _form(tmp_path, [_row(0, "주소", "실제주소", "0"), _row(1, "메모", "현재", "0")])
    report = submit_hwpx(src, tmp_path / "out.hwpx", identity={"주소": "새주소"},
        acceptance_gate=False, preserve_template=True, submission_cleanup=False, normalize_colors=False)
    assert _tables(Path(report.final)) == _tables(src)


def test_round4_submit_reads_profile_item_description(tmp_path):
    src = _form(tmp_path, [_row(0, "창업아이템 개요", "", "0")])
    identity = build_direct_fill_identity(ProjectInput(template_id="synthetic",
        organization_profile={"item_description": "프로필에 저장한 아이템 설명"}))
    report = submit_hwpx(src, tmp_path / "out.hwpx", identity=identity,
        acceptance_gate=False, preserve_template=True, submission_cleanup=False, normalize_colors=False)
    assert _tables(Path(report.final))[0][0] == ["창업아이템 개요", "프로필에 저장한 아이템 설명"]
