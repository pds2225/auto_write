"""Domain-aware workspace/results routing regression tests."""
from __future__ import annotations

import json
from pathlib import Path

from auto_write.config import Settings, ensure_directories
from auto_write.models import ProjectInput, TemplateProfile
from auto_write.services.project_service import ProjectService
from auto_write.storage import Storage


def _settings(root: Path) -> Settings:
    workspace = root / "workspace"
    app_root = root / "app"
    return Settings(
        app_root=app_root,
        workspace_root=workspace,
        template_root=workspace / "templates",
        project_root=workspace / "projects",
        results_root=root / "results",
        static_root=app_root / "static",
        template_view_root=app_root / "templates",
        host="127.0.0.1",
        port=8765,
        openai_api_key="",
        openai_model="",
        openai_search_model="",
        openai_image_model="",
        anthropic_api_key="",
        anthropic_model="",
        anthropic_search_model="",
    )


def test_new_business_plan_project_uses_domain_roots(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ensure_directories(settings)
    storage = Storage(settings)

    project_id, project_path = storage.create_project_space(
        "template-1", "BP", domain="business_plan"
    )

    assert project_path == settings.workspace_root / "business_plan" / "projects" / project_id
    assert storage.project_dir(project_id) == project_path
    assert storage.results_dir(project_id) == settings.results_root / "business_plan" / project_id
    assert json.loads((project_path / "project_meta.json").read_text(encoding="utf-8"))["domain"] == "business_plan"


def test_new_consultant_project_uses_domain_roots(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ensure_directories(settings)
    storage = Storage(settings)

    project_id, project_path = storage.create_project_space(
        "resume-1", "CA", domain="consultant_application"
    )

    assert project_path == settings.workspace_root / "consultant_application" / "projects" / project_id
    assert storage.project_dir(project_id) == project_path
    assert storage.results_dir(project_id) == settings.results_root / "consultant_application" / project_id


def test_legacy_project_is_still_readable(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ensure_directories(settings)
    storage = Storage(settings)
    legacy = settings.project_root / "legacy-1"
    legacy.mkdir(parents=True)
    (legacy / "project_meta.json").write_text(
        json.dumps({"project_id": "legacy-1"}),
        encoding="utf-8",
    )

    assert storage.project_dir("legacy-1") == legacy
    # A legacy project without a migrated result directory keeps its old result root.
    assert storage.results_dir("legacy-1") == settings.results_root / "legacy-1"


def test_web_finalization_publishes_only_a_lrule_checked_draft(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ensure_directories(settings)
    storage = Storage(settings)
    template_dir = settings.template_root / "tpl-1"
    template_dir.mkdir(parents=True)
    profile = TemplateProfile(
        template_id="tpl-1",
        template_name="사업계획서.docx",
        source_docx=str(template_dir / "source.docx"),
    )
    storage.save_template_profile(profile)
    project_id, project_path = storage.create_project_space(
        "tpl-1", "BP", domain="business_plan"
    )
    storage.save_project_input(
        project_id,
        ProjectInput(template_id="tpl-1", project_meta={"domain": "business_plan"}),
    )
    artifact = project_path / "output" / "output.docx"
    artifact.write_bytes(b"synthetic generated artifact")

    service = ProjectService.__new__(ProjectService)
    service.storage = storage
    result = service.finalize_project(project_id)

    assert result["domain"]["domain"] == "business_plan"
    assert Path(result["lrule_report"]).exists()
    assert result["finalizer"]["submittable"] is False
    draft = Path(result["final_docx"])
    assert draft.name == f"제출초안_{project_id}_DRAFT.docx"
    assert draft.exists()
    assert (project_path / "output" / "output.docx").exists()
