"""test_pure_resume_form_map.py — 빈 이력서 양식의 '반복행 리스트 표' 인식 안전망.

이력서 양식(HWPX)에는 학력·경력·자격 같은 '헤더행 + 여러 빈 데이터행' 표가 있다.
이 모듈은 그 표를 찾아 **어느 열이 어떤 항목인지**(기간/직장명/직위…)와 **어느 행이
비어 있는지**를 지도로 만든다. 채움 서비스가 이 지도만 보고 값을 기입하므로, 지도가
틀리면 엉뚱한 칸에 값이 들어간다.

파싱은 lxml 트리만 받는 순수 함수라 파일·한글 없이 그대로 돌린다. 야간 안전망(2026-08-04).

여기서 고정하는 계약(불변: **오매칭 < 빈칸**):
- 헤더를 확신할 수 없는 표는 통째로 건너뛴다(None) — 엉뚱한 표를 채우지 않는다.
- 이미 값이 든 행은 '빈 데이터행'에 넣지 않는다(덮어쓰기 금지).
- 체크박스 등 폼 컨트롤이 든 칸은 빈칸으로 보지 않는다(글자·컨트롤 이중 표시 방지).
"""

from __future__ import annotations

from lxml import etree

from auto_write.services.resume_form_map import (
    SECTION_KINDS,
    FormSection,
    map_form_sections,
    map_table_section,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _cell(text: str = "", col: int | None = None, extra: str = "") -> str:
    addr = f'<cellAddr colAddr="{col}" rowAddr="0"/>' if col is not None else ""
    body = f"<subList><p><run><t>{text}</t></run>{extra}</p></subList>" if (text or extra) else ""
    return f"<tc>{addr}{body}</tc>"


def _row(*cells: str) -> str:
    return f"<tr>{''.join(cells)}</tr>"


def _table(*rows: str) -> str:
    return f"<tbl>{''.join(rows)}</tbl>"


def _root(xml: str):
    return etree.fromstring(f'<sec xmlns="{_HP}">{xml}</sec>'.encode("utf-8"))


def _one_table(xml: str):
    return next(_root(xml).iter(f"{{{_HP}}}tbl"))


_CAREER_HEADER = _row(
    _cell("근무기간", 0), _cell("직장명", 1), _cell("직위", 2), _cell("담당업무", 3)
)
_EMPTY_ROW = _row(_cell(col=0), _cell(col=1), _cell(col=2), _cell(col=3))


# --- 인식 성공 ---------------------------------------------------------------

def test_career_table_maps_columns_to_profile_fields():
    fs = map_table_section(_one_table(_table(_CAREER_HEADER, _EMPTY_ROW, _EMPTY_ROW)))
    assert fs is not None
    assert fs.kind == "career"
    assert fs.col_field_map == {0: "period", 1: "company", 2: "position", 3: "duty"}
    assert len(fs.empty_rows) == 2


def test_education_table_is_recognized():
    header = _row(
        _cell("재학기간", 0), _cell("학교명", 1), _cell("전공", 2), _cell("학위", 3)
    )
    fs = map_table_section(_one_table(_table(header, _EMPTY_ROW)))
    assert fs is not None and fs.kind == "education"
    assert fs.col_field_map == {0: "period", 1: "school", 2: "major", 3: "degree"}


def test_certs_table_is_recognized():
    header = _row(_cell("자격증명", 0), _cell("취득일", 1), _cell("발급기관", 2))
    fs = map_table_section(_one_table(_table(header, _row(_cell(col=0), _cell(col=1), _cell(col=2)))))
    assert fs is not None and fs.kind == "certs"
    assert fs.col_field_map == {0: "name", 1: "date", 2: "issuer"}


def test_header_labels_tolerate_inner_spaces():
    # 『직 위』처럼 자간을 벌린 라벨도 정규화 후 인식된다.
    header = _row(
        _cell("근무 기간", 0), _cell("직 장 명", 1), _cell("직 위", 2), _cell("담당 업무", 3)
    )
    fs = map_table_section(_one_table(_table(header, _EMPTY_ROW)))
    assert fs is not None and fs.col_field_map[1] == "company"


def test_position_index_is_used_when_celladdr_missing():
    header = _row(_cell("근무기간"), _cell("직장명"), _cell("직위"), _cell("담당업무"))
    empty = _row(_cell(), _cell(), _cell(), _cell())
    fs = map_table_section(_one_table(_table(header, empty)))
    assert fs is not None
    assert fs.col_field_map == {0: "period", 1: "company", 2: "position", 3: "duty"}
    assert len(fs.empty_rows) == 1


def test_header_row_and_table_are_kept_for_the_fill_service():
    tbl = _one_table(_table(_CAREER_HEADER, _EMPTY_ROW))
    fs = map_table_section(tbl)
    assert fs.table is tbl
    assert fs.header_row is list(tbl)[0]


# --- 인식 거부 (오매칭 < 빈칸) ------------------------------------------------

def test_unknown_table_is_skipped():
    tbl = _one_table(_table(_row(_cell("항목", 0), _cell("내용", 1)), _EMPTY_ROW))
    assert map_table_section(tbl) is None


def test_recognized_kind_without_mappable_columns_is_skipped():
    # 헤더 시그니처는 맞지만 한 칸에 뭉쳐 있어 열 지도를 못 만들면 건너뛴다.
    tbl = _one_table(_table(_row(_cell("직장명 / 담당업무", 0)), _EMPTY_ROW))
    assert map_table_section(tbl) is None


def test_data_row_leading_with_a_year_is_not_mistaken_for_header():
    # 값이 먼저 든 표(부분 작성본)에서 데이터행을 헤더로 오인하지 않는다.
    tbl = _one_table(
        _table(_row(_cell("2020.01~2022.12", 0), _cell("직장명", 1), _cell("직위", 2)))
    )
    assert map_table_section(tbl) is None


def test_empty_table_is_skipped():
    assert map_table_section(_one_table(_table())) is None


# --- 빈 데이터행 판정 ---------------------------------------------------------

def test_row_with_existing_value_is_not_treated_as_empty():
    filled = _row(
        _cell("2020.01~2022.12", 0), _cell("밸류업파트너스", 1),
        _cell("대표", 2), _cell("컨설팅", 3),
    )
    fs = map_table_section(_one_table(_table(_CAREER_HEADER, filled, _EMPTY_ROW)))
    assert len(fs.empty_rows) == 1     # 값 있는 행은 제외(덮어쓰기 금지)


def test_partially_filled_row_is_not_empty():
    partial = _row(_cell("2020.01~", 0), _cell(col=1), _cell(col=2), _cell(col=3))
    fs = map_table_section(_one_table(_table(_CAREER_HEADER, partial)))
    assert fs.empty_rows == []


def test_row_without_mapped_columns_is_ignored():
    # 합계·비고처럼 매핑 열이 없는 행은 데이터행으로 세지 않는다.
    note = _row(_cell(col=7), _cell(col=8))
    fs = map_table_section(_one_table(_table(_CAREER_HEADER, note, _EMPTY_ROW)))
    assert len(fs.empty_rows) == 1


def test_cell_with_form_control_is_not_fillable():
    # 체크박스가 든 칸은 비어 보여도 글자를 넣으면 안 된다(이중 표시).
    ctrl = _row(
        _cell(col=0, extra="<run><checkBtn/></run>"),
        _cell(col=1), _cell(col=2), _cell(col=3),
    )
    fs = map_table_section(_one_table(_table(_CAREER_HEADER, ctrl)))
    assert fs.empty_rows == []


def test_row_with_no_cells_is_skipped():
    fs = map_table_section(_one_table(_table(_CAREER_HEADER, "<tr/>", _EMPTY_ROW)))
    assert len(fs.empty_rows) == 1


# --- map_form_sections (문서 전체) --------------------------------------------

def test_sections_are_returned_in_document_order():
    edu_header = _row(_cell("재학기간", 0), _cell("학교명", 1), _cell("학위", 2))
    edu_empty = _row(_cell(col=0), _cell(col=1), _cell(col=2))
    root = _root(
        _table(edu_header, edu_empty)
        + _table(_row(_cell("항목", 0)))            # 인식 불가 — 건너뜀
        + _table(_CAREER_HEADER, _EMPTY_ROW)
    )
    kinds = [fs.kind for fs in map_form_sections(root)]
    assert kinds == ["education", "career"]


def test_document_without_recognizable_tables_returns_empty_list():
    assert map_form_sections(_root(_table(_row(_cell("항목", 0))))) == []


# --- FormSection.summary ------------------------------------------------------

def test_summary_has_no_lxml_references():
    fs = map_table_section(_one_table(_table(_CAREER_HEADER, _EMPTY_ROW, _EMPTY_ROW)))
    assert fs.summary() == {
        "kind": "career",
        "fields": ["period", "company", "position", "duty"],
        "empty_rows": 2,
    }


def test_default_form_section_summary():
    assert FormSection(kind="certs").summary() == {
        "kind": "certs", "fields": [], "empty_rows": 0
    }


def test_section_kinds_cover_every_supported_list():
    assert set(SECTION_KINDS) == {
        "education", "career", "certs", "lectures", "projects"
    }
