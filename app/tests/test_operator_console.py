from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from auto_write.operator_main import app
from auto_write.services.docx_edit_service import DocxEditService
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
