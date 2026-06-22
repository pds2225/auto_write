"""cross_form_autofill.py — 완성된 사업계획서 A(소스)의 라벨-값을
빈 양식 B(타깃)의 유사 항목 칸에 자동 전사하는 결정론 엔진(v1, AI無).

배경/목적
---------
같은 사업계획서를 여러 운영기관 양식에 다시 옮겨 적는 반복 작업을 줄인다.
A 문서에서 "라벨→값" 쌍을 뽑고, B 문서의 빈 항목 칸 라벨과 의미가 같은(동의어 포함)
칸을 보수적으로 매칭해 값을 전사한다.

핵심 안전 원칙
-------------
- **오매칭은 빈칸보다 나쁘다** → **high 만 자동 전사한다.**
  정확일치/동의어 단일후보(high)만 채운다. 퍼지(자카드·부분문자열)·약매칭·충돌은
  자동 채우지 않고 needs_confirm 으로 제안만 한다(접미사 다른 합성어 — 사업명/사업자명,
  주소/주소지정 — 가 자동 전사되는 것을 원천 차단).
- **날조 0** — 소스에 실제로 존재하는(비어있지 않은) 값만 옮긴다. 없으면 안 채운다.
- **원본 미수정** — A·B 는 절대 변형하지 않는다. out==source 또는 out==target 이면 ValueError.
  중간본은 tempfile 로 처리한다.
- **전사값 보존** — 전사 셀에는 ``docx_ops.set_cell_text`` 로 값을 직접 기입한다.
  잔여물/안내 청소 패스를 돌리지 않으므로 ``○○○`` 마스킹 이름·``OOO-OO-OOOOO`` 같은
  값이 훼손되지 않는다(거짓 보고 방지). transcribed 는 실제 저장 문서 기준으로 센다.
- AI 호출 없음 — 동일 입력, 동일 결과(결정론). use_ai 는 v1 에서 미사용(향후 확장 슬롯).

재사용
------
- ``SubmittableFiller._key`` / ``_logical_cells`` 의 정규화·병합셀 안전 순회를 재사용한다
  (여기서는 모듈 함수 _key/_logical_cells 로 노출해 일관 사용).
- 전사는 타깃 칸 좌표(table_index/row/value_cell)에 ``docx_ops.set_cell_text`` 로 직접
  기입한다(라벨 다음 칸이 아니라 정확한 값셀에, 잔여물 청소 없이).
- A/B 가 .hwp/.hwpx 면 ``hwp_docx_convert`` 로 DOCX 변환, out 이 .hwp 면 docx_to_hwp.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from .docx_ops import set_cell_text
from .submittable_filler import SubmittableFiller

_HWP_EXTS = {".hwp", ".hwpx"}
_SUPPORTED_EXTS = {".docx", ".hwp", ".hwpx"}  # H7: 입력 지원 확장자 화이트리스트


# --- 라벨 정규화 / 병합셀 순회(SubmittableFiller 규칙 재사용) -------------------

def _key(text: str) -> str:
    """라벨 비교용 핵심 키: 괄호 보조설명·공백 제거(SubmittableFiller._key 와 동일 규칙)."""
    return SubmittableFiller._key(text)


def _logical_cells(row) -> list:
    """병합 중복을 제거한 논리적 셀 목록(SubmittableFiller._logical_cells 와 동일 규칙)."""
    return SubmittableFiller._logical_cells(row)


# --- 동의어 클러스터 ----------------------------------------------------------
# 각 클러스터는 의미가 같은 라벨들의 모음이다. 정규화(_key) 기준으로 비교한다.
# 확장 가능: 새 클러스터를 리스트에 추가하면 _CLUSTER_OF 가 자동 반영된다.
SYNONYMS: list[list[str]] = [
    ["기업명", "신청기관", "업체명", "회사명", "상호", "기관명", "법인명"],
    ["대표자", "성명", "대표", "대표이사", "대표자명", "성명(대표자)", "신청인"],
    ["사업명", "과제명", "사업명칭", "과제명칭", "사업과제명", "과제명(사업명)"],
    ["사업자등록번호", "사업자번호", "사업자등록No", "사업자등록번호No"],
    ["연락처", "전화", "전화번호", "휴대전화", "연락전화", "대표전화", "핸드폰"],
    ["주소", "소재지", "사업장주소", "사업장소재지", "주된사무소소재지", "본사주소"],
    ["업종", "산업분류", "업태", "주업종"],
    ["이메일", "전자우편", "email", "e-mail", "메일", "이메일주소"],
    ["설립일", "설립연월일", "창업일", "설립일자", "개업연월일", "창업연월일"],
]

# 정규화 라벨 → 대표키(클러스터의 첫 원소). 같은 대표키면 동의어로 본다.
_CLUSTER_OF: dict[str, str] = {}
for _cluster in SYNONYMS:
    _rep = _key(_cluster[0])
    for _alias in _cluster:
        _CLUSTER_OF[_key(_alias)] = _rep


def _cluster_rep(norm_label: str) -> Optional[str]:
    """정규화 라벨이 속한 동의어 클러스터 대표키. 없으면 None."""
    return _CLUSTER_OF.get(norm_label)


_BRACKET_RE = re.compile(r"[\(（]([^\)）]*)[\)）]")


def _bracket_tokens(text: str) -> set[str]:
    """라벨의 괄호 안 토큰 집합(공백 제거). 예: '금액(국고)' → {'국고'}."""
    return {
        re.sub(r"\s+", "", m).strip()
        for m in _BRACKET_RE.findall(str(text or ""))
        if re.sub(r"\s+", "", m).strip()
    }


def _bracket_conflict(label_a: str, label_b: str) -> bool:
    """두 원본 라벨의 괄호 토큰이 양쪽에 존재하고 서로 다르면 True(H3).

    '금액(국고)' vs '금액(자부담)' → _key 는 둘 다 '금액'이라 정확일치하지만
    괄호 구별 토큰이 달라 같은 항목이 아니다 → high 금지.
    """
    ta = _bracket_tokens(label_a)
    tb = _bracket_tokens(label_b)
    if not ta or not tb:
        return False
    return ta != tb


# --- 데이터 모델 --------------------------------------------------------------

@dataclass
class Match:
    target_label: str          # 타깃 원본 라벨 텍스트
    normalized: str            # 타깃 정규화 라벨
    source_label: str          # 매칭된 소스 원본 라벨(자동전사 대상이 아니면 "")
    value: str                 # 전사할 값(소스 실값; 전사 대상이 아니면 "")
    confidence: str            # "high"(자동전사) | "fuzzy" | "conflict" | "low"
    table_index: int           # 타깃 표 인덱스
    row: int                   # 타깃 행
    value_cell: int            # 타깃 값 셀(논리 셀) 인덱스
    candidates: list[str] = field(default_factory=list)  # 보고용 후보(자동전사 아님)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_label": self.target_label,
            "normalized": self.normalized,
            "source_label": self.source_label,
            "value": self.value,
            "confidence": self.confidence,
            "table_index": self.table_index,
            "row": self.row,
            "value_cell": self.value_cell,
        }


@dataclass
class AutofillReport:
    source: str
    target: str
    output: str
    transcribed: int = 0
    src_fields: int = 0        # 소스에서 추출한 라벨-값 수(진단용, H6)
    tgt_fields: int = 0        # 타깃에서 찾은 빈칸 수(진단용, H6)
    matches: list[Match] = field(default_factory=list)        # 실제 전사한 매칭
    needs_confirm: list[dict[str, Any]] = field(default_factory=list)  # 애매/충돌(보류)
    unmatched_targets: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "output": self.output,
            "transcribed": self.transcribed,
            "src_fields": self.src_fields,
            "tgt_fields": self.tgt_fields,
            "matches": [m.as_dict() for m in self.matches],
            "needs_confirm": self.needs_confirm,
            "unmatched_targets": self.unmatched_targets,
            "ok": self.ok,
            "notes": self.notes,
        }


# --- 추출: 소스에서 라벨→값 ----------------------------------------------------

_PARA_LABEL_VALUE_RE = re.compile(r"^\s*([^:：]{1,40})\s*[:：]\s*(.+?)\s*$")

# 순수 숫자/금액/날짜 패턴(값이 라벨로 둔갑하는 행렬표에서 라벨다움 판정용).
# 예: "30,000,000", "60,000원", "2026-04-10", "2026.04.10", "10%", "1,234.5"
_NUMERIC_VALUE_RE = re.compile(
    r"^[\s\d.,\-/원만억천백십개%~()–—:]+$"
)


def _looks_numeric(text: str) -> bool:
    """값이 순수 숫자/금액/날짜/수량 패턴이면 True(라벨로 등록 부적합)."""
    t = (text or "").strip()
    if not t:
        return False
    if not any(ch.isdigit() for ch in t):
        return False
    return bool(_NUMERIC_VALUE_RE.match(t))


def _is_numeric_data_row(logical) -> bool:
    """행의 비어있지 않은 셀이 대부분(과반 이상) 순수 숫자/금액이면 데이터 행."""
    vals = [c.text.strip() for c in logical if c.text and c.text.strip()]
    if len(vals) < 2:
        return False
    numeric = sum(1 for v in vals if _looks_numeric(v))
    return numeric >= len(vals) / 2


def _is_matrix_header_row(table_rows, ri: int) -> bool:
    """행렬형 헤더 행(라벨만 가득 + 다음 행이 숫자 데이터)이면 True.

    예: 행0=[국고보조금, 자기부담금, 총사업비] (라벨들), 행1=[30M, 10M, 40M] (숫자).
    이런 헤더 행은 짝수=라벨 위치단정이 라벨→라벨 페어링을 만들므로 건너뛴다.
    """
    if ri + 1 >= len(table_rows):
        return False
    logical = _logical_cells(table_rows[ri])
    non_empty = [c.text.strip() for c in logical if c.text and c.text.strip()]
    if len(non_empty) < 3:
        return False
    # 헤더 행 자신은 비숫자 라벨들로 가득해야 한다.
    if any(_looks_numeric(v) for v in non_empty):
        return False
    # 바로 다음 행이 숫자 데이터 행이어야 한다.
    return _is_numeric_data_row(_logical_cells(table_rows[ri + 1]))


def _collect_label_keys(doc) -> set[str]:
    """문서에서 '라벨로도 등장하는' 셀들의 정규화 키 집합(값 둔갑 차단용).

    두 종류를 수집한다:
    1. 짝수 인덱스(0,2,…) 셀 — 정상 라벨-값 쌍의 라벨 위치.
    2. **반복 셀** — 같은 열 인덱스에서 2개 이상 행에 같은 텍스트로 나타나는 셀.
       행렬/세로병합 예산표의 행머리(예: 국고보조금)·범주 라벨(인증평가·현금)은
       값이 아니라 분류 라벨인데 홀수 인덱스에 와도 반복되므로 이렇게 잡는다.

    행렬/세로배치 예산표에서 한 셀이 '값'으로 추출돼도 같은 문서에 '라벨'로도
    등장하면 그 (라벨,값) 쌍을 폐기하기 위한 라벨 사전이다.
    """
    keys: set[str] = set()
    # (col_index, key) → 출현 횟수
    col_counts: dict[tuple[int, str], int] = {}
    for table in doc.tables:
        rows = table.rows
        for ri, row in enumerate(rows):
            logical = _logical_cells(row)
            header_row = _is_matrix_header_row(rows, ri)
            for i, cell in enumerate(logical):
                k = _key(cell.text)
                if not k:
                    continue
                if i % 2 == 0 or header_row:  # 짝수 인덱스 또는 행렬 헤더 = 라벨 위치
                    keys.add(k)
                if not _looks_numeric(cell.text):  # 숫자는 반복돼도 라벨 아님
                    col_counts[(i, k)] = col_counts.get((i, k), 0) + 1
    # 같은 열에서 2회 이상 반복된 비숫자 셀 = 분류/행머리 라벨
    for (_, k), cnt in col_counts.items():
        if cnt >= 2:
            keys.add(k)
    return keys


def _is_bad_value(value: str, label_keys: set[str]) -> bool:
    """추출된 '값'이 실제로는 또 다른 라벨이라서 폐기해야 하면 True(C1/H1/M3 가드).

    (a) 값의 정규화 키가 동의어 클러스터 라벨이거나,
    (b) 같은 문서에서 라벨로도 등장하면(짝수 인덱스 또는 반복 셀) → 라벨→라벨
        오염이므로 폐기.

    숫자/금액/날짜 값(예: 123-45-67890, 30,000,000)은 그 자체로 라벨이 될 수 없어
    라벨→라벨 전사를 일으키지 않으므로 폐기하지 않는다(사업자등록번호 등 실값 보존).
    동의어 클러스터(a)는 label_keys 에 이미 그 라벨이 함께 등장할 때만 의미가 있으므로
    (b) 와 결합해서만 적용한다(단발 '연락처' 값 보존 — 기존 회귀 보호).
    """
    vkey = _key(value)
    if not vkey:
        return True
    # (b) 같은 문서에서 라벨로도 등장 → 라벨→라벨 오염
    if vkey in label_keys:
        return True
    # (a) 동의어 클러스터 라벨이면서, 그 클러스터의 다른 라벨이 문서 라벨로도 존재 →
    #     예산표의 분류 라벨이 값으로 둔갑한 경우. 단발 값(연락처 1회)은 보존.
    rep = _cluster_rep(vkey)
    if rep is not None:
        for lk in label_keys:
            if _cluster_rep(lk) == rep and lk != vkey:
                return True
    return False


def extract_source_fields(docx_path: str | Path) -> dict[str, str]:
    """소스 DOCX 의 표에서 (라벨,값) 쌍을 추출한다.

    - **짝수 인덱스(0,2,4…)만 라벨로** 본다: col0=라벨,col1=값,col2=라벨,col3=값.
      값 셀(홀수 인덱스)을 라벨로 쓰지 않으므로 ``[항목][연락처][010-…]`` 같은 행에서
      값 셀(연락처/010-…)이 라벨로 오염되지 않는다.
    - **방어 가드(C1/H1/M3)**: 추출된 '값'이 (a)동의어 클러스터 라벨이거나
      (b)같은 문서에서 라벨로도 등장하거나 (c)순수 숫자/금액/날짜 패턴이면 그 쌍을
      폐기한다. 행렬/세로배치/병합 예산표에서 라벨이 값으로 둔갑해 high 오전사되는
      것을 차단한다(오매칭은 빈칸보다 나쁘다).
    - 정규화 라벨(_key)을 키로, 라벨·값 둘 다 비어있지 않을 때만 담는다(날조 0의 출발점).
    - 같은 정규화 라벨이 여러 번 나오면 처음 채워진 값을 유지한다.
    - 보조: 본문 단락의 "라벨: 값" 패턴도 추출(표에 없을 때만 보강).
    """
    fields, _ = _extract_source(docx_path)
    return fields


def _extract_source(docx_path: str | Path) -> tuple[dict[str, str], dict[str, str]]:
    """extract_source_fields 의 내부 구현. (정규화필드, 원본라벨맵)을 함께 반환.

    원본라벨맵은 {정규화키: 원본 라벨 텍스트} 로, H3(괄호 토큰 대조)에 쓰인다.
    """
    doc = Document(str(docx_path))
    fields: dict[str, str] = {}
    originals: dict[str, str] = {}
    label_keys = _collect_label_keys(doc)

    def _put(label: str, label_text: str, value: str) -> None:
        if label not in fields:
            fields[label] = value
            originals[label] = SubmittableFiller._norm(label_text)

    for table in doc.tables:
        rows = table.rows
        for ri, row in enumerate(rows):
            logical = _logical_cells(row)
            # 행렬형 헤더 행(라벨만 + 다음 행 숫자)은 짝수 페어링 비적용(C1)
            if _is_matrix_header_row(rows, ri):
                continue
            # 짝수 인덱스만 라벨: (0,1)(2,3)(4,5)… 쌍으로 처리
            for i in range(0, len(logical) - 1, 2):
                label_text = logical[i].text
                label = _key(label_text)
                value = (logical[i + 1].text or "").strip()
                if not label or not value:
                    continue
                # 라벨 자리에 순수 숫자/금액/날짜가 오면(행렬표 데이터행) 라벨 등록 제외(M3)
                if _looks_numeric(label_text):
                    continue
                # 값이 라벨/동의어로 둔갑한 행렬표 오염 차단(C1/H1)
                if _is_bad_value(value, label_keys):
                    continue
                _put(label, label_text, value)

    # 보조: 본문 "라벨: 값" — 표에서 못 얻은 라벨만 보강
    for para in doc.paragraphs:
        m = _PARA_LABEL_VALUE_RE.match(para.text or "")
        if not m:
            continue
        label = _key(m.group(1))
        value = m.group(2).strip()
        if label and value and label not in fields:
            _put(label, m.group(1), value)

    return fields, originals


# --- 탐지: 타깃에서 빈 값칸 ----------------------------------------------------

def find_target_fields(docx_path: str | Path) -> list[dict[str, Any]]:
    """타깃 DOCX 에서 '라벨은 있고 인접 값칸이 빈' 칸을 식별한다.

    반환 각 항목: {orig_label, normalized, table_index, row, value_cell}
    - value_cell 은 라벨 셀 바로 다음 논리 셀의 인덱스(row_rewrites 의 cols 인덱스와 동일).
    - 인접 값칸이 이미 채워져 있으면(빈칸 아님) 후보에서 제외한다(덮어쓰기 금지).
    """
    doc = Document(str(docx_path))
    targets: list[dict[str, Any]] = []
    for ti, table in enumerate(doc.tables):
        for ri, row in enumerate(table.rows):
            logical = _logical_cells(row)
            for i in range(len(logical) - 1):
                label_text = logical[i].text or ""
                label = _key(label_text)
                if not label:
                    continue
                value_text = (logical[i + 1].text or "").strip()
                if value_text:
                    continue  # 이미 채워짐 → 후보 아님
                targets.append({
                    "orig_label": SubmittableFiller._norm(label_text),
                    "normalized": label,
                    "table_index": ti,
                    "row": ri,
                    "value_cell": i + 1,
                })
    return targets


# --- 매칭: 타깃 라벨 ↔ 소스 라벨 ----------------------------------------------

def _tokens(norm_label: str) -> set[str]:
    """정규화 라벨을 문자 단위 토큰 집합으로(한국어 라벨은 짧아 문자 자카드가 안정적)."""
    return set(norm_label)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


_FUZZY_THRESHOLD = 0.6


def _best_source_for_target(
    norm_target: str, source: dict[str, str]
) -> tuple[Optional[str], str, list[str]]:
    """타깃 정규화 라벨에 대한 best 소스 라벨을 보수적으로 고른다.

    반환: (선택 소스라벨 or None, confidence, 후보 리스트)
    - **자동 전사(high)는 ①정규화 정확일치 ②동의어 같은 클러스터 단일후보 만.**
    - 동의어 클러스터에 소스 후보가 2개 이상이면 ``"conflict"`` (자동전사 금지).
    - 정확일치·동의어가 없으면 퍼지(자카드·부분문자열)로 **제안만** → ``"fuzzy"``
      (자동전사 금지, needs_confirm). 접미사 다른 합성어(사업명/사업자명, 주소/주소지정)는
      클러스터가 다르므로 high 가 될 수 없고, 퍼지로만 제안된다.
    - 아무 후보도 없으면 ``"low"`` (미매칭).
    """
    # ① 정확일치 → high (단일)
    if norm_target in source:
        return norm_target, "high", []

    # ② 동의어 클러스터
    rep = _cluster_rep(norm_target)
    if rep is not None:
        syn_hits = [s for s in source if _cluster_rep(s) == rep]
        if len(syn_hits) == 1:
            return syn_hits[0], "high", []
        if len(syn_hits) > 1:
            return None, "conflict", syn_hits  # 충돌 → 자동전사 금지

    # ③ 퍼지: 자카드 ≥ 임계 또는 포함+길이차 작음 → 제안만(fuzzy), 자동전사 금지
    t_tokens = _tokens(norm_target)
    scored: list[tuple[float, str]] = []
    for s in source:
        s_tokens = _tokens(s)
        jac = _jaccard(t_tokens, s_tokens)
        contains = (norm_target in s or s in norm_target)
        len_close = abs(len(norm_target) - len(s)) <= 2
        if jac >= _FUZZY_THRESHOLD or (contains and len_close):
            scored.append((jac, s))
    if not scored:
        return None, "low", []
    scored.sort(key=lambda x: x[0], reverse=True)
    top_score = scored[0][0]
    top = [s for sc, s in scored if abs(sc - top_score) < 1e-9]
    return None, "fuzzy", top  # 단일이든 동점이든 자동전사 금지(제안만)


def match_fields(
    source: dict[str, str],
    targets: list[dict[str, Any]],
    source_originals: Optional[dict[str, str]] = None,
) -> list[Match]:
    """각 타깃에 best 소스 매칭을 산출한다.

    **high 단일 후보만** Match(전사 대상: source_label/value 채움)로 만든다.
    그 외(conflict·fuzzy·low)는 confidence 를 명확히 구분하고 ``value=""`` 로 표시 →
    autofill 단계가 needs_confirm/unmatched 로 분리한다. (충돌·퍼지가 confident 로
    새지 않도록 source_label 도 비운다.)

    추가 강등(오매칭은 빈칸보다 나쁘다):
    - **H2 중복 타깃**: 동일 정규화 타깃 라벨이 2개 이상이면 첫 1회만 high,
      나머지는 ``"duplicate"`` 로 강등(같은 값을 N칸에 복제 전사 방지).
    - **H3 괄호 토큰 충돌**: 정확일치라도 소스/타깃 원본 라벨의 괄호 토큰이
      서로 다르면(금액(국고) vs 금액(자부담)) ``"bracket"`` 로 강등(false high 방지).
    """
    source_originals = source_originals or {}
    matches: list[Match] = []
    high_seen: set[str] = set()  # 이미 high 전사된 정규화 타깃(H2 dedup)

    for tgt in targets:
        norm = tgt["normalized"]
        src_label, conf, candidates = _best_source_for_target(norm, source)

        demote_to: Optional[str] = None
        if conf == "high" and src_label is not None:
            # H3: 괄호 토큰이 다르면 high 금지(정확일치라도 다른 항목)
            if _bracket_conflict(source_originals.get(src_label, src_label),
                                 tgt["orig_label"]):
                demote_to = "bracket"
            # H2: 동일 정규화 타깃이 이미 high 전사됐으면 둘째부터 강등
            elif norm in high_seen:
                demote_to = "duplicate"

        if conf == "high" and src_label is not None and demote_to is None:
            high_seen.add(norm)
            matches.append(Match(
                target_label=tgt["orig_label"],
                normalized=norm,
                source_label=src_label,
                value=source[src_label],
                confidence="high",
                table_index=tgt["table_index"],
                row=tgt["row"],
                value_cell=tgt["value_cell"],
            ))
        else:
            # conflict / fuzzy / low / duplicate / bracket → 전사 보류.
            # source_label/value 모두 비움. 후보만 candidates 에 남긴다.
            final_conf = demote_to if demote_to is not None else conf
            cand = list(candidates)
            if demote_to is not None and src_label is not None and not cand:
                cand = [src_label]
            matches.append(Match(
                target_label=tgt["orig_label"],
                normalized=norm,
                source_label="",
                value="",
                confidence=final_conf,
                table_index=tgt["table_index"],
                row=tgt["row"],
                value_cell=tgt["value_cell"],
                candidates=cand,
            ))
    return matches


# --- 변환 헬퍼(HWP) -----------------------------------------------------------

def _to_docx_if_needed(path: Path, tmpdir: Path, report: AutofillReport) -> Optional[Path]:
    """입력이 .hwp/.hwpx 면 DOCX 로 변환해 그 경로를 반환. 실패 시 None."""
    if path.suffix.lower() not in _HWP_EXTS:
        return path
    from .hwp_docx_convert import hwp_to_docx

    out = tmpdir / (path.stem + "_in.docx")
    rep = hwp_to_docx(path, out)
    if rep.ok:
        report.notes.append(f"HWP 변환({path.name} → DOCX, {rep.method})")
        return out
    report.notes.append(f"HWP 변환 실패({path.name}): {'; '.join(rep.notes)}")
    return None


# --- 진입점 -------------------------------------------------------------------

def autofill_from_source(
    source: str | Path,
    target: str | Path,
    out: str | Path,
    *,
    use_ai: bool = False,
) -> AutofillReport:
    """소스 A 의 값을 타깃 B 의 빈 칸에 전사해 out 으로 저장한다(원본 미수정).

    절차: (HWP→DOCX 변환) → extract(소스) → find(타깃 빈칸) → match(보수)
          → **high 매칭만** 해당 값셀에 set_cell_text 로 직접 기입(잔여물/안내 청소 없음)
          → (out 이 .hwp 면 docx_to_hwp).
    잔여물/안내 청소 패스를 돌리지 않으므로 ``○○○``·``OOO-OO-OOOOO`` 같은 전사값이 보존된다.
    transcribed 는 실제 저장 문서에서 비어있지 않게 기입된 셀 수다.
    """
    source = Path(source)
    target = Path(target)
    out = Path(out)

    # 원본 보호: 출력이 소스/타깃과 같으면 거부(중간본은 tempfile)
    if source.exists() and out.resolve() == source.resolve():
        raise ValueError("출력 경로가 소스와 같습니다. 원본 덮어쓰기는 금지입니다.")
    if target.exists() and out.resolve() == target.resolve():
        raise ValueError("출력 경로가 타깃과 같습니다. 원본 덮어쓰기는 금지입니다.")

    report = AutofillReport(source=str(source), target=str(target), output=str(out))

    if not source.exists():
        raise FileNotFoundError(f"소스 파일이 없습니다: {source}")
    if not target.exists():
        raise FileNotFoundError(f"타깃 파일이 없습니다: {target}")
    if use_ai:
        report.notes.append("use_ai=True 는 v1 에서 미지원 — 결정론 매칭으로 진행")

    # H7: 지원 확장자 화이트리스트(.docx/.hwp/.hwpx). PDF/xlsx/위장파일은 보수적 거부.
    for role, p in (("소스", source), ("타깃", target)):
        if p.suffix.lower() not in _SUPPORTED_EXTS:
            report.ok = False
            report.notes.append(
                f"{role} 비지원 확장자({p.suffix or '없음'}) — .docx/.hwp/.hwpx 만 지원")
            return report

    # M6: 출력 상위 폴더가 없으면 자동 생성(중첩 경로 저장 시 크래시 방지)
    if out.parent and not out.parent.exists():
        out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="xform_") as td:
        tmpdir = Path(td)

        src_docx = _to_docx_if_needed(source, tmpdir, report)
        tgt_docx = _to_docx_if_needed(target, tmpdir, report)
        if src_docx is None or tgt_docx is None:
            report.ok = False
            return report

        # H7: 손상/위장 DOCX(PackageNotFoundError)는 raw traceback 대신 ok=False+notes.
        try:
            src_fields, src_originals = _extract_source(src_docx)
            tgt_fields = find_target_fields(tgt_docx)
        except PackageNotFoundError as exc:
            report.ok = False
            report.notes.append(f"DOCX 로딩 실패(손상/위장 파일 가능): {exc}")
            return report

        report.src_fields = len(src_fields)
        report.tgt_fields = len(tgt_fields)
        all_matches = match_fields(src_fields, tgt_fields, src_originals)

        # confident: confidence=="high" AND value 비어있지 않음 (충돌·퍼지·low 제외)
        confident = [
            m for m in all_matches
            if m.confidence == "high" and m.source_label and m.value
        ]
        for m in all_matches:
            if m in confident:
                continue
            if m.confidence == "low":
                report.unmatched_targets.append({
                    "target_label": m.target_label,
                    "normalized": m.normalized,
                })
            else:
                # conflict / fuzzy → 사람 확인 필요(자동전사 금지)
                report.needs_confirm.append({
                    "target_label": m.target_label,
                    "normalized": m.normalized,
                    "candidates": list(m.candidates),
                    "confidence": m.confidence,
                })

        # 전사 출력은 DOCX 중간본(tmp). out 이 .docx 면 바로, .hwp 면 변환.
        out_is_hwp = out.suffix.lower() in _HWP_EXTS
        docx_out = (tmpdir / (out.stem + "_filled.docx")) if out_is_hwp else out

        # 직접 쓰기: 타깃을 열어 (table_index,row,value_cell) 좌표에 set_cell_text 로
        # 값을 직접 기입한다. 잔여물/안내 청소 패스를 돌리지 않으므로 ○○○·OOO-… 보존.
        doc = Document(str(tgt_docx))
        transcribed = 0
        for m in confident:
            if m.table_index >= len(doc.tables):
                report.notes.append(f"전사 표 범위초과 ti={m.table_index}")
                continue
            table = doc.tables[m.table_index]
            if m.row >= len(table.rows):
                report.notes.append(f"전사 행 범위초과 ti={m.table_index} ri={m.row}")
                continue
            logical = _logical_cells(table.rows[m.row])
            if m.value_cell >= len(logical):
                report.notes.append(
                    f"전사 셀 범위초과 ti={m.table_index} ri={m.row} ci={m.value_cell}")
                continue
            set_cell_text(logical[m.value_cell], str(m.value))
            transcribed += 1
        doc.save(str(docx_out))

        report.matches = confident
        report.transcribed = transcribed

        # H6: 전사 0건/타깃 빈칸 0건은 "성공"으로 오인하지 않도록 보수적 처리.
        #     파일 저장은 됐어도 전사 성과가 없으므로 ok=False + 진단 경고.
        nothing_done = (transcribed == 0) or (report.tgt_fields == 0)
        if nothing_done:
            if report.tgt_fields == 0:
                report.notes.append(
                    "타깃에서 '라벨|빈칸' 구조를 찾지 못함(세로형/단일열/마스킹 등 구조 불일치 가능)")
            else:
                report.notes.append(
                    f"전사 0건 — 소스 {report.src_fields}필드/타깃 {report.tgt_fields}빈칸이나 "
                    f"보수적 매칭(high)에서 자동전사 대상 없음")

        if out_is_hwp:
            from .hwp_docx_convert import docx_to_hwp

            conv = docx_to_hwp(docx_out, out)
            if conv.ok:
                report.ok = not nothing_done
            else:
                # COM 미가용 등 — DOCX 보존(예외 전파 금지)
                fallback = out.with_suffix(".docx")
                Document(str(docx_out)).save(str(fallback))
                report.output = str(fallback)
                report.ok = False
                report.notes.append(
                    f"HWP 출력 실패 — DOCX 보존: {fallback.name} ({'; '.join(conv.notes)})")
        else:
            report.ok = not nothing_done

    return report
