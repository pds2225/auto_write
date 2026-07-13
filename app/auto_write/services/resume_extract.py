"""resume_extract.py — 원본 이력서(들) → 구조화 프로필(profile.json).

범용 이력서 자동작성기 P1(M1). 소스 이력서 파일 N개(또는 폴더)를 읽어
identity/education/career/certs/lectures/projects/publications 로 구조화한다.

원칙(불변)
---------
- **날조 0**: 소스에 없는 필드는 ``None`` + ``needs_confirm`` 목록으로 노출한다.
  파서가 지어내지 않는다.
- **충돌 = 최신/상위 우선 + 병기**: 여러 이력서가 같은 항목을 다르게 적으면
  pick 스코어 상위(=최신·적합) 파일 값을 채택하고 충돌 내역을 needs_confirm 에 남긴다.
- **원본 미수정**: 읽기 전용.

재사용
------
- 소스 텍스트화: ``doc_text_extract.extract_text`` (HWP/HWPX/DOCX/PDF → 텍스트,
  표는 ``" | "`` 로 평문화).
- 소스 우선순위: ``cross_form_autofill.rank_source_pool`` (키워드+이력서보너스+파일명날짜).

파서는 순수 함수(``parse_profile_text``)로 분리해 COM/파일 없이 테스트한다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .doc_text_extract import extract_text

__all__ = [
    "Education",
    "Career",
    "Cert",
    "Lecture",
    "Project",
    "ResumeProfile",
    "ProfileBuildResult",
    "parse_profile_text",
    "extract_profile_from_file",
    "merge_profiles",
    "build_profile",
    "IDENTITY_KEYS",
]

_CELL_SEP = "|"
# 표 셀 중 사진 자리표시 등 무의미한 값(모두의장 양식의 마지막 "이미지" 칸).
_DROP_CELLS = {"이미지", "사진", "(사진)", "photo", ""}

# identity 라벨 정규화(공백 제거 후 매칭) → 표준 키.
_IDENTITY_LABELS = {
    "성명": "name",
    "성명(국문)": "name",
    "성명(영문)": "name_en",
    "소속": "org",
    "성별": "gender",
    "직위": "position",
    "직책": "position",
    "핸드폰": "phone",
    "휴대폰": "phone",
    "전화": "phone",
    "연락처": "phone",
    "생년월일": "birth",
    "이메일": "email",
    "e-mail": "email",
    "주소(사업장)": "address_work",
    "주소(거주지)": "address_home",
    "주소": "address_home",
    "컨설팅분야": "field",
    "전문분야": "field",
    "팩스": "fax",
}

# profile.json 에 항상 존재해야 하는 identity 키(없으면 None + needs_confirm).
IDENTITY_KEYS = (
    "name", "gender", "org", "position", "phone", "birth",
    "email", "address_work", "address_home", "field",
)


def _norm_label(cell: str) -> str:
    """라벨 셀을 공백 제거·소문자로 정규화(『성 명』→『성명』)."""
    return re.sub(r"\s+", "", cell).lower()


def _split_cells(line: str) -> list[str]:
    """``a | b | c`` → [a, b, c]. 앞뒤 공백 제거, 사진 자리표시 셀 제거."""
    if _CELL_SEP not in line:
        return []
    cells = [c.strip() for c in line.split(_CELL_SEP)]
    # 뒤쪽 "이미지"/빈 자리표시 셀만 제거(앞쪽 값은 보존).
    while cells and _norm_label(cells[-1]) in {_norm_label(x) for x in _DROP_CELLS}:
        cells.pop()
    return cells


# --- 데이터 클래스 -----------------------------------------------------------
@dataclass
class Education:
    period: Optional[str] = None
    school: Optional[str] = None
    major: Optional[str] = None
    degree: Optional[str] = None

    def as_dict(self) -> dict:
        return {"period": self.period, "school": self.school,
                "major": self.major, "degree": self.degree}

    def key(self) -> tuple:
        # period 포함(학과/학위 공란 시 서로 다른 학력이 조용히 합쳐지는 것 방지).
        return (self.period, self.school, self.major, self.degree)


@dataclass
class Career:
    period: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    duty: Optional[str] = None

    def as_dict(self) -> dict:
        return {"period": self.period, "company": self.company,
                "position": self.position, "duty": self.duty}

    def key(self) -> tuple:
        return (self.period, self.company)


@dataclass
class Cert:
    date: Optional[str] = None
    name: Optional[str] = None
    number: Optional[str] = None
    issuer: Optional[str] = None

    def as_dict(self) -> dict:
        return {"date": self.date, "name": self.name,
                "number": self.number, "issuer": self.issuer}

    def key(self) -> tuple:
        # 발급번호가 있으면 그것으로, 없으면 date/issuer 로 구분(갱신 자격 유실 방지).
        if self.number:
            return (self.name, self.number)
        return (self.name, self.date, self.issuer)


@dataclass
class Lecture:
    date: Optional[str] = None
    org: Optional[str] = None
    topic: Optional[str] = None
    count: Optional[str] = None
    kind: Optional[str] = None

    def as_dict(self) -> dict:
        return {"date": self.date, "org": self.org, "topic": self.topic,
                "count": self.count, "kind": self.kind}

    def key(self) -> tuple:
        return (self.date, self.org, self.topic)


@dataclass
class Project:
    period: Optional[str] = None
    name: Optional[str] = None
    content: Optional[str] = None
    client: Optional[str] = None

    def as_dict(self) -> dict:
        return {"period": self.period, "name": self.name,
                "content": self.content, "client": self.client}

    def key(self) -> tuple:
        return (self.period, self.name, self.client)


@dataclass
class ResumeProfile:
    identity: dict = field(default_factory=dict)
    education: list = field(default_factory=list)
    career: list = field(default_factory=list)
    certs: list = field(default_factory=list)
    lectures: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    publications: list = field(default_factory=list)
    sources: list = field(default_factory=list)

    def as_dict(self) -> dict:
        ident = {k: self.identity.get(k) for k in IDENTITY_KEYS}
        # 표준 키 외에 잡힌 값(name_en·fax 등)도 보존.
        for k, v in self.identity.items():
            if k not in ident:
                ident[k] = v
        return {
            "identity": ident,
            "education": [e.as_dict() for e in self.education],
            "career": [c.as_dict() for c in self.career],
            "certs": [c.as_dict() for c in self.certs],
            "lectures": [l.as_dict() for l in self.lectures],
            "projects": [p.as_dict() for p in self.projects],
            "publications": list(self.publications),
            "sources": list(self.sources),
        }


@dataclass
class ProfileBuildResult:
    profile: ResumeProfile
    needs_confirm: list = field(default_factory=list)
    merged_sources: list = field(default_factory=list)
    skipped_sources: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        d = self.profile.as_dict()
        d["needs_confirm"] = list(self.needs_confirm)
        d["merged_sources"] = list(self.merged_sources)
        d["skipped_sources"] = list(self.skipped_sources)
        d["notes"] = list(self.notes)
        return d


# --- 섹션 헤더 인식 ----------------------------------------------------------
def _match_section_header(cells: list[str]) -> Optional[str]:
    """표 헤더행이면 섹션명 반환, 아니면 None. 셀 라벨 시그니처로 판정."""
    if not cells:
        return None
    # 헤더행은 라벨행이라 날짜로 시작하지 않는다. 날짜 선두면 데이터행 → 헤더 오인 방지
    # (데이터 내용에 '학교명·학위·강의주제' 등 시그니처 단어가 섞여도 헤더로 안 삼킴).
    if _DATE_LEAD_RE.match(cells[0]):
        return None
    norm = [_norm_label(c) for c in cells]
    joined = "".join(norm)
    if "학교명" in joined and "학위" in joined:
        return "education"
    if "직장명" in joined and ("담당업무" in joined or "직위" in joined):
        return "career"
    if "자격증명" in joined and ("발급번호" in joined or "발급기관" in joined):
        return "certs"
    if "강의주제" in joined or ("주최기관명" in joined and "회차" in joined):
        return "lectures"
    if "프로젝트명" in joined and ("수행내용" in joined or "발주처" in joined):
        return "projects"
    return None


def _strip_section_tag(cells: list[str], tag: str) -> list[str]:
    """선두 셀이 섹션 태그(학력/경력/자격)면 제거한 나머지를 반환."""
    if cells and _norm_label(cells[0]) == _norm_label(tag):
        return cells[1:]
    return cells


def _section_data_body(cells: list[str], tag: str) -> Optional[list[str]]:
    """education/career/certs 데이터행이면 (태그 제거한) body 반환, 아니면 None.

    섹션이 활성이어도 아무 행이나 삼키지 않는다(날조 방지). 데이터로 인정하는 경우:
    ① 선두 셀이 섹션 태그(학력/경력/자격) → 태그 뒤가 body,
    ② 태그가 없어도 기간/일자 칸(첫 셀)이 날짜 선두(2020.01 …).
    선두 셀이 identity 라벨(성명·소속 등)이거나 위 조건 미충족이면 None
    → 호출측이 identity 파싱으로 fall-through(섹션 뒤 서명/머리행 오삼킴 차단)."""
    if not cells:
        return None
    if _norm_label(cells[0]) in _IDENTITY_LABELS:
        return None
    if _norm_label(cells[0]) == _norm_label(tag):
        return cells[1:]
    first = _val(cells, 0)
    if first and _DATE_LEAD_RE.match(first):
        return cells
    return None


def _val(cells: list[str], idx: int) -> Optional[str]:
    if 0 <= idx < len(cells):
        v = cells[idx].strip()
        return v or None
    return None


_DATE_LEAD_RE = re.compile(r"^\s*\d{4}[.\-]")
_PUB_RE = re.compile(r"[『「].+[』」]")


# --- 파서(순수 함수) ---------------------------------------------------------
def parse_profile_text(text: str, source: Optional[str] = None) -> ResumeProfile:
    """평문화된 이력서 텍스트를 구조화 프로필로 파싱한다(날조 없음)."""
    prof = ResumeProfile()
    if source:
        prof.sources.append(str(source))
    section: Optional[str] = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # publications: 『...』 인용 라인(표 밖).
        if _PUB_RE.search(line) and _CELL_SEP not in line:
            if line not in prof.publications:
                prof.publications.append(line)
            continue

        cells = _split_cells(line)
        if not cells:
            continue

        # 섹션 헤더?
        hdr = _match_section_header(cells)
        if hdr is not None:
            section = hdr
            continue

        # 섹션 데이터행 파싱. 섹션 데이터로 인식될 때만 소비(continue)하고,
        # 아니면 아래 identity 파싱으로 fall-through 한다(섹션 뒤 서명/머리행 오삼킴·날조 차단).
        if section == "education":
            body = _section_data_body(cells, "학력")
            if body is not None:
                if _val(body, 0) or _val(body, 1):
                    prof.education.append(Education(
                        period=_val(body, 0), school=_val(body, 1),
                        major=_val(body, 2), degree=_val(body, 3)))
                continue
        elif section == "career":
            body = _section_data_body(cells, "경력")
            if body is not None:
                if _val(body, 0) or _val(body, 1):
                    prof.career.append(Career(
                        period=_val(body, 0), company=_val(body, 1),
                        position=_val(body, 2), duty=_val(body, 3)))
                continue
        elif section == "certs":
            body = _section_data_body(cells, "자격")
            if body is not None:
                if _val(body, 0) or _val(body, 1):
                    prof.certs.append(Cert(
                        date=_val(body, 0), name=_val(body, 1),
                        number=_val(body, 2), issuer=_val(body, 3)))
                continue
        elif section == "lectures":
            if _DATE_LEAD_RE.match(cells[0]):
                prof.lectures.append(Lecture(
                    date=_val(cells, 0), org=_val(cells, 1), topic=_val(cells, 2),
                    count=_val(cells, 3), kind=_val(cells, 4)))
                continue
            # 날짜 선두가 아니면 섹션 종료 후보 → identity 로 넘김.
        elif section == "projects":
            if _DATE_LEAD_RE.match(cells[0]):
                prof.projects.append(Project(
                    period=_val(cells, 0), name=_val(cells, 1),
                    content=_val(cells, 2), client=_val(cells, 3)))
                continue

        # identity 라벨-값 행(섹션 밖·섹션 시작 전·섹션 뒤 비데이터 행).
        _parse_identity_row(cells, prof.identity)

    return prof


def _parse_identity_row(cells: list[str], identity: dict) -> None:
    """``라벨 | 값 [| 라벨 | 값]`` identity 행 파싱. 값 반복 칸은 무시."""
    if len(cells) < 2:
        return
    # 첫 쌍
    _assign_identity(cells[0], cells[1], identity)
    # 둘째 쌍: cells[2] 가 알려진 라벨이고 cells[3] 이 있을 때만(값 반복과 구분).
    if len(cells) >= 4 and _norm_label(cells[2]) in _IDENTITY_LABELS:
        _assign_identity(cells[2], cells[3], identity)


def _assign_identity(label: str, value: str, identity: dict) -> None:
    key = _IDENTITY_LABELS.get(_norm_label(label))
    if not key:
        return
    v = value.strip()
    if not v or _norm_label(v) in {_norm_label(x) for x in _DROP_CELLS}:
        return
    # 먼저 채운 값(상위 소스/상단 행) 우선 — 덮어쓰지 않음.
    identity.setdefault(key, v)


# --- 파일 추출 ---------------------------------------------------------------
def extract_profile_from_file(path: str | Path) -> tuple[ResumeProfile, list[str]]:
    """단일 이력서 파일 → (ResumeProfile, notes)."""
    p = Path(path)
    text, notes = extract_text(p)
    if not text.strip():
        return ResumeProfile(sources=[str(p)]), notes
    return parse_profile_text(text, source=str(p)), notes


# --- 병합 --------------------------------------------------------------------
def _dedup_extend(dst: list, src: list) -> None:
    seen = {item.key() for item in dst}
    for item in src:
        k = item.key()
        if k not in seen:
            dst.append(item)
            seen.add(k)


def merge_profiles(profiles: list[ResumeProfile]) -> tuple[ResumeProfile, list[str]]:
    """여러 프로필을 상위(우선순위 높은 것 먼저) → 하위 순으로 병합.

    identity 는 상위 우선(먼저 채운 값 유지), 충돌 시 needs_confirm 에 병기.
    리스트는 dedup union. 반환: (merged, needs_confirm).
    """
    merged = ResumeProfile()
    needs_confirm: list[str] = []
    for prof in profiles:
        merged.sources.extend(prof.sources)
        for key, val in prof.identity.items():
            if key not in merged.identity:
                merged.identity[key] = val
            elif merged.identity[key] != val:
                src = Path(prof.sources[0]).name if prof.sources else "?"
                needs_confirm.append(
                    f"[충돌] {key}: '{merged.identity[key]}' 채택(상위) / "
                    f"'{val}'({src}) 무시 — 확인 필요")
        _dedup_extend(merged.education, prof.education)
        _dedup_extend(merged.career, prof.career)
        _dedup_extend(merged.certs, prof.certs)
        _dedup_extend(merged.lectures, prof.lectures)
        _dedup_extend(merged.projects, prof.projects)
        for pub in prof.publications:
            if pub not in merged.publications:
                merged.publications.append(pub)

    # 필수 identity 키 누락 → needs_confirm(날조 금지: null 로 남김).
    for k in IDENTITY_KEYS:
        if not merged.identity.get(k):
            needs_confirm.append(f"[미확인] identity.{k}: 소스에 값 없음 — 확인/입력 필요")
    return merged, needs_confirm


# --- 빌드(폴더/파일 → profile.json 재료) ------------------------------------
def build_profile(
    inputs: list[str | Path],
    *,
    recursive: bool = True,
    prefer_resume: bool = True,
    limit: Optional[int] = 8,
) -> ProfileBuildResult:
    """이력서 파일들 또는 폴더 → 병합 프로필 + needs_confirm.

    폴더가 주어지면 pick 스코어(rank_source_pool)로 상위 정렬 후 상위 ``limit`` 개만
    병합한다(``limit=None`` 이면 전체). 어떤 파일을 병합/생략했는지 리포트한다.
    """
    from .cross_form_autofill import list_source_pool, rank_source_pool

    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            report = rank_source_pool(
                p, recursive=recursive, prefer_resume=prefer_resume, use_dry_run=False)
            ranked = [Path(s.path) for s in report.scores]
            if not ranked:
                ranked = list_source_pool(p, recursive=recursive)
            files.extend(ranked)
            # rank/list_source_pool 은 양식(docx/hwp/hwpx)만 본다. extract_text 가 지원하는
            # pdf/txt 이력서도 포함(폴더↔파일-직접 인자 파리티). 중복은 아래 seen 이 제거.
            globber = p.rglob if recursive else p.glob
            for ext in ("*.pdf", "*.txt"):
                files.extend(sorted(globber(ext)))
        elif p.is_file():
            files.append(p)

    # 중복 경로 제거(순서 보존).
    seen: set[str] = set()
    ordered: list[Path] = []
    for f in files:
        s = str(f)
        if s not in seen:
            seen.add(s)
            ordered.append(f)

    skipped: list[str] = []
    if limit is not None and len(ordered) > limit:
        skipped = [str(f) for f in ordered[limit:]]
        ordered = ordered[:limit]

    profiles: list[ResumeProfile] = []
    merged_sources: list[str] = []
    notes: list[str] = []
    for f in ordered:
        prof, fnotes = extract_profile_from_file(f)
        # 값이 하나도 안 나온 파일은 병합에서 제외(잡음 방지).
        if (prof.identity or prof.education or prof.career or prof.certs
                or prof.lectures or prof.projects or prof.publications):
            profiles.append(prof)
            merged_sources.append(str(f))
        else:
            skipped.append(str(f))
        for n in fnotes:
            tagged = f"{Path(f).name}: {n}"
            if tagged not in notes:
                notes.append(tagged)

    if not profiles:
        return ProfileBuildResult(
            profile=ResumeProfile(), needs_confirm=["소스에서 추출된 항목이 없습니다."],
            merged_sources=[], skipped_sources=skipped, notes=notes)

    merged, needs_confirm = merge_profiles(profiles)
    if skipped:
        notes.append(f"병합 {len(merged_sources)}개 · 생략 {len(skipped)}개"
                     f"(limit={limit}) — 생략분은 --all 또는 --limit 로 포함 가능.")
    return ProfileBuildResult(
        profile=merged, needs_confirm=needs_confirm,
        merged_sources=merged_sources, skipped_sources=skipped, notes=notes)


def profile_to_json(result: ProfileBuildResult, *, indent: int = 2) -> str:
    return json.dumps(result.as_dict(), ensure_ascii=False, indent=indent)


def format_build_korean(result: ProfileBuildResult) -> str:
    """CLI 요약용 한국어 리포트."""
    p = result.profile
    lines = [
        "=== 이력서 프로필 추출 결과 ===",
        f"병합 소스: {len(result.merged_sources)}개",
    ]
    for s in result.merged_sources:
        lines.append(f"  · {Path(s).name}")
    if result.skipped_sources:
        lines.append(f"생략 소스: {len(result.skipped_sources)}개 (limit 초과/무추출)")
    lines.append("")
    lines.append(f"성명: {p.identity.get('name') or '(없음)'}"
                 f" · 소속: {p.identity.get('org') or '(없음)'}")
    lines.append(f"학력 {len(p.education)} · 경력 {len(p.career)} · 자격 {len(p.certs)}"
                 f" · 강의 {len(p.lectures)} · 수행 {len(p.projects)}"
                 f" · 저서/논문 {len(p.publications)}")
    if result.needs_confirm:
        lines.append("")
        lines.append(f"⚠ 확인 필요 {len(result.needs_confirm)}건:")
        for nc in result.needs_confirm:
            lines.append(f"  - {nc}")
    if result.notes:
        lines.append("")
        lines.append("비고:")
        for n in result.notes:
            lines.append(f"  · {n}")
    return "\n".join(lines)
