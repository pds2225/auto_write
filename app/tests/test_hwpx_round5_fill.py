"""Round-5: 늦은 기간 헤더·병합 열과 괄호 안내문의 실제 ZIP 채움 회귀."""
from datetime import date
from pathlib import Path
import zipfile

from lxml import etree
import pytest

from auto_write.models import ProjectInput
from auto_write.services.company_identity import build_direct_fill_identity
from core.docx.services.hwpx_fill import fill_hwpx, _is_hwpx_guidance_placeholder
from test_hwpx_round2_fill import _cell, _run, _sec, _write, _tables


def _merged(col, row, text, span=1):
    return _cell(col, row, _run(text)).replace('colSpan="1"', f'colSpan="{span}"')


def _fill(tmp_path, headers, values, identity, header_row=3):
    rows = [f'<hp:tr>{_merged(0, i, "양식 안내", 7)}</hp:tr>' for i in range(header_row)]
    rows += ['<hp:tr>' + _merged(0, header_row, '구분') + ''.join(
        _merged(col, header_row, text, span) for col, span, text in headers
    ) + '</hp:tr>']
    rows += ['<hp:tr>' + _merged(0, header_row+1, '종업원수') + ''.join(
        _merged(col, header_row+1, text, span) for col, span, text in values
    ) + '</hp:tr>']
    src, out = tmp_path / 'source.hwpx', tmp_path / 'filled.hwpx'
    _write(src, _sec(f'<hp:p><hp:run><hp:tbl rowCnt="{header_row+2}" colCnt="7">'
                     + ''.join(rows) + '</hp:tbl></hp:run></hp:p>'))
    original = src.read_bytes()
    report = fill_hwpx(src, out, identity=identity, force_black=False)
    assert src.read_bytes() == original
    with zipfile.ZipFile(src) as before, zipfile.ZipFile(out) as after:
        for name in before.namelist():
            if name != 'Contents/section0.xml':
                assert before.read(name) == after.read(name)
        ns = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}
        old = etree.fromstring(before.read('Contents/section0.xml'))
        new = etree.fromstring(after.read('Contents/section0.xml'))
        assert old.xpath('//hp:cellSpan/@colSpan', namespaces=ns) == new.xpath('//hp:cellSpan/@colSpan', namespaces=ns)
        assert old.xpath('//hp:cellAddr/@colAddr', namespaces=ns) == new.xpath('//hp:cellAddr/@colAddr', namespaces=ns)
    return src, out, report


@pytest.mark.parametrize('current', ['올해(예상)', '올해', '금년', '현재'])
def test_fourth_row_merged_current_header_writes_only_its_merged_cell(tmp_path, current):
    src, out, report = _fill(tmp_path,
        [(1, 2, '(3년전)'), (3, 2, current), (5, 2, '작년')],
        [(1, 2, ''), (3, 2, ''), (5, 2, '')], {'직원수': '12명'})
    assert _tables(out)[0][4] == ['종업원수', '', '12명', '']
    assert _tables(out)[0][:4] == _tables(src)[0][:4]
    assert report.filled['직원수'] == '12명'


@pytest.mark.parametrize('header_row', [0, 3])
def test_absolute_current_year_is_selected_even_when_old_year_is_on_right(tmp_path, header_row):
    year = date.today().year
    _, out, report = _fill(tmp_path,
        [(1, 2, f'{year}년'), (3, 2, f'{year-2}년'), (5, 2, f'{year-1}년')],
        [(1, 2, ''), (3, 2, ''), (5, 2, '')], {'직원수': '12명'}, header_row=header_row)
    assert _tables(out)[0][-1] == ['종업원수', '12명', '', '']
    assert report.filled['직원수'] == '12명'


@pytest.mark.parametrize('headers', [
    [(1, 2, '(3년전)'), (3, 2, '(2년전)'), (5, 2, '작년')],
    [(1, 2, f'{date.today().year-2}년'), (3, 2, f'{date.today().year-1}년')],
])
def test_past_only_headers_preserve_all_cells_and_explain_skip(tmp_path, headers):
    src, out, report = _fill(tmp_path, headers,
        [(1, 2, ''), (3, 2, ''), (5, 2, '')], {'직원수': '12명'})
    assert _tables(out) == _tables(src)
    assert report.filled == {}
    assert any('PAST_PERIOD_ONLY' in note for note in report.notes)


def test_merged_current_header_covering_two_value_cells_is_not_guessed(tmp_path):
    src, out, report = _fill(tmp_path,
        [(1, 2, '작년'), (3, 4, '올해(예상)')],
        [(1, 2, ''), (3, 2, ''), (5, 2, '')], {'직원수': '12명'})
    assert _tables(out) == _tables(src)
    assert report.filled == {}
    assert any('AMBIGUOUS_PERIOD_CELL' in note for note in report.notes)


def test_overlapping_past_and_current_header_ranges_are_not_written(tmp_path):
    src, out, report = _fill(tmp_path,
        [(1, 4, '올해'), (3, 2, '작년')],
        [(1, 2, ''), (3, 2, ''), (5, 2, '')], {'직원수': '12명'})
    assert _tables(out) == _tables(src)
    assert report.filled == {}
    assert any('AMBIGUOUS_PERIOD_HEADER' in note for note in report.notes)


@pytest.mark.parametrize('headers,reason', [
    ([(1, 2, '(3년전)'), (3, 4, '작년')], 'PAST_PERIOD_ONLY'),
    ([(1, 2, '작년'), (3, 4, '올해')], 'AMBIGUOUS_PERIOD_CELL'),
])
@pytest.mark.parametrize('key', ['직원수', '종업원수'])
def test_period_hold_also_prevents_inline_alias_fill(tmp_path, headers, reason, key):
    src, out, report = _fill(tmp_path, headers,
        [(1, 2, '종업원수 : ____'), (3, 2, '직원수 : ____'), (5, 2, '')],
        {key: '12명'})
    assert _tables(out) == _tables(src)
    assert report.filled == {}
    assert any(reason in note for note in report.notes)


@pytest.mark.parametrize('label', ['설립연도', '연도', '년도'])
def test_establishment_year_value_is_not_a_period_header(tmp_path, label):
    rows = [f'<hp:tr>{_merged(0, i, "양식 안내", 4)}</hp:tr>' for i in range(4)]
    rows.append('<hp:tr>' + _merged(0, 4, label)
                + _merged(1, 4, f'{date.today().year}년') + '</hp:tr>')
    rows.append('<hp:tr>' + ''.join(_merged(col, 5, value) for col, value in
                enumerate(['직위', '', '대표자', ''])) + '</hp:tr>')
    src, out = tmp_path / 'metadata.hwpx', tmp_path / 'filled.hwpx'
    _write(src, _sec('<hp:p><hp:run><hp:tbl>' + ''.join(rows) + '</hp:tbl></hp:run></hp:p>'))
    original = src.read_bytes()
    report = fill_hwpx(src, out, identity={'대표자': '검증대표'}, force_black=False)
    assert _tables(out)[0][-1] == ['직위', '', '대표자', '검증대표']
    assert _tables(out)[0][:-1] == _tables(src)[0][:-1]
    assert report.filled['대표자'] == '검증대표'
    assert src.read_bytes() == original


def test_numeric_header_cannot_route_representative_past_next_label(tmp_path):
    rows = [f'<hp:tr>{_merged(0, i, "양식 안내", 4)}</hp:tr>' for i in range(4)]
    rows.append('<hp:tr>' + _merged(0, 4, '연도', 3)
                + _merged(3, 4, f'{date.today().year}년') + '</hp:tr>')
    rows.append('<hp:tr>' + ''.join(_merged(col, 5, value) for col, value in
                enumerate(['대표자', '', '직위', ''])) + '</hp:tr>')
    src, out = tmp_path / 'bounded.hwpx', tmp_path / 'filled.hwpx'
    _write(src, _sec('<hp:p><hp:run><hp:tbl>' + ''.join(rows) + '</hp:tbl></hp:run></hp:p>'))
    original = src.read_bytes()
    report = fill_hwpx(src, out, identity={'대표자': '검증대표'}, force_black=False)
    assert _tables(out)[0][-1] == ['대표자', '검증대표', '직위', '']
    assert _tables(out)[0][:-1] == _tables(src)[0][:-1]
    assert report.filled['대표자'] == '검증대표'
    assert src.read_bytes() == original


@pytest.mark.parametrize('heading', ['구분(명)', '구분 (단위: 명)', '연도별 실적', '인원 현황'])
@pytest.mark.parametrize('current', ['현재', '작년'])
def test_period_header_qualifiers_never_fall_back_to_past_cell(tmp_path, heading, current):
    row = '<hp:tr>' + _merged(0, 0, heading) + _merged(1, 0, '(3년전)') + _merged(2, 0, current) + '</hp:tr>'
    row += '<hp:tr>' + _merged(0, 1, '종업원수') + _merged(1, 1, '') + _merged(2, 1, '') + '</hp:tr>'
    src, out = tmp_path / 'qualified.hwpx', tmp_path / 'filled.hwpx'
    _write(src, _sec('<hp:p><hp:run><hp:tbl>' + row + '</hp:tbl></hp:run></hp:p>'))
    report = fill_hwpx(src, out, identity={'직원수': '12명'}, force_black=False)
    assert _tables(out)[0][1][1] == ''
    if current == '현재' and heading != '인원 현황':
        assert _tables(out)[0][1][2] == '12명'
    else:
        assert _tables(out) == _tables(src)
        assert report.filled == {}
        assert any('PERIOD_' in note for note in report.notes)


@pytest.mark.parametrize('guidance', [
    '(본인이 희망하는 창업 아이템 및 분야에 대하여 간략히 소개)',
    '（본인이 희망하는 창업 아이템 및 분야에 대하여 간략히 소개）',
    '(해당 사항을 기재)',
    '(사업 내용을 간략히 작성)',
])
def test_parenthesized_instruction_is_filled_from_user_brief(tmp_path, guidance):
    assert _is_hwpx_guidance_placeholder(guidance)
    src, out = tmp_path / 'overview.hwpx', tmp_path / 'filled.hwpx'
    middle = len(guidance) // 2
    row = '<hp:tr>' + _cell(0, 0, _run('창업아이템 개요')) + _cell(
        1, 0, _run(guidance[:middle]) + _run(guidance[middle:])
    ) + '</hp:tr>'
    _write(src, _sec('<hp:p><hp:run><hp:tbl>' + row + '</hp:tbl></hp:run></hp:p>'))
    original = src.read_bytes()
    brief = '사용자가 입력한 문서 작성 지원 서비스'
    identity = build_direct_fill_identity(ProjectInput(template_id='synthetic', answers={'user_brief': brief}))
    report = fill_hwpx(src, out, identity=identity, force_black=False)
    assert _tables(out)[0][0] == ['창업아이템 개요', brief]
    assert report.filled['창업아이템 개요'] == brief
    assert not any('EXISTING_VALUE' in note for note in report.notes)
    assert src.read_bytes() == original


@pytest.mark.parametrize('value', [
    '(AI가 문서 초안을 작성하는 서비스)',
    '(사업계획서 작성)',
    '(사업 내용을 작성하는 AI 서비스)',
    '(신청자 정보 기재 완료)',
    '(본인이 희망하는 분야: 문서 작성)',
    '현재 작성한 사업 개요 (간략히 소개)',
    '(사업 내용은 생성형 AI로 맞춤형 사업계획서를 작성)',
    '(창업 아이템은 사용자 질문을 분석해 문서 초안을 작성)',
])
def test_parenthesized_real_overview_is_preserved_with_existing_value_note(tmp_path, value):
    assert not _is_hwpx_guidance_placeholder(value)
    src, out = tmp_path / 'overview.hwpx', tmp_path / 'filled.hwpx'
    row = '<hp:tr>' + _cell(0, 0, _run('창업아이템 개요')) + _cell(1, 0, _run(value)) + '</hp:tr>'
    _write(src, _sec('<hp:p><hp:run><hp:tbl>' + row + '</hp:tbl></hp:run></hp:p>'))
    original = src.read_bytes()
    report = fill_hwpx(src, out, identity={'창업아이템 개요': '대체 값'}, force_black=False)
    assert _tables(out) == _tables(src)
    assert report.filled == {}
    assert any('EXISTING_VALUE' in note for note in report.notes)
    assert src.read_bytes() == original
