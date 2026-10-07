"""test_lessons_coverage.py — 오답노트 교훈 ↔ 코드 가드 커버리지 SSOT 메타테스트.

배경 ("부활방지"의 핵심)
------------------------
자가학습 오답노트(``~/.omc/agent-learning/lessons.md``)에는 70여 건의 교훈이 쌓여
있지만, 그 중 코드/테스트로 실제 강제되는 것과 사람 판단으로만 남은 것이 뒤섞여
있어 **어떤 교훈이 기계적으로 재발 방지되는지 감사할 수가 없었다**. 그래서

  1. 이미 가드가 있던 교훈의 가드 테스트가 삭제돼도 아무도 모르고(부활 위험),
  2. 새 교훈이 추가돼도 '기계화할지/판단영역인지' 분류 없이 묻혀 버린다.

이 파일은 그 두 구멍을 기계적으로 막는다. 커버리지 지도는
``app/tests/lessons_coverage.json`` (매핑 워크플로우가 생성한 SSOT)에 있고,
각 교훈이 mechanized(가드 있음)/gap(기계화 가능한데 없음)/judgment(사람 판단)로
분류돼 있다.

  ┌────────────────────────────────────────────────────────────────────┐
  │ (A) mechanized 로 분류된 교훈이 참조하는 가드 테스트 파일은 실재해야    │
  │     한다 — 가드가 삭제되면 이 테스트가 정직하게 실패한다.               │
  │ (B) lessons.md 의 모든 교훈은 이 지도에 분류돼 있어야 한다 — 새 교훈이   │
  │     분류 없이 추가되면 실패한다(기계화 여부를 강제로 판단하게).          │
  └────────────────────────────────────────────────────────────────────┘

(B)는 외부 파일(lessons.md)에 의존하므로 그 파일이 없는 머신/CI 에서는 skip 한다
(가드는 repo-local 위생 불변식). (A)·(C)·(D)는 JSON 만으로 자족적이라 항상 실행된다.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
_DATA = _TESTS_DIR / "lessons_coverage.json"

_VALID_CATEGORIES = {"mechanized", "gap", "judgment"}
_TEST_FILE_RE = re.compile(r"test_[A-Za-z0-9_]+\.py")


def _load() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _lessons() -> list[dict]:
    return _load()["lessons"]


def _lessons_md_path() -> Path | None:
    """오답노트 원본 경로(환경변수 우선). 없으면 None → 해당 검사 skip."""
    env = os.environ.get("AUTOWRITE_LESSONS_FILE")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    default = Path.home() / ".omc" / "agent-learning" / "lessons.md"
    # 이 PC 실경로 폴백(홈 밖 .omc).
    for cand in (default, Path(r"D:\.omc\agent-learning\lessons.md")):
        if cand.is_file():
            return cand
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


# ---------------------------------------------------------------------------
# (C) 지도 자체의 건전성 — 자족적, 항상 실행.
# ---------------------------------------------------------------------------

def test_registry_wellformed() -> None:
    """모든 교훈 항목이 필수 필드와 유효한 category 를 가진다."""
    lessons = _lessons()
    assert lessons, "커버리지 지도가 비어 있음"
    seen_ids: set[str] = set()
    for l in lessons:
        for key in ("id", "category", "mechanizable", "impact"):
            assert l.get(key), f"항목에 {key} 누락: {l.get('id', l)}"
        assert l["category"] in _VALID_CATEGORIES, f"잘못된 category: {l['id']}={l['category']}"
        assert l["id"] not in seen_ids, f"중복 교훈 id(헤딩이 정확히 같음): {l['id']}"
        seen_ids.add(l["id"])


def test_counts_consistent() -> None:
    """저장된 counts 가 실제 lessons 분류 집계와 일치한다(무결성 잠금).

    누군가 교훈을 재분류하면 counts 도 함께 갱신하도록 강제 — 통계가 조용히
    틀어지는 것을 막는다.
    """
    data = _load()
    lessons = data["lessons"]
    counts = data["counts"]
    from collections import Counter
    actual = Counter(l["category"] for l in lessons)
    assert counts["mechanized"] == actual["mechanized"], "mechanized 집계 불일치"
    assert counts["gap"] == actual["gap"], "gap 집계 불일치"
    assert counts["judgment"] == actual["judgment"], "judgment 집계 불일치"
    assert counts["total"] == len(lessons), "total 집계 불일치"


# ---------------------------------------------------------------------------
# (A) mechanized 교훈의 가드 테스트 파일 실재 — 가드 삭제 시 실패(핵심 부활방지).
# ---------------------------------------------------------------------------

def test_mechanized_lessons_reference_existing_guards() -> None:
    """mechanized 로 분류된 교훈의 guard_ref 가 가리키는 test_*.py 는 실재해야 한다.

    가드 테스트가 삭제·개명되면(부활 위험) 여기서 정직하게 실패한다. guard_ref 에
    test_*.py 참조가 하나도 없는 mechanized 교훈은 '가드 근거 미기재'로 실패시켜
    지도가 헐거워지는 것도 막는다(단, 소스파일만으로 강제되는 소수는 guard_ref 에
    해당 test 를 함께 적어 두는 규약).
    """
    missing_files: list[str] = []
    no_test_ref: list[str] = []
    for l in _lessons():
        if l["category"] != "mechanized":
            continue
        refs = set(_TEST_FILE_RE.findall(l.get("guard_ref", "")))
        if not refs:
            no_test_ref.append(l["id"])
            continue
        for fname in refs:
            if not (_TESTS_DIR / fname).is_file():
                missing_files.append(f"{l['id']} → {fname}")
    assert not missing_files, (
        "mechanized 교훈이 참조하는 가드 테스트가 사라졌다(부활 위험):\n  "
        + "\n  ".join(missing_files)
    )
    assert not no_test_ref, (
        "mechanized 인데 guard_ref 에 test_*.py 근거가 없다(가드 출처 불명): "
        + ", ".join(no_test_ref)
    )


# ---------------------------------------------------------------------------
# (B) lessons.md 의 모든 교훈이 분류돼 있어야 한다 — 새 교훈 미분류 방지.
#     외부 파일 의존이라 파일이 있을 때만 실행.
# ---------------------------------------------------------------------------

def test_all_current_lessons_are_classified() -> None:
    """lessons.md 의 모든 ``## L...`` 교훈이 커버리지 지도에 분류돼 있어야 한다.

    새 교훈을 추가하면 이 지도(lessons_coverage.json)에도 mechanized/gap/judgment
    로 분류해 넣어야 통과한다 — 교훈이 '문서로만 남고 기계화 판단 없이' 묻히는 것을
    막는다. (lessons.md 가 없는 머신/CI 는 skip.)
    """
    lp = _lessons_md_path()
    if lp is None:
        pytest.skip("lessons.md 없음(다른 머신/CI) — repo-local 위생 불변식이라 skip")
    headings = re.findall(r"(?m)^##\s+(L\S.*?)\s*$", lp.read_text(encoding="utf-8"))
    assert headings, "lessons.md 에서 교훈 헤딩을 못 찾음(형식 변경?)"
    registry_norm = {_norm(l["id"]) for l in _lessons()}
    unclassified = [h for h in headings if _norm(h) not in registry_norm]
    assert not unclassified, (
        "lessons.md 에 새로 추가됐지만 커버리지 지도에 미분류된 교훈이 있다.\n"
        "app/tests/lessons_coverage.json 에 각 교훈을 "
        "mechanized/gap/judgment 로 분류해 추가하세요:\n  "
        + "\n  ".join(unclassified)
    )
