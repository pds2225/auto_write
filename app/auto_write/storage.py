from __future__ import annotations

import re
import shutil
from pathlib import Path

from .config import Settings, get_domain_results, get_domain_workspace
from .models import ProjectInput, TemplateProfile
from .utils import read_json, sanitize_user_filename, short_id, write_json


_INTERNAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
_DOMAINS = {"business_plan", "consultant_application", "other"}


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

    def _domain_project_root(self, domain: str) -> Path:
        if domain not in _DOMAINS:
            raise ValueError(f"알 수 없는 domain: {domain}")
        root = get_domain_workspace(domain, self.settings) / "projects"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _domain_results_root(self, domain: str) -> Path:
        if domain not in _DOMAINS:
            raise ValueError(f"알 수 없는 domain: {domain}")
        root = get_domain_results(domain, self.settings)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def project_dir(self, project_id: str, domain: str | None = None) -> Path:
        """프로젝트 경로를 반환한다.

        ``domain``이 지정된 신규 프로젝트는 도메인별 workspace를 사용한다.
        미지정 조회는 레거시 경로를 먼저 보고, 없을 때 도메인 경로를 찾아
        기존 caller가 마이그레이션 없이 계속 읽도록 한다.
        """
        if domain:
            return _safe_root_child(self._domain_project_root(domain), project_id, "프로젝트 ID")
        legacy = _safe_root_child(self.settings.project_root, project_id, "프로젝트 ID")
        if legacy.exists():
            return legacy
        for candidate_domain in ("business_plan", "consultant_application", "other"):
            candidate = _safe_root_child(self._domain_project_root(candidate_domain), project_id, "프로젝트 ID")
            if candidate.exists():
                return candidate
        return legacy

    def results_dir(self, project_id: str, domain: str | None = None) -> Path:
        """프로젝트 결과 경로를 반환한다(도메인 신규 경로 + 레거시 fallback)."""
        if domain:
            return _safe_root_child(self._domain_results_root(domain), project_id, "프로젝트 ID")

        project = self.project_dir(project_id)
        meta_path = project / "project_meta.json"
        if meta_path.exists():
            try:
                meta = read_json(meta_path)
                meta_domain = str(meta.get("domain", "")).strip()
                if meta_domain in _DOMAINS:
                    return _safe_root_child(self._domain_results_root(meta_domain), project_id, "프로젝트 ID")
            except Exception:
                pass
        legacy = _safe_root_child(self.settings.results_root, project_id, "프로젝트 ID")
        return legacy

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

    def create_project_space(
        self, template_id: str, project_name: str, domain: str | None = None
    ) -> tuple[str, Path]:
        self.template_dir(template_id)
        project_id = short_id("prj")
        folder = self.project_dir(project_id, domain=domain)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "references").mkdir(exist_ok=True)
        (folder / "generated_assets").mkdir(exist_ok=True)
        (folder / "output").mkdir(exist_ok=True)
        meta = {"project_id": project_id, "template_id": template_id, "project_name": project_name}
        if domain:
            meta["domain"] = domain
        write_json(folder / "project_meta.json", meta)
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
        roots = [self.settings.project_root]
        roots.extend(
            self._domain_project_root(domain)
            for domain in ("business_plan", "consultant_application", "other")
        )
        seen: set[str] = set()
        for root in roots:
            for path in sorted(root.glob("*/project_meta.json")):
                data = read_json(path)
                project_id = str(data.get("project_id", path.parent.name))
                if project_id in seen:
                    continue
                seen.add(project_id)
                items.append(data)
        return items

    def copy_reference_file(self, project_id: str, source_path: Path, target_name: str) -> Path:
        safe_name = sanitize_user_filename(target_name)
        target = self.project_dir(project_id) / "references" / safe_name
        shutil.copy2(source_path, target)
        return target
