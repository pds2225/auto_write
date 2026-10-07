"""resume_form_map.py — 빈 이력서 양식(HWPX)의 '반복행 리스트 표'를 인식한다.

범용 이력서 자동작성기 P2(M2). 양식 HWPX 의 각 섹션 표를 훑어, 학력·경력·자격·
강의·수행 같은 '헤더행 + 여러 데이터행' 구조(반복행 리스트 표)를 찾는다. 헤더행의
각 열(colAddr)을 프로필 필드(period/school/… 등)에 매핑하고, 그 아래 '빈 데이터행'
목록을 산출한다. 채움 로직(resume_fill_service)이 이 지도를 받아 실제 값을 기입한다.

원칙(불변)
---------
- **오매칭 < 빈칸**: 헤더를 확신할 수 없는 표는 스킵한다(엉뚱한 표 채움 금지).
- **near-순수 함수**: 파싱은 lxml 트리만 받는 순수 함수(``map_form_sections``)로 분리해
  파일/COM 없이 테스트한다.
- **읽기 전용**: 이 모듈은 트리를 수정하지 않는다(채움은 fill_service 담당).

재사용
------
- OWPML 표 헬퍼는 ``hwpx_fill`` 에서 그대로 가져온다(단일 출처):
  ``_q``·``_direct``·``_cell_addr``·``_cell_text``·``_cell_is_fillable``.
- 섹션 헤더 인식은 ``resume_extract._match_section_header`` 를 재사용한다(추출/양식 동일 기준).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from auto_write.services.hwpx_fill import (
    _cell_addr,
    _cell_is_fillable,
    _cell_text,
    _direct,
    _q,
)
from .resume_extract import _match_section_header, _norm_label

__all__ = [
    "FormSection",
    "SECTION_KINDS",
    "map_form_sections",
    "map_table_section",
]

# kind → {정규화(공백제거·소문자) 헤더 라벨: 프로필 필드}.
# 헤더 텍스트를 프로필 항목의 필드로 옮기는 열 지도. 확신 없는 열은 매핑하지 않는다
# (미매핑 열은 채우지 않음 = 오기입<빈칸). resume_extract 데이터클래스 필드명과 일치.
_COL_FIELD_MAPS: dict[str, dict[str, str]] = {
    "education": {
        "기간": "period", "재학기간": "period", "수학기간": "period", "연도": "period",
        "학교명": "school", "학교": "school", "출신학교": "school", "학교(전공)": "school",
        "전공": "major", "학과": "major", "전공분야": "major", "전공(학과)": "major",
        "학위": "degree", "학위구분": "degree", "졸업구분": "degree", "학위(구분)": "degree",
    },
    "career": {
        "기간": "period", "근무기간": "period", "재직기간": "period", "재직기간(년월)": "period",
        "직장명": "company", "회사명": "company", "근무처": "company", "기관명": "company",
        "직장": "company", "소속": "company",
        "직위": "position", "직급": "position", "직책": "position",
        "담당업무": "duty", "담당": "duty", "주요업무": "duty", "업무내용": "duty", "업무": "duty",
    },
    "certs": {
        "취득일": "date", "취득일자": "date", "일자": "date", "취득년월": "date", "취득년월일": "date",
        "자격증명": "name", "자격명": "name", "자격증": "name", "종목": "name", "종목명": "name",
        "발급번호": "number", "자격번호": "number", "등록번호": "number", "자격증번호": "number",
        "발급기관": "issuer", "발급처": "issuer", "주관기관": "issuer", "시행기관": "issuer",
    },
    "lectures": {
        "일자": "date", "날짜": "date", "강의일자": "date", "연도": "date",
        "주최기관": "org", "주최기관명": "org", "주관기관": "org", "주관기관명": "org",
        "기관명": "org", "교육기관": "org",
        "강의주제": "topic", "주제": "topic", "강의명": "topic", "제목": "topic", "과목": "topic",
        "회차": "count", "횟수": "count", "시간": "count", "강의시간": "count",
        "구분": "kind", "유형": "kind", "형태": "kind",
    },
    "projects": {
        "기간": "period", "수행기간": "period", "사업기간": "period",
        "프로젝트명": "name", "과제명": "name", "사업명": "name", "프로젝트": "name",
        "수행내용": "content", "내용": "content", "주요내용": "content", "역할": "content",
        "발주처": "client", "발주기관": "client", "고객사": "client", "의뢰기관": "client",
        "수요기관": "client",
    },
}

# 인식 가능한 반복행 섹션 종류(프로필 리스트 키와 동일).
SECTION_KINDS = tuple(_COL_FIELD_MAPS.keys())


@dataclass
class FormSection:
    """양식 안의 반복행 리스트 표 한 개.

    kind: 섹션 종류(education/career/certs/lectures/projects).
    col_field_map: {열키(colAddr 또는 위치 인덱스): 프로필 필드명}.
    empty_rows: 헤더 아래 '빈 데이터행'(매핑 열이 전부 빈) tr 요소 목록(문서순).
    table/header_row: 원본 lxml 요소(채움 서비스가 제자리 수정에 사용).
    """

    kind: str
    col_field_map: dict[Any, str] = field(default_factory=dict)
    empty_rows: list = field(default_factory=list)
    table: Any = None
    header_row: Any = None

    def summary(self) -> dict:
        """요소 참조 없이 개수만 담은 요약(테스트·리포트용)."""
        return {
            "kind": self.kind,
            "fields": list(self.col_field_map.values()),
            "empty_rows": len(self.empty_rows),
        }


def _row_colkey_cells(cells: list) -> list:
    """행의 [(열키, tc)] — colAddr 있으면 그 값, 없으면 위치 인덱스."""
    out = []
    for pos, tc in enumerate(cells):
        addr = _cell_addr(tc)
        out.append((addr if addr is not None else pos, tc))
    return out


def _header_kind_and_map(cells: list) -> Optional[tuple[str, dict]]:
    """헤더행 셀들이면 (kind, col_field_map) 반환, 아니면 None.

    _match_section_header 로 kind 를 먼저 판정한 뒤, 그 kind 의 열 지도로
    각 헤더 셀을 필드에 매핑한다. 매핑된 열이 하나도 없으면 None(스킵).
    """
    texts = [_cell_text(tc) for tc in cells]
    kind = _match_section_header(texts)
    if kind is None:
        return None
    label_map = _COL_FIELD_MAPS.get(kind, {})
    col_field: dict = {}
    for colkey, tc in _row_colkey_cells(cells):
        fld = label_map.get(_norm_label(_cell_text(tc)))
        if fld is not None and colkey not in col_field:
            col_field[colkey] = fld
    if not col_field:
        return None
    return kind, col_field


def map_table_section(tbl) -> Optional[FormSection]:
    """표 하나 → FormSection(반복행 리스트로 인식되면) 또는 None.

    첫 번째 헤더행을 찾아 kind·열지도를 정하고, 그 아래 '빈 데이터행'(매핑 열이
    전부 채움 가능한 빈칸)만 모은다. 값이 든 행은 스킵(덮어쓰기 금지)하고 계속
    탐색한다 — 부분 채워진 양식도 남은 빈 행을 이어서 채울 수 있다.
    """
    rows = _direct(tbl, "tr")
    header_idx = None
    kind: Optional[str] = None
    col_field: dict = {}
    for i, tr in enumerate(rows):
        cells = _direct(tr, "tc")
        if not cells:
            continue
        hk = _header_kind_and_map(cells)
        if hk is not None:
            kind, col_field = hk
            header_idx = i
            break
    if header_idx is None or kind is None or not col_field:
        return None

    empty_rows: list = []
    for tr in rows[header_idx + 1:]:
        cells = _direct(tr, "tc")
        if not cells:
            continue
        by_key = {k: tc for k, tc in _row_colkey_cells(cells)}
        mapped = [by_key[k] for k in col_field if k in by_key]
        if not mapped:
            continue  # 매핑 열이 없는 행(주석·합계 등) — 데이터행 아님
        # 매핑 셀이 전부 '채움 가능한 빈칸'이어야 빈 데이터행(실값 있으면 스킵).
        if all(_cell_is_fillable(tc) and not _cell_text(tc) for tc in mapped):
            empty_rows.append(tr)
    return FormSection(
        kind=kind, col_field_map=col_field, empty_rows=empty_rows,
        table=tbl, header_row=rows[header_idx])


def map_form_sections(section_root) -> list:
    """섹션 XML 루트 → FormSection 목록(문서순).

    루트의 모든 hp:tbl 을 순회하며 반복행 리스트로 인식되는 표만 담는다.
    헤더를 못 찾은 표는 스킵된다(오매칭<빈칸).
    """
    out: list = []
    for tbl in section_root.iter(_q("tbl")):
        fs = map_table_section(tbl)
        if fs is not None:
            out.append(fs)
    return out
