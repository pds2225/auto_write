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

from .docx_ops import set_cell_text
from .submittable_filler import SubmittableFiller

_HWP_EXTS = {".hwp", ".hwpx"}


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
            "matches": [m.as_dict() for m in self.matches],
            "needs_confirm": self.needs_confirm,
            "unmatched_targets": self.unmatched_targets,
            "ok": self.ok,
            "notes": self.notes,
        }


# --- 추출: 소스에서 라벨→값 ----------------------------------------------------

_PARA_LABEL_VALUE_RE = re.compile(r"^\s*([^:：]{1,40})\s*[:：]\s*(.+?)\s*$")


def extract_source_fields(docx_path: str | Path) -> dict[str, str]:
    """소스 DOCX 의 표에서 (라벨,값) 쌍을 추출한다.

    - **짝수 인덱스(0,2,4…)만 라벨로** 본다: col0=라벨,col1=값,col2=라벨,col3=값.
      값 셀(홀수 인덱스)을 라벨로 쓰지 않으므로 ``[항목][연락처][010-…]`` 같은 행에서
      값 셀(연락처/010-…)이 라벨로 오염되지 않는다.
    - 정규화 라벨(_key)을 키로, 라벨·값 둘 다 비어있지 않을 때만 담는다(날조 0의 출발점).
    - 같은 정규화 라벨이 여러 번 나오면 처음 채워진 값을 유지한다.
    - 보조: 본문 단락의 "라벨: 값" 패턴도 추출(표에 없을 때만 보강).
    """
    doc = Document(str(docx_path))
    fields: dict[str, str] = {}

    for table in doc.tables:
        for row in table.rows:
            logical = _logical_cells(row)
            # 짝수 인덱스만 라벨: (0,1)(2,3)(4,5)… 쌍으로 처리
            for i in range(0, len(logical) - 1, 2):
                label = _key(logical[i].text)
                value = (logical[i + 1].text or "").strip()
                if not label or not value:
                    continue
                if label not in fields:
                    fields[label] = value

    # 보조: 본문 "라벨: 값" — 표에서 못 얻은 라벨만 보강
    for para in doc.paragraphs:
        m = _PARA_LABEL_VALUE_RE.match(para.text or "")
        if not m:
            continue
        label = _key(m.group(1))
        value = m.group(2).strip()
        if label and value and label not in fields:
            fields[label] = value

    return fields


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


def match_fields(source: dict[str, str], targets: list[dict[str, Any]]) -> list[Match]:
    """각 타깃에 best 소스 매칭을 산출한다.

    **high 단일 후보만** Match(전사 대상: source_label/value 채움)로 만든다.
    그 외(conflict·fuzzy·low)는 confidence 를 명확히 구분하고 ``value=""`` 로 표시 →
    autofill 단계가 needs_confirm/unmatched 로 분리한다. (충돌·퍼지가 confident 로
    새지 않도록 source_label 도 비운다.)
    """
    matches: list[Match] = []
    for tgt in targets:
        norm = tgt["normalized"]
        src_label, conf, candidates = _best_source_for_target(norm, source)
        if conf == "high" and src_label is not None:
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
            # conflict / fuzzy / low → 전사 보류. source_label/value 모두 비움.
            # 후보는 needs_confirm 리포트용으로만 candidates 에 남긴다.
            matches.append(Match(
                target_label=tgt["orig_label"],
                normalized=norm,
                source_label="",
                value="",
                confidence=conf,
                table_index=tgt["table_index"],
                row=tgt["row"],
                value_cell=tgt["value_cell"],
                candidates=list(candidates),
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

    with tempfile.TemporaryDirectory(prefix="xform_") as td:
        tmpdir = Path(td)

        src_docx = _to_docx_if_needed(source, tmpdir, report)
        tgt_docx = _to_docx_if_needed(target, tmpdir, report)
        if src_docx is None or tgt_docx is None:
            report.ok = False
            return report

        src_fields = extract_source_fields(src_docx)
        tgt_fields = find_target_fields(tgt_docx)
        all_matches = match_fields(src_fields, tgt_fields)

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

        if out_is_hwp:
            from .hwp_docx_convert import docx_to_hwp

            conv = docx_to_hwp(docx_out, out)
            if conv.ok:
                report.ok = True
            else:
                # COM 미가용 등 — DOCX 보존(예외 전파 금지)
                fallback = out.with_suffix(".docx")
                Document(str(docx_out)).save(str(fallback))
                report.output = str(fallback)
                report.ok = False
                report.notes.append(
                    f"HWP 출력 실패 — DOCX 보존: {fallback.name} ({'; '.join(conv.notes)})")
        else:
            report.ok = True

    return report
