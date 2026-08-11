from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from auto_write.operator_main import app
from auto_write.services.docx_edit_service import DocxEditService
from auto_write.services.git_sync_service import GitSyncError, GitSyncService
from auto_write.services.lrule_console_service import LRuleConsoleService
from auto_write.services.system_map_service import SystemMapService
from auto_write.services.workflow_monitor import WorkflowMonitor


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_operator_console_smoke():
    client = TestClient(app)
    response = client.get("/console")
    assert response.status_code == 200
    assert "문서 작업" in response.text
    assert "L 규칙" in response.text
    assert "GitHub" in response.text


def test_operator_lrules_exposes_entire_canonical_registry():
    service = LRuleConsoleService(REPO_ROOT)
    data = service.load()
    rules = service.list_rules()
    assert len(rules) == len(data["lessons"])
    assert len(rules) == data["counts"]["total"]
    assert rules[0]["_code"].startswith("L")


def test_architecture_map_checks_real_files():
    lrules = LRuleConsoleService(REPO_ROOT)
    service = SystemMapService(REPO_ROOT, lrules)
    overview = service.overview()
    keys = {node["key"] for node in overview["nodes"]}
    assert {"web", "router", "lrule", "project", "converter"}.issubset(keys)
    router = next(node for node in overview["nodes"] if node["key"] == "router")
    assert router["path"] == "app/auto_write/domains/domain_router.py"
    assert router["status"] == "NORMAL"


def test_docx_browser_edit_never_overwrites_source_and_locks(tmp_path):
    source = tmp_path / "source.docx"
    doc = Document()
    doc.add_paragraph("원문")
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "표 원문"
    doc.save(source)

    output = tmp_path / "edited.docx"
    locks = tmp_path / "user_locks.json"
    service = DocxEditService()
    report = service.apply_edits(
        source,
        {"p:0": "사용자 수정", "t:0:r:0:c:0": "표 수정"},
        output,
        locks,
    )

    assert report["applied_count"] == 2
    assert source.read_bytes() != output.read_bytes()
    assert Document(source).paragraphs[0].text == "원문"
    assert Document(output).paragraphs[0].text == "사용자 수정"
    assert json.loads(locks.read_text(encoding="utf-8"))["locks"]["p:0"] == "사용자 수정"

    second = service.apply_edits(
        Path(report["output"]),
        {"p:0": "사용자 2차 수정"},
        output,
        locks,
    )
    assert Path(second["output"]).name == "output_user_edited_v2.docx"
    assert Document(output).paragraphs[0].text == "사용자 수정"
    assert Document(second["output"]).paragraphs[0].text == "사용자 2차 수정"


def test_workflow_monitor_records_actual_wrapped_step(tmp_path):
    monitor = WorkflowMonitor(tmp_path / "runs.json")
    run_id = monitor.start_run("write", "문서 작성")
    with monitor.step(run_id, "route", "업무 분류", "DomainRouter"):
        value = 1 + 1
        assert value == 2
    monitor.finish_run(run_id, {"result": "ok"})

    run = monitor.get_run(run_id)
    assert run is not None
    assert run["status"] == "SUCCESS"
    assert run["steps"][0]["status"] == "SUCCESS"
    assert run["steps"][0]["service"] == "DomainRouter"


def test_git_sync_source_has_no_force_push_default():
    source = (REPO_ROOT / "app/auto_write/services/git_sync_service.py").read_text(encoding="utf-8")
    assert '"push", "-u"' in source
    assert '"--force"' not in source
    assert '"--force-with-lease"' not in source


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError((proc.stderr or proc.stdout).strip())
    return (proc.stdout or "").strip()


def _setup_git_remote(tmp_path: Path) -> tuple[Path, Path, Path]:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    web = tmp_path / "web"
    peer = tmp_path / "peer"

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True, capture_output=True)
    _git(seed, "config", "user.email", "test@example.com")
    _git(seed, "config", "user.name", "Auto Write Test")
    (seed / "rules.json").write_text('{"v":1}\n', encoding="utf-8")
    _git(seed, "add", "rules.json")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "branch", "-M", "master")
    _git(seed, "push", "-u", "origin", "master")

    subprocess.run(["git", "clone", "-b", "master", str(remote), str(web)], check=True, capture_output=True)
    subprocess.run(["git", "clone", "-b", "master", str(remote), str(peer)], check=True, capture_output=True)
    for repo in (web, peer):
        _git(repo, "config", "user.email", "test@example.com")
        _git(repo, "config", "user.name", "Auto Write Test")
    return remote, web, peer


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable required")
def test_git_sync_bidirectional_and_stale_remote_guard(tmp_path):
    _, web, peer = _setup_git_remote(tmp_path)
    service = GitSyncService(web)
    service.write_mode = "direct"

    assert service.snapshot(fetch=True).status == "SYNCED"

    (peer / "rules.json").write_text('{"v":2,"from":"remote"}\n', encoding="utf-8")
    _git(peer, "add", "rules.json")
    _git(peer, "commit", "-m", "remote update")
    _git(peer, "push", "origin", "master")
    synced = service.sync_from_remote()
    assert synced.status == "SYNCED"
    assert '"from":"remote"' in (web / "rules.json").read_text(encoding="utf-8")

    expected = service.base_remote_sha()
    service.assert_write_base(expected)
    (web / "rules.json").write_text('{"v":3,"from":"web"}\n', encoding="utf-8")
    result = service.commit_and_push(
        ["rules.json"],
        message="web update",
        expected_base_remote_sha=expected,
    )
    assert result["branch"] == "master"
    _git(peer, "pull", "--ff-only")
    assert '"from":"web"' in (peer / "rules.json").read_text(encoding="utf-8")

    stale_base = service.base_remote_sha()
    (peer / "rules.json").write_text('{"v":4,"from":"remote-race"}\n', encoding="utf-8")
    _git(peer, "add", "rules.json")
    _git(peer, "commit", "-m", "remote race")
    _git(peer, "push", "origin", "master")
    with pytest.raises(GitSyncError):
        service.assert_write_base(stale_base)


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable required")
def test_git_branch_pr_mode_reuses_branch_until_merge_then_returns_to_master(tmp_path, monkeypatch):
    _, web, _ = _setup_git_remote(tmp_path)
    service = GitSyncService(web)
    service.write_mode = "branch-pr"
    original_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "gh" else original_which(name))

    expected = service.base_remote_sha()
    service.assert_write_base(expected)
    (web / "rules.json").write_text('{"v":2,"from":"web-branch"}\n', encoding="utf-8")
    first = service.commit_and_push(
        ["rules.json"],
        message="branch update 1",
        expected_base_remote_sha=expected,
    )

    assert first["branch"].startswith("web/lrule-")
    assert _git(web, "rev-parse", "--abbrev-ref", "HEAD") == first["branch"]
    assert service.remote_sha(first["branch"]) == service.local_sha()
    assert '"from":"web-branch"' in (web / "rules.json").read_text(encoding="utf-8")

    expected2 = service.base_remote_sha()
    service.assert_write_base(expected2)
    (web / "rules.json").write_text('{"v":3,"from":"web-branch-2"}\n', encoding="utf-8")
    second = service.commit_and_push(
        ["rules.json"],
        message="branch update 2",
        expected_base_remote_sha=expected2,
    )
    assert second["branch"] == first["branch"]
    assert service.remote_sha(first["branch"]) == service.local_sha()

    _git(web, "push", "origin", f"{first['branch']}:master")
    synced = service.sync_from_remote()
    assert _git(web, "rev-parse", "--abbrev-ref", "HEAD") == "master"
    assert synced.status == "SYNCED"
    assert '"from":"web-branch-2"' in (web / "rules.json").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable required")
def test_git_failed_feature_push_rolls_back_worktree(tmp_path, monkeypatch):
    remote, web, _ = _setup_git_remote(tmp_path)
    service = GitSyncService(web)
    service.write_mode = "branch-pr"
    original_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "gh" else original_which(name))

    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    expected = service.base_remote_sha()
    service.assert_write_base(expected)
    (web / "rules.json").write_text('{"v":9,"should":"rollback"}\n', encoding="utf-8")

    with pytest.raises(GitSyncError):
        service.commit_and_push(
            ["rules.json"],
            message="rejected update",
            expected_base_remote_sha=expected,
        )

    assert _git(web, "rev-parse", "--abbrev-ref", "HEAD") == "master"
    assert _git(web, "status", "--porcelain") == ""
    assert (web / "rules.json").read_text(encoding="utf-8").strip() == '{"v":1}'
