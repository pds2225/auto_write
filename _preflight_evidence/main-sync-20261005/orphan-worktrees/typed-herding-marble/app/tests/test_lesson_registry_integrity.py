"""test_lesson_registry_integrity.py — L규칙(오답노트) 레지스트리 번호 무결성 게이트.

배경
----
``test_lessons_coverage.py`` 는 이미 두 가지를 지킨다: (A) mechanized 로 분류된
교훈의 가드 테스트가 실재하는지, (B) lessons.md 의 모든 헤딩이 커버리지 지도에
분류돼 있는지. 하지만 두 파일 모두 "항목 id **전체 문자열**"로만 중복을 검사한다
(``test_registry_wellformed`` 의 ``l["id"] not in seen_ids``) — 그래서 **같은 번호에
다른 카테고리·날짜·제목**이 붙은 진짜 충돌(예: 2026-08-07 에 실제로 발견된
L092/L095/L106/L108/L125 각 2건씩)은 전체 문자열이 다르므로 전혀 걸리지 않았다.

이 파일은 그 구멍을 **번호(canonical numeric id) 단위**로 막는다. lessons.md
(``D:\\.omc\\agent-learning\\lessons.md``, 정본) 가 없는 머신/CI 에서는 그 파일에
의존하는 검사만 skip 한다(repo-local 위생 불변식, 기존 파일과 동일한 정책).
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
_COVERAGE_JSON = _TESTS_DIR / "lessons_coverage.json"
_REPO_ROOT = _TESTS_DIR.parent.parent
_RESUME_L_RULES_SKILL = _REPO_ROOT / ".claude" / "skills" / "resume-l-rules" / "SKILL.md"

_ID_NUM_RE = re.compile(r"^L(\d+)")
_STANDARD_HEADER_RE = re.compile(r"^## (L\d+) \| ([^|]+) \| (\d{4}-\d{2}-\d{2}) \| (.+)$")
_ANY_HEADER_RE = re.compile(r"^##\s+(L\S.*)$")
_BODY_REF_RE = re.compile(r"\bL(\d{2,})\b")


def _lessons_md_path() -> Path | None:
    """오답노트 정본 경로(환경변수 우선). 없으면 None → 관련 검사 skip.

    ``test_lessons_coverage.py`` 의 ``_lessons_md_path`` 와 동일 정책(중복 구현
    은 의도적 — 두 파일이 서로 다른 이유로 실패할 때 원인을 분리하기 위함).
    """
    env = os.environ.get("AUTOWRITE_LESSONS_FILE")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    for cand in (Path.home() / ".omc" / "agent-learning" / "lessons.md",
                 Path(r"D:\.omc\agent-learning\lessons.md")):
        if cand.is_file():
            return cand
    return None


def _parse_lessons_md_headers(text: str) -> list[dict]:
    """``## L### | 카테고리 | 날짜 | 제목`` 헤딩만 표준으로 취급해 파싱한다.

    표준을 벗어난 헤딩(``## L1 — 제목`` 처럼 파이프 구분자가 없는 것)은 별도로
    ``test_all_headers_are_standard_format`` 이 잡는다 — 여기서는 섞이지 않게
    표준 정규식에 매칭되는 것만 모은다.
    """
    out = []
    for i, line in enumerate(text.splitlines()):
        m = _STANDARD_HEADER_RE.match(line.strip())
        if m:
            lid, cat, date, title = m.groups()
            out.append({"id": lid, "num": int(lid[1:]), "category": cat.strip(),
                        "date": date, "title": title.strip(), "line": i + 1})
    return out


def _numeric_id(raw_id: str) -> str | None:
    """coverage.json 의 ``id`` 필드(파이프 구분 문자열)에서 canonical 번호만 뽑는다."""
    first = raw_id.split("|")[0].strip().split(" ")[0].split("—")[0].strip()
    m = _ID_NUM_RE.match(first)
    return f"L{int(m.group(1))}" if m else None


def _load_coverage() -> dict:
    return json.loads(_COVERAGE_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# (1)(2)(3)(6) lessons.md 자체 — 번호 단위 중복 금지 + 표준 형식 강제.
#     정본 파일 의존이라 없는 머신/CI 는 skip.
# ---------------------------------------------------------------------------

def test_all_headers_are_standard_format() -> None:
    """``## L...`` 로 시작하는 모든 헤딩이 ``L### | 카테고리 | 날짜 | 제목`` 형식이어야 한다.

    2026-08-07 발견: ``## L1 — 제목``·``## L113 — 제목 (날짜)`` 처럼 파이프
    구분자가 없는 헤딩은 표준 파서(``_STANDARD_HEADER_RE``)를 조용히 통과해
    번호 충돌 검사에서 누락됐다. 형식 자체를 강제해 재발을 막는다.
    """
    lp = _lessons_md_path()
    if lp is None:
        pytest.skip("lessons.md 없음(다른 머신/CI) — repo-local 위생 불변식이라 skip")
    text = lp.read_text(encoding="utf-8")
    nonstandard = []
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        m_any = _ANY_HEADER_RE.match(s)
        if not m_any:
            continue
        if not _STANDARD_HEADER_RE.match(s):
            nonstandard.append(f"line {i + 1}: {s[:100]!r}")
    assert not nonstandard, (
        "lessons.md 에 '## L### | 카테고리 | 날짜 | 제목' 표준 형식이 아닌 헤딩이 있다"
        "(번호 충돌 검사가 이런 헤딩을 놓친다):\n  " + "\n  ".join(nonstandard)
    )


def test_no_duplicate_canonical_numbers_in_lessons_md() -> None:
    """같은 번호(Lxxx)가 서로 다른 제목으로 두 번 이상 쓰이면 실패한다.

    ``test_registry_wellformed`` 의 전체-문자열 중복검사가 놓치는 정확히 그
    구멍(2026-08-07 L092/L095/L106/L108/L125 각 2건 사고)을 번호 단위로 막는다.
    """
    lp = _lessons_md_path()
    if lp is None:
        pytest.skip("lessons.md 없음(다른 머신/CI) — repo-local 위생 불변식이라 skip")
    entries = _parse_lessons_md_headers(lp.read_text(encoding="utf-8"))
    assert entries, "lessons.md 에서 표준 헤딩을 하나도 못 찾음(형식 변경?)"
    by_num: dict[int, list[dict]] = defaultdict(list)
    for e in entries:
        by_num[e["num"]].append(e)
    dupes = {n: es for n, es in by_num.items() if len(es) > 1}
    assert not dupes, (
        "lessons.md 에 같은 번호가 서로 다른 규칙에 중복 배정됐다(L118 위반 — "
        "추가 전 실제 최대 번호를 다시 확인했어야 한다):\n  " + "\n  ".join(
            f"L{n:03d}: " + " / ".join(f"(line {e['line']}) {e['title'][:50]}" for e in es)
            for n, es in sorted(dupes.items())
        )
    )


def test_no_gaps_below_max_lessons_md_number() -> None:
    """L001 부터 최대 번호까지 빈 번호가 없어야 한다(번호 하나가 통째로 유실되지 않았는지).

    번호 재정렬은 금지 대상이지만, "쓰다가 하나를 통째로 빼먹는" 사고(예: coverage.json
    에는 있는데 본문에는 없던 옛 L113)는 별개 결함이라 여기서 잡는다.
    """
    lp = _lessons_md_path()
    if lp is None:
        pytest.skip("lessons.md 없음(다른 머신/CI) — repo-local 위생 불변식이라 skip")
    entries = _parse_lessons_md_headers(lp.read_text(encoding="utf-8"))
    nums = {e["num"] for e in entries}
    assert nums, "lessons.md 에서 표준 헤딩을 하나도 못 찾음"
    missing = sorted(n for n in range(1, max(nums) + 1) if n not in nums)
    assert not missing, (
        f"L001..L{max(nums):03d} 구간에 번호가 빠져 있다(본문 미기재 또는 삭제 의심): "
        + ", ".join(f"L{n:03d}" for n in missing)
    )


# ---------------------------------------------------------------------------
# (2) coverage.json 자체 — id 필드가 canonical 번호 형식(L + 숫자)이어야 한다.
#     JSON 만으로 자족적이라 항상 실행.
# ---------------------------------------------------------------------------

def test_coverage_json_ids_extract_canonical_number() -> None:
    """coverage.json 의 모든 ``id`` 필드에서 canonical 번호(L+숫자)를 추출할 수 있어야 한다.

    2026-08-07 발견: ``id: "L1 — 제목"``·``id: "L54 | ..."`` (실제 내용은 L083)
    처럼 번호 자체가 틀리거나 형식이 어긋난 항목이 있었다. 추출 실패 = 형식 위반.
    """
    data = _load_coverage()
    bad = []
    for item in data["lessons"]:
        raw = item.get("id", "")
        if _numeric_id(raw) is None:
            bad.append(raw)
    assert not bad, (
        "lessons_coverage.json 에 canonical 번호를 추출할 수 없는 id 가 있다:\n  "
        + "\n  ".join(repr(b) for b in bad)
    )


def test_coverage_json_no_duplicate_canonical_numbers() -> None:
    """coverage.json 안에서도 같은 canonical 번호가 두 항목에 쓰이면 실패한다."""
    data = _load_coverage()
    by_num: dict[str, list[str]] = defaultdict(list)
    for item in data["lessons"]:
        num = _numeric_id(item.get("id", ""))
        if num:
            by_num[num].append(item["id"])
    dupes = {n: ids for n, ids in by_num.items() if len(ids) > 1}
    assert not dupes, (
        "lessons_coverage.json 안에서 같은 canonical 번호가 중복 사용됐다:\n  "
        + "\n  ".join(f"{n}: {ids}" for n, ids in sorted(dupes.items()))
    )


# ---------------------------------------------------------------------------
# (7) 정본 ↔ coverage.json canonical 번호 집합 정합성.
# ---------------------------------------------------------------------------

def test_lessons_md_and_coverage_numeric_ids_match() -> None:
    """lessons.md 의 canonical 번호 집합과 coverage.json 의 canonical 번호 집합이 같아야 한다.

    ``test_all_current_lessons_are_classified`` (전체 문자열 기준)와 상호보완 —
    이쪽은 번호만 비교하므로 제목이 살짝 달라도(오타 등) 번호 누락은 반드시 잡는다.
    """
    lp = _lessons_md_path()
    if lp is None:
        pytest.skip("lessons.md 없음(다른 머신/CI) — repo-local 위생 불변식이라 skip")
    md_nums = {f"L{e['num']}" for e in _parse_lessons_md_headers(lp.read_text(encoding="utf-8"))}
    data = _load_coverage()
    cov_nums = {n for n in (_numeric_id(item.get("id", "")) for item in data["lessons"]) if n}

    only_in_md = sorted(md_nums - cov_nums, key=lambda x: int(x[1:]))
    only_in_cov = sorted(cov_nums - md_nums, key=lambda x: int(x[1:]))
    assert not only_in_md, f"lessons.md 에는 있지만 coverage.json 에 없는 번호: {only_in_md}"
    assert not only_in_cov, f"coverage.json 에는 있지만 lessons.md 에 없는 번호(고아 항목): {only_in_cov}"


# ---------------------------------------------------------------------------
# (8) resume-l-rules/SKILL.md 가 인용하는 L번호가 정본에 실재해야 한다.
# ---------------------------------------------------------------------------

def test_resume_l_rules_skill_references_exist() -> None:
    """resume-l-rules/SKILL.md 표에 나오는 L번호가 lessons.md 정본에 모두 존재해야 한다."""
    lp = _lessons_md_path()
    if lp is None:
        pytest.skip("lessons.md 없음(다른 머신/CI) — repo-local 위생 불변식이라 skip")
    if not _RESUME_L_RULES_SKILL.is_file():
        pytest.skip("resume-l-rules/SKILL.md 없음 — skip")
    md_nums = {e["num"] for e in _parse_lessons_md_headers(lp.read_text(encoding="utf-8"))}
    skill_text = _RESUME_L_RULES_SKILL.read_text(encoding="utf-8")
    # 표의 첫 열(| L### |)만 대상 — 본문 설명 속 우연한 L+숫자는 제외.
    referenced = set(int(n) for n in re.findall(r"^\|\s*L(\d+)\s*\|", skill_text, flags=re.MULTILINE))
    dangling = sorted(n for n in referenced if n not in md_nums)
    assert not dangling, (
        "resume-l-rules/SKILL.md 가 lessons.md 정본에 없는 번호를 인용한다: "
        + ", ".join(f"L{n:03d}" for n in dangling)
    )


# ---------------------------------------------------------------------------
# (9) lessons.md 본문 안의 상호참조(예: "L083 참조", "(L074/L091)")가
#     실제로 존재하는 canonical 번호를 가리키는지 — dangling 자기참조 검출.
# ---------------------------------------------------------------------------

def test_no_dangling_cross_references_in_lessons_md() -> None:
    """헤딩 안이 아니라 본문 텍스트에서 언급된 'Lxxx' 상호참조가 실재 번호여야 한다.

    100% 정확한 필터는 아니다(코드 식별자 등 우연한 'L\\d+' 오탐 가능) — 그래서
    **존재하지 않는 번호를 가리키는 경우만** 실패시킨다(과잉 매칭은 허용, 언더매칭만 방지).
    """
    lp = _lessons_md_path()
    if lp is None:
        pytest.skip("lessons.md 없음(다른 머신/CI) — repo-local 위생 불변식이라 skip")
    text = lp.read_text(encoding="utf-8")
    entries = _parse_lessons_md_headers(text)
    md_nums = {e["num"] for e in entries}
    header_lines = {e["line"] for e in entries}

    dangling: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if i in header_lines:
            continue  # 헤딩 자신의 번호는 상호참조가 아니다.
        for m in _BODY_REF_RE.finditer(line):
            n = int(m.group(1))
            # 3자리 미만(L1, L54 같은 표기오류)은 별도 형식 테스트가 담당 —
            # 여기서는 실제 lessons.md 번호 범위(최소 3자리)만 상호참조로 본다.
            if len(m.group(1)) < 3:
                continue
            if n not in md_nums:
                dangling.append(f"line {i}: L{n} — {line.strip()[:80]!r}")
    assert not dangling, (
        "lessons.md 본문에서 존재하지 않는 번호를 참조한다(dangling cross-reference):\n  "
        + "\n  ".join(dangling[:30])
    )


# ---------------------------------------------------------------------------
# (4)(5) alias/deprecated 필드 무결성 — 현재는 두 필드 모두 미사용(0건)이라
#     vacuous 하게 통과하지만, 앞으로 쓰일 때를 대비해 계약을 미리 고정한다.
# ---------------------------------------------------------------------------

def test_deprecated_and_alias_targets_exist_if_present() -> None:
    """항목에 ``deprecated_by``/``aliases`` 가 있으면 그 대상 canonical 번호가 실재해야 한다."""
    data = _load_coverage()
    all_nums = {n for n in (_numeric_id(item.get("id", "")) for item in data["lessons"]) if n}
    bad = []
    for item in data["lessons"]:
        dep_by = item.get("deprecated_by")
        if dep_by and dep_by not in all_nums:
            bad.append(f"{item['id'][:40]!r} deprecated_by={dep_by!r} (대상 없음)")
        for alias in item.get("aliases", []) or []:
            target = _numeric_id(alias) or alias
            if target not in all_nums:
                bad.append(f"{item['id'][:40]!r} alias={alias!r} (대상 없음)")
    assert not bad, "\n  ".join(["deprecated_by/alias 대상이 실재하지 않는다:"] + bad)
