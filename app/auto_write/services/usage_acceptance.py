"""usage_acceptance.py — 실사용 기준 수용 검사(acceptance) 엔진.

doc_quality_score(서식 청소 점수)와 측정 대상이 다르다.
여기서는 '심사위원·접수처 관점'에서 제출을 막는 하드페일 결함을 찾는다.
fail 등급 결함이 1개라도 있으면 제출불가(DRAFT) 판정이다.

- AI 호출 없음. 동일 입력 → 동일 결과(결정론).
- 본문 직계 단락 + 표 셀(중첩 포함) 전체를 검사한다.

검사 항목 (check_id / 등급)
---------------------------------
unresolved_markers     [확인필요] 등 미해결 작성 마커 잔존            fail
self_inserted_blocks   파이프라인 자기삽입 안내블록(NotebookLM 등) 잔존 fail
template_placeholders  양식 자리표시(<사진(이미지)>, OOO 등) 잔존      fail
unchecked_choices      '택 1'/'해당여부' 행에 선택 표시 없음           fail
empty_label_fields     명칭 등 필수 라벨 옆 칸 공란                    fail
font_name_mixing       폰트 이름 혼용(표 포함, 허용 4종 초과)          fail
font_size_spread       글자크기 과다 분산(7종 초과)·이상치(<8/>18pt)   warn
empty_table_rows       완전히 빈 표 행                                 warn
recruit_date_conflict  채용시기 표기 상호 모순                         warn
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from docx import Document
from docx.oxml.ns import qn

SEV_FAIL = "fail"
SEV_WARN = "warn"

_MAX_SAMPLES = 5

# --- 패턴 ------------------------------------------------------------------
_MARKER_RE = re.compile(r"\[확인필요[^\]]*\]|\[산출근거[^\]]*\]\s*\?|\[TODO[^\]]*\]")
_SELF_BLOCK_RE = re.compile(
    r"NotebookLM\s*슬라이드\s*생성용\s*프롬프트|이\s*블록은\s*삭제하세요|슬라이드\s*생성에\s*붙여넣으세요"
)
# 제거기(image_apply.strip_notebooklm_blocks)가 같은 정의를 쓰도록 공개한다 —
# 검출과 제거의 패턴이 어긋나면 '지웠는데 검출됨' 류의 재발이 생긴다.
SELF_BLOCK_RE = _SELF_BLOCK_RE
_PLACEHOLDER_RES = (
    re.compile(r"<\s*사진\s*\(이미지\)[^>]*>"),
    re.compile(r"<[^<>\n]{0,30}제목\s*>"),
    re.compile(r"(?<!\w)(OOO|○○○)(?!\w)"),
)
_CHECKBOX_ROW_RE = re.compile(r"택\s*1|해당\s*여부")
_CHECKED_MARKS = ("■", "☑", "✔", "▣", "☒", "√")
_LABEL_FIELDS = ("명 칭", "명칭", "기업명", "대표자명", "창업아이템명")
_DATE_TOKEN_RE = re.compile(r"[’'‘]\s?(\d{2})\s*\.\s*(\d{1,2})")
# 템플릿이 정상적으로 쓰는 폰트 조합(KISED 양식 기준) — 이 수를 넘으면 혼용으로 본다.
_ALLOWED_FONT_KINDS = 4
_ALLOWED_SIZE_KINDS = 7


@dataclass
class CheckResult:
    check_id: str
    label: str
    severity: str
    defects: int
    samples: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.defects == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id, "label": self.label,
            "severity": self.severity, "defects": self.defects,
            "passed": self.passed, "samples": self.samples, "detail": self.detail,
        }


@dataclass
class AcceptanceReport:
    source: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def submittable(self) -> bool:
        return all(r.passed for r in self.results if r.severity == SEV_FAIL)

    @property
    def fail_defects(self) -> int:
        return sum(r.defects for r in self.results if r.severity == SEV_FAIL)

    @property
    def warn_defects(self) -> int:
        return sum(r.defects for r in self.results if r.severity == SEV_WARN)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "submittable": self.submittable,
            "verdict": "제출가능" if self.submittable else "제출불가(DRAFT)",
            "fail_defects": self.fail_defects,
            "warn_defects": self.warn_defects,
            "checks": [r.as_dict() for r in self.results],
        }


# --- 순회 도우미 ------------------------------------------------------------

def _iter_cells(tables) -> Iterator:
    for table in tables:
        for row in table.rows:
            for cell in row.cells:
                yield cell
                if cell.tables:
                    yield from _iter_cells(cell.tables)


def _dedup_cells(doc: Document):
    """병합 중복을 제거한 셀 목록.

    주의: lxml 요소 proxy 는 참조가 사라지면 메모리(id)가 재사용될 수 있어
    id 만 저장하면 서로 다른 셀이 '본 것'으로 오판된다(과소 집계 버그).
    refs 리스트로 proxy 참조를 유지해 id 안정성을 보장한다.
    """
    seen_ids: set[int] = set()
    refs: list = []          # proxy 생존 유지용 — 삭제 금지
    out = []
    for cell in _iter_cells(doc.tables):
        tc = cell._tc
        if id(tc) in seen_ids:
            continue
        seen_ids.add(id(tc))
        refs.append(tc)
        out.append(cell)
    return out


def _iter_all_texts(doc: Document) -> Iterator[tuple[str, str]]:
    """(위치, 텍스트) — 본문 단락과 표 셀(중첩 포함)을 모두 낸다."""
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            yield ("본문", t)
    for cell in _dedup_cells(doc):
        t = cell.text.strip()
        if t:
            yield ("표", t)


def _iter_all_runs(doc: Document):
    for p in doc.paragraphs:
        yield from p.runs
    for cell in _dedup_cells(doc):
        for p in cell.paragraphs:
            yield from p.runs


def _row_cells_dedup(row) -> list[str]:
    """병합 셀 중복을 제거한 행 셀 텍스트 목록."""
    out: list[str] = []
    seen: list = []
    for cell in row.cells:
        tc = cell._tc
        if any(tc is s for s in seen):
            continue
        seen.append(tc)
        out.append(cell.text.strip())
    return out


def _scan_regex(doc: Document, regexes) -> tuple[int, list[str]]:
    n, samples = 0, []
    for where, text in _iter_all_texts(doc):
        hits = 0
        for rx in regexes:
            hits += len(rx.findall(text))
        if hits:
            n += hits
            if len(samples) < _MAX_SAMPLES:
                samples.append(f"[{where}] {text[:40]}")
    return n, samples


# --- 개별 검사 ---------------------------------------------------------------

def check_unresolved_markers(doc: Document) -> CheckResult:
    n, s = _scan_regex(doc, (_MARKER_RE,))
    return CheckResult("unresolved_markers", "[확인필요] 등 미해결 마커", SEV_FAIL, n, s,
                       f"마커 {n}개 — 전부 실제 값으로 치환해야 제출 가능")


def check_self_inserted_blocks(doc: Document) -> CheckResult:
    n = 0
    samples: list[str] = []
    for where, text in _iter_all_texts(doc):
        if _SELF_BLOCK_RE.search(text):
            n += 1
            if len(samples) < _MAX_SAMPLES:
                samples.append(f"[{where}] {text[:40]}")
    return CheckResult("self_inserted_blocks", "자기삽입 안내블록 잔존", SEV_FAIL, n, samples,
                       f"파이프라인이 삽입한 작업용 블록 {n}개 잔존 — 제출본에서는 0이어야 함")


def check_template_placeholders(doc: Document) -> CheckResult:
    """자리표시 검출 — 패턴이 겹쳐도(동일 구간 이중매치) 1건으로 센다."""
    n = 0
    samples: list[str] = []
    for where, text in _iter_all_texts(doc):
        spans: list[tuple[int, int]] = []
        for rx in _PLACEHOLDER_RES:
            spans.extend(m.span() for m in rx.finditer(text))
        if not spans:
            continue
        spans.sort()
        merged = 0
        cur_end = -1
        for a, b in spans:
            if a >= cur_end:
                merged += 1
                cur_end = b
            else:
                cur_end = max(cur_end, b)
        n += merged
        if len(samples) < _MAX_SAMPLES:
            samples.append(f"[{where}] {text[:40]}")
    return CheckResult("template_placeholders", "양식 자리표시 잔존", SEV_FAIL, n, samples,
                       f"<사진(이미지)>·OOO 등 자리표시 {n}개")


def check_unchecked_choices(doc: Document) -> CheckResult:
    defects = 0
    samples: list[str] = []
    seen_labels: set[str] = set()
    def _walk(tables):
        nonlocal defects
        for table in tables:
            for row in table.rows:
                cells = _row_cells_dedup(row)
                row_text = " ".join(cells)
                if not _CHECKBOX_ROW_RE.search(row_text):
                    continue
                label = cells[0][:20] if cells else row_text[:20]
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                if "□" in row_text and not any(m in row_text for m in _CHECKED_MARKS):
                    defects += 1
                    if len(samples) < _MAX_SAMPLES:
                        samples.append(f"[표] {row_text[:40]}")
            for row in table.rows:
                for cell in row.cells:
                    if cell.tables:
                        _walk(cell.tables)
    _walk(doc.tables)
    return CheckResult("unchecked_choices", "선택란(택1·해당여부) 미체크", SEV_FAIL, defects, samples,
                       f"체크 표시(■ 등) 없는 선택 행 {defects}개")


def check_empty_label_fields(doc: Document) -> CheckResult:
    defects = 0
    samples: list[str] = []
    def _walk(tables):
        nonlocal defects
        for table in tables:
            for row in table.rows:
                cells = _row_cells_dedup(row)
                for i, c in enumerate(cells[:-1]):
                    if c in _LABEL_FIELDS and not cells[i + 1]:
                        defects += 1
                        if len(samples) < _MAX_SAMPLES:
                            samples.append(f"[표] '{c}' 옆 칸 공란")
            for row in table.rows:
                for cell in row.cells:
                    if cell.tables:
                        _walk(cell.tables)
    _walk(doc.tables)
    return CheckResult("empty_label_fields", "필수 라벨 옆 칸 공란", SEV_FAIL, defects, samples,
                       f"공란 필수칸 {defects}개")


def check_font_name_mixing(doc: Document) -> CheckResult:
    names: set[str] = set()
    for run in _iter_all_runs(doc):
        if not (run.text or "").strip():
            continue
        if run.font.name:
            names.add(run.font.name)
        rpr = run._element.rPr
        if rpr is not None and rpr.rFonts is not None:
            ea = rpr.rFonts.get(qn("w:eastAsia"))
            if ea:
                names.add(ea)
    over = max(0, len(names) - _ALLOWED_FONT_KINDS)
    return CheckResult("font_name_mixing", "폰트 이름 혼용(표 포함)", SEV_FAIL, over,
                       sorted(names)[:_MAX_SAMPLES + 4],
                       f"사용 폰트 {len(names)}종 (허용 {_ALLOWED_FONT_KINDS}종)")


def check_font_size_spread(doc: Document) -> CheckResult:
    sizes: set[float] = set()
    outliers = 0
    for run in _iter_all_runs(doc):
        if not (run.text or "").strip() or run.font.size is None:
            continue
        pt = run.font.size.pt
        sizes.add(pt)
        if pt < 8 or pt > 18:
            outliers += 1
    over = max(0, len(sizes) - _ALLOWED_SIZE_KINDS) + (1 if outliers else 0)
    return CheckResult("font_size_spread", "글자크기 분산·이상치", SEV_WARN, over,
                       [f"{s}pt" for s in sorted(sizes)],
                       f"크기 {len(sizes)}종, 이상치(8pt 미만/18pt 초과) {outliers}개")


def check_empty_table_rows(doc: Document) -> CheckResult:
    defects = 0
    for table in doc.tables:
        for row in table.rows:
            cells = _row_cells_dedup(row)
            if cells and all(not c for c in cells):
                defects += 1
    return CheckResult("empty_table_rows", "완전히 빈 표 행", SEV_WARN, defects, [],
                       f"빈 행 {defects}개")


def check_recruit_date_conflict(doc: Document) -> CheckResult:
    tokens: set[str] = set()
    samples: list[str] = []
    for where, text in _iter_all_texts(doc):
        if "채용" not in text:
            continue
        for y, m in _DATE_TOKEN_RE.findall(text):
            tok = f"'{y}.{int(m)}"
            if tok not in tokens and len(samples) < _MAX_SAMPLES:
                samples.append(f"[{where}] {tok} ← {text[:30]}")
            tokens.add(tok)
    defects = max(0, len(tokens) - 1)
    return CheckResult("recruit_date_conflict", "채용시기 표기 모순", SEV_WARN, defects, samples,
                       f"서로 다른 채용시기 표기 {len(tokens)}종: {sorted(tokens)}")


_ALL_CHECKS = (
    check_unresolved_markers,
    check_self_inserted_blocks,
    check_template_placeholders,
    check_unchecked_choices,
    check_empty_label_fields,
    check_font_name_mixing,
    check_font_size_spread,
    check_empty_table_rows,
    check_recruit_date_conflict,
)


def run_acceptance(path: str | Path) -> AcceptanceReport:
    """DOCX 1개에 대해 전체 수용 검사를 실행한다 (읽기 전용)."""
    path = Path(path)
    doc = Document(str(path))
    report = AcceptanceReport(source=str(path))
    for check in _ALL_CHECKS:
        report.results.append(check(doc))
    return report


def force_draft_name(path: Path, *, avoid: Path | None = None) -> tuple[Path, str]:
    """게이트 정책(R7/R8) 파일명 유틸 — 제출불가 판정 파일에 ``_DRAFT`` 를 강제한다.

    검사(run_acceptance)는 읽기 전용이고, 이 헬퍼는 게이트(파이프라인)만 호출한다.
    이미 ``_DRAFT`` 이름이면 그대로 둔다. 목표 이름이 ``avoid``(예: 입력 원본)와
    겹치면 덮어쓰지 않고 ``_DRAFT2`` 로 마킹한다(원본 보존).

    Returns:
        (최종 경로, 오류 문자열). rename 실패(파일 잠금 등) 시 경로는 원래대로
        남고 오류 문자열이 채워진다 — 호출자는 이를 사용자에게 반드시 알려야 한다.
    """
    if path.stem.endswith("_DRAFT") or path.stem.endswith("_DRAFT2"):
        return path, ""
    draft = path.with_name(f"{path.stem}_DRAFT{path.suffix}")
    if avoid is not None and draft.resolve() == avoid.resolve():
        draft = path.with_name(f"{path.stem}_DRAFT2{path.suffix}")
    try:
        path.replace(draft)
    except OSError as exc:
        return path, f"{type(exc).__name__}: {exc}"
    return draft, ""
