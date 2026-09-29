"""L-rule guard verification status. VERIFIED requires a passing run for the current HEAD."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import auto_write.operator_main as operator_main
from auto_write.operator_main import app
from auto_write.services.lrule_console_service import LRuleConsoleService
from auto_write.services.lrule_verification import (
    ENV_SKIPPED,
    FAILING,
    MISSING_GUARD,
    NOT_RUN,
    UNVERIFIED,
    VERIFIED,
    GuardIndex,
    build_wiring,
    file_stats,
    git_head,
    resolve_guard,
    status_from_outcomes,
    verify_lessons,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "app" / "tests" / "lessons_coverage.json"


def _rule(guard_ref: str, *, category: str = "mechanized", code: str = "L001") -> dict:
    return {
        "id": f"{code} | 테스트",
        "summary": "status",
        "mechanizable": "yes",
        "category": category,
        "guard_ref": guard_ref,
        "gap_desc": "",
        "impact": "low",
        "domain": "all",
    }


def _repo_with_test(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    path = repo / "app" / "tests" / "test_ok.py"
    path.parent.mkdir(parents=True)
    path.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    return repo, "app/tests/test_ok.py::test_ok"


def _cache(head: str, guard_ref: str, stats: dict, outcome: str, nodeid: str, message: str = "") -> dict:
    return {
        "L001": {
            "head": head,
            "guard_ref": guard_ref,
            "files": stats,
            "missing": [],
            "nodes": [{"nodeid": nodeid, "outcome": outcome, "message": message}],
            "error": "",
        }
    }


def test_status_from_outcomes_failed_is_failing():
    status = status_from_outcomes(
        missing=[],
        nodes=[{"nodeid": "app/tests/test_ok.py::test_ok", "outcome": "failed", "message": "assert"}],
    )
    assert status == FAILING
    assert status != VERIFIED


def test_status_from_outcomes_missing_node_is_missing_guard():
    status = status_from_outcomes(missing=["없는 테스트 노드: app/tests/test_nope.py::test_nope"], nodes=[])
    assert status == MISSING_GUARD
    assert status != VERIFIED


def test_status_from_outcomes_skip_is_not_verified():
    status = status_from_outcomes(
        missing=[],
        nodes=[{"nodeid": "app/tests/test_env.py::test_env", "outcome": "skipped", "message": "win32"}],
    )
    assert status == ENV_SKIPPED
    assert status != VERIFIED


def test_missing_guard_file_is_missing_guard(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "app" / "tests").mkdir(parents=True)
    wiring = build_wiring(
        _rule("app/tests/test_nope.py::test_nope", code="L009"),
        code="L009",
        repo=repo,
        cache_rules={},
        head="abc123",
        index=GuardIndex(repo),
        include_tests=True,
    )
    assert wiring["status"] == MISSING_GUARD
    assert wiring["status"] != VERIFIED
    assert wiring["missing"]


def test_failed_cached_run_is_failing(tmp_path: Path):
    repo, nodeid = _repo_with_test(tmp_path)
    guard = "app/tests/test_ok.py::test_ok"
    stats = file_stats(repo, ["app/tests/test_ok.py"])
    wiring = build_wiring(
        _rule(guard),
        code="L001",
        repo=repo,
        cache_rules=_cache("abc123", guard, stats, "failed", nodeid, "assert False"),
        head="abc123",
        index=GuardIndex(repo),
    )
    assert wiring["status"] == FAILING
    assert wiring["status"] != VERIFIED


def test_stale_sha_is_not_verified(tmp_path: Path):
    repo, nodeid = _repo_with_test(tmp_path)
    guard = "app/tests/test_ok.py::test_ok"
    stats = file_stats(repo, ["app/tests/test_ok.py"])
    wiring = build_wiring(
        _rule(guard),
        code="L001",
        repo=repo,
        cache_rules=_cache("oldsha", guard, stats, "passed", nodeid),
        head="newsha",
        index=GuardIndex(repo),
    )
    assert wiring["status"] == UNVERIFIED
    assert wiring["stale"] is True
    assert wiring["status"] != VERIFIED


def test_stale_mtime_is_not_verified(tmp_path: Path):
    repo, nodeid = _repo_with_test(tmp_path)
    guard = "app/tests/test_ok.py::test_ok"
    stats = file_stats(repo, ["app/tests/test_ok.py"])
    stats["app/tests/test_ok.py"] = {"mtime_ns": 1, "size": 1}
    wiring = build_wiring(
        _rule(guard),
        code="L001",
        repo=repo,
        cache_rules=_cache("abc123", guard, stats, "passed", nodeid),
        head="abc123",
        index=GuardIndex(repo),
    )
    assert wiring["status"] == UNVERIFIED
    assert wiring["status"] != VERIFIED


def test_fresh_all_pass_is_verified(tmp_path: Path):
    repo, nodeid = _repo_with_test(tmp_path)
    guard = "app/tests/test_ok.py::test_ok"
    stats = file_stats(repo, ["app/tests/test_ok.py"])
    wiring = build_wiring(
        _rule(guard),
        code="L001",
        repo=repo,
        cache_rules=_cache("abc123", guard, stats, "passed", nodeid),
        head="abc123",
        index=GuardIndex(repo),
    )
    assert wiring["status"] == VERIFIED


def test_empty_head_never_verified(tmp_path: Path):
    repo, nodeid = _repo_with_test(tmp_path)
    guard = "app/tests/test_ok.py::test_ok"
    stats = file_stats(repo, ["app/tests/test_ok.py"])
    wiring = build_wiring(
        _rule(guard),
        code="L001",
        repo=repo,
        cache_rules=_cache("abc123", guard, stats, "passed", nodeid),
        head="",
        index=GuardIndex(repo),
    )
    assert wiring["status"] == UNVERIFIED
    assert wiring["status"] != VERIFIED


def test_not_run_without_cache(tmp_path: Path):
    repo, _nodeid = _repo_with_test(tmp_path)
    wiring = build_wiring(
        _rule("app/tests/test_ok.py::test_ok"),
        code="L001",
        repo=repo,
        cache_rules={},
        head="abc123",
        index=GuardIndex(repo),
    )
    assert wiring["status"] == NOT_RUN
    assert wiring["status"] != VERIFIED


def test_selector_does_not_swallow_next_filename():
    index = GuardIndex(REPO_ROOT)
    resolved = resolve_guard(
        "app/tests/test_auto_write_apply.py::test_autopilot_cli_forwards_blind_review"
        "·test_submission_pipeline.py::test_pipeline_forwards_blind_review_to_acceptance",
        REPO_ROOT,
        index,
    )
    assert resolved.missing == []
    assert ("app/tests/test_auto_write_apply.py", "test_autopilot_cli_forwards_blind_review") in resolved.specific
    assert (
        "app/tests/test_submission_pipeline.py",
        "test_pipeline_forwards_blind_review_to_acceptance",
    ) in resolved.specific


def test_mechanized_registry_guards_resolve_to_real_tests():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    index = GuardIndex(REPO_ROOT)
    broken = []
    for lesson in data["lessons"]:
        if lesson.get("category") != "mechanized":
            continue
        resolved = resolve_guard(str(lesson.get("guard_ref", "")), REPO_ROOT, index)
        if resolved.missing or not resolved.has_targets:
            code = str(lesson.get("id", "")).split("|")[0].strip()
            broken.append(f"{code}: {resolved.missing}")
    assert broken == []


def test_verify_lessons_maps_injected_results_without_pytest(tmp_path: Path):
    repo, nodeid = _repo_with_test(tmp_path)
    lessons = [
        _rule("app/tests/test_ok.py::test_ok", code="L001"),
        _rule("app/tests/test_ok.py::test_missing_name", code="L002"),
    ]
    (repo / "app" / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n\ndef test_missing_name():\n    assert True\n",
        encoding="utf-8",
    )

    def collect(_repo, files):
        return {files[0]: [nodeid, "app/tests/test_ok.py::test_missing_name"]}, ""

    def execute(_repo, targets):
        return {
            nodeid: {"nodeid": nodeid, "outcome": "failed", "message": "assert False"},
            "app/tests/test_ok.py::test_missing_name": {
                "nodeid": "app/tests/test_ok.py::test_missing_name",
                "outcome": "passed",
                "message": "",
            },
        }, "", 0

    records = verify_lessons(
        lessons,
        repo=repo,
        index=GuardIndex(repo),
        head="abc123",
        codes=None,
        rule_code_fn=lambda rule: str(rule["id"]).split("|")[0].strip(),
        collect=collect,
        execute=execute,
    )
    failed = build_wiring(
        lessons[0],
        code="L001",
        repo=repo,
        cache_rules=records,
        head="abc123",
        index=GuardIndex(repo),
    )
    assert failed["status"] == FAILING
    passed = build_wiring(
        lessons[1],
        code="L002",
        repo=repo,
        cache_rules=records,
        head="abc123",
        index=GuardIndex(repo),
    )
    assert passed["status"] == VERIFIED


def _git(cwd: Path, *args: str) -> None:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError((proc.stderr or proc.stdout).strip())


@pytest.mark.skipif(subprocess.run(["git", "--version"], capture_output=True).returncode != 0, reason="git required")
def test_verify_rules_runs_pytest_and_stale_head_drops_verified(tmp_path: Path):
    repo = tmp_path / "repo"
    tests = repo / "app" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_pass_guard.py").write_text("def test_pass():\n    assert True\n", encoding="utf-8")
    (tests / "test_fail_guard.py").write_text("def test_fail():\n    assert False, 'boom'\n", encoding="utf-8")
    (tests / "test_env_guard.py").write_text(
        "import pytest\n\ndef test_env():\n    pytest.skip('Windows hangul data/sample.hwpx is not in this workspace')\n",
        encoding="utf-8",
    )
    lessons = {
        "counts": {"mechanized": 4, "gap": 0, "judgment": 1, "total": 5},
        "lessons": [
            _rule("app/tests/test_pass_guard.py::test_pass", code="L001"),
            _rule("app/tests/test_fail_guard.py::test_fail", code="L002"),
            _rule("app/tests/test_missing_guard.py::test_nope", code="L003"),
            _rule("app/tests/test_env_guard.py::test_env", code="L004"),
            _rule("", category="judgment", code="L005"),
        ],
    }
    (tests / "lessons_coverage.json").write_text(json.dumps(lessons, ensure_ascii=False), encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "LRule Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed")
    service = LRuleConsoleService(repo, cache_path=tmp_path / "cache.json")
    before = service.light_wiring(lessons["lessons"][0])
    assert before["status"] == NOT_RUN
    summary = service.verify_rules()
    statuses = {row["_code"]: row["_wiring"]["status"] for row in service.list_rules()}
    assert statuses["L001"] == VERIFIED
    assert statuses["L002"] == FAILING
    assert statuses["L003"] == MISSING_GUARD
    assert statuses["L004"] == ENV_SKIPPED
    assert statuses["L005"] == "HUMAN_RULE"
    assert summary["verified"] == 1
    assert summary["failing"] == 1
    assert summary["missing_guard"] == 1
    assert summary["env_skipped"] == 1
    previous = git_head(repo)
    (repo / "marker.txt").write_text("next\n", encoding="utf-8")
    _git(repo, "add", "marker.txt")
    _git(repo, "commit", "-m", "new head")
    assert git_head(repo) != previous
    stale = service.light_wiring(lessons["lessons"][0])
    assert stale["status"] == UNVERIFIED
    assert stale["status"] != VERIFIED


def test_lrules_page_does_not_show_verified_without_a_run(tmp_path, monkeypatch):
    service = LRuleConsoleService(REPO_ROOT, cache_path=tmp_path / "empty-cache.json")
    monkeypatch.setattr(operator_main, "lrule_console", service)
    response = TestClient(app).get("/console/lrules")
    assert response.status_code == 200
    assert "가드 테스트 전체 검증" in response.text
    assert "badge-not_run" in response.text
    assert "badge-verified" not in response.text
    assert "badge-declared" not in response.text
    assert ">DECLARED<" not in response.text


def test_verify_route_does_not_run_pytest_inline(monkeypatch):
    calls = []

    def fake_start(codes=None):
        calls.append(codes)
        return "가드 테스트 검증을 시작했습니다."

    monkeypatch.setattr(operator_main.lrule_console, "start_verify", fake_start)
    response = TestClient(app).post("/console/lrules/verify", follow_redirects=False)
    assert response.status_code == 303
    assert calls == [None]
    assert "message=" in response.headers["location"]
