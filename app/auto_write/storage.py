from __future__ import annotations

import re
import shutil
from pathlib import Path

from .config import Settings
from .models import ProjectInput, TemplateProfile
from .utils import read_json, sanitize_user_filename, short_id, write_json


_INTERNAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


def _safe_root_child(root: Path, value: str, label: str) -> Path:
    raw_value = str(value or "").strip()
    if not _INTERNAL_ID_RE.fullmatch(raw_value):
        raise ValueError(f"{label} 형식이 올바르지 않습니다.")
    base = root.resolve()
    target = (base / raw_value).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"{label}가 저장소 경계를 벗어났습니다.") from exc
    return target


class Storage:
    def __init__(self, settings: Settings):
        self.settings = settings

    def template_dir(self, template_id: str) -> Path:
        return _safe_root_child(self.settings.template_root, template_id, "템플릿 ID")

    def project_dir(self, project_id: str) -> Path:
        return _safe_root_child(self.settings.project_root, project_id, "프로젝트 ID")

    def results_dir(self, project_id: str) -> Path:
        return _safe_root_child(self.settings.results_root, project_id, "프로젝트 ID")

    def create_template_space(self, file_name: str) -> tuple[str, Path]:
        safe_name = sanitize_user_filename(file_name)
        template_id = short_id("tpl")
        folder = self.template_dir(template_id)
        folder.mkdir(parents=True, exist_ok=True)
        return template_id, folder / safe_name

    def save_template_profile(self, profile: TemplateProfile) -> Path:
        path = self.template_dir(profile.template_id) / "template_profile.json"
        write_json(path, profile.model_dump())
        return path

    def load_template_profile(self, template_id: str) -> TemplateProfile:
        data = read_json(self.template_dir(template_id) / "template_profile.json")
        return TemplateProfile.model_validate(data)

    def list_template_profiles(self) -> list[TemplateProfile]:
        profiles: list[TemplateProfile] = []
        for path in sorted(self.settings.template_root.glob("*/template_profile.json")):
            profiles.append(TemplateProfile.model_validate(read_json(path)))
        return profiles

    def create_project_space(self, template_id: str, project_name: str) -> tuple[str, Path]:
        self.template_dir(template_id)
        project_id = short_id("prj")
        folder = self.project_dir(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "references").mkdir(exist_ok=True)
        (folder / "generated_assets").mkdir(exist_ok=True)
        (folder / "output").mkdir(exist_ok=True)
        write_json(
            folder / "project_meta.json",
            {"project_id": project_id, "template_id": template_id, "project_name": project_name},
        )
        return project_id, folder

    def save_project_input(self, project_id: str, project_input: ProjectInput) -> Path:
        path = self.project_dir(project_id) / "project_input.json"
        write_json(path, project_input.model_dump())
        return path

    def load_project_input(self, project_id: str) -> ProjectInput:
        data = read_json(self.project_dir(project_id) / "project_input.json")
        return ProjectInput.model_validate(data)

    def list_projects(self) -> list[dict]:
        items: list[dict] = []
        for path in sorted(self.settings.project_root.glob("*/project_meta.json")):
            items.append(read_json(path))
        return items

    def copy_reference_file(self, project_id: str, source_path: Path, target_name: str) -> Path:
        safe_name = sanitize_user_filename(target_name)
        target = self.project_dir(project_id) / "references" / safe_name
        shutil.copy2(source_path, target)
        return target
