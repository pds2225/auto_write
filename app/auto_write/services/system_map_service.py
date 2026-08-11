from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SystemNode:
    key: str
    label: str
    easy_description: str
    path: str
    symbol: str
    status: str
    related_rules: list[str]
    compatibility_path: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class SystemMapService:
    """Build a non-developer system map from real repository files/symbols.

    Canonical implementation paths are preferred. Legacy ``auto_write.services``
    wrappers are exposed only as compatibility paths so the operator UI reflects
    the repository's current architecture rather than historical import shims.
    """

    NODE_SPECS = (
        (
            "web",
            "웹 운영 콘솔",
            "사용자가 문서와 규칙을 다루는 화면입니다.",
            "app/auto_write/operator_main.py",
            "FastAPI",
            "",
        ),
        (
            "router",
            "DomainRouter",
            "요청이 어떤 문서 업무인지 분류합니다.",
            "app/auto_write/domains/domain_router.py",
            "class DomainRouter",
            "",
        ),
        (
            "bizplan",
            "사업계획서 엔진",
            "사업계획서 작성·보강 오케스트레이션을 실행합니다.",
            "app/core/docx/services/bizplan_autopilot.py",
            "def run_bizplan_autopilot",
            "app/auto_write/services/bizplan_autopilot.py",
        ),
        (
            "cross_form",
            "기존자료 활용",
            "기존 자료의 사실을 새 양식에 보수적으로 전사하는 엔진입니다.",
            "app/core/docx/services/cross_form_autofill.py",
            "SYNONYMS",
            "app/auto_write/services/cross_form_autofill.py",
        ),
        (
            "lrule",
            "L 규칙 엔진",
            "canonical L 규칙 registry를 읽고 적용 상태를 관리합니다.",
            "app/auto_write/services/lrule_enforcer.py",
            "class LRuleEnforcer",
            "",
        ),
        (
            "project",
            "문서 작성 서비스",
            "업로드 자료와 양식을 실제 문서 생성 과정에 연결합니다.",
            "app/auto_write/services/project_service.py",
            "class ProjectService",
            "",
        ),
        (
            "render",
            "DOCX 렌더러",
            "작성 내용을 실제 DOCX 본문과 표에 반영합니다.",
            "app/core/docx/services/render_service.py",
            "class RenderService",
            "app/auto_write/services/render_service.py",
        ),
        (
            "converter",
            "HWP/DOCX 변환",
            "HWP·HWPX·DOCX 간 실제 지원 가능한 변환을 수행합니다.",
            "app/core/docx/services/hwp_docx_convert.py",
            "def convert",
            "app/auto_write/services/hwp_docx_convert.py",
        ),
        (
            "finalizer",
            "Finalizer",
            "L 규칙 결과와 산출물 해시를 기준으로 최종 파일 처리를 통제합니다.",
            "app/auto_write/services/finalizer.py",
            "class Finalizer",
            "",
        ),
    )

    def __init__(self, repo_root: str | Path, lrule_service: Any):
        self.repo_root = Path(repo_root)
        self.lrule_service = lrule_service

    def _related_rules(self, file_path: str, compatibility_path: str = "") -> list[str]:
        names = {Path(file_path).name.lower()}
        if compatibility_path:
            names.add(Path(compatibility_path).name.lower())
        rows = []
        try:
            lessons = self.lrule_service.load().get("lessons", [])
        except Exception:
            lessons = []
        for rule in lessons:
            guard = str(rule.get("guard_ref", "")).lower()
            if any(name in guard for name in names):
                code = self.lrule_service.rule_code(rule)
                if code not in rows:
                    rows.append(code)
        return rows[:30]

    def nodes(self) -> list[dict]:
        rows = []
        for key, label, description, rel_path, symbol, compatibility_path in self.NODE_SPECS:
            path = self.repo_root / rel_path
            exists = path.is_file()
            symbol_ok = False
            if exists:
                try:
                    symbol_ok = symbol.lower() in path.read_text(encoding="utf-8", errors="ignore").lower()
                except Exception:
                    symbol_ok = False
            status = "NORMAL" if exists and symbol_ok else ("WARNING" if exists else "DISCONNECTED")
            node = SystemNode(
                key=key,
                label=label,
                easy_description=description,
                path=rel_path,
                symbol=symbol,
                status=status,
                related_rules=self._related_rules(rel_path, compatibility_path),
                compatibility_path=compatibility_path,
            )
            rows.append(node.as_dict())
        return rows

    def workflows(self) -> list[dict]:
        return [
            {
                "key": "write",
                "label": "문서 작성",
                "description": "공고·양식·기존자료를 한 화면에서 받아 기존 작성 엔진으로 연결합니다.",
                "steps": [
                    {"key": "upload", "label": "자료 입력", "service": "Web", "node": "web"},
                    {"key": "analyze", "label": "양식/자료 분석", "service": "ProjectService", "node": "project"},
                    {"key": "route", "label": "업무 분류", "service": "DomainRouter", "node": "router"},
                    {"key": "rules", "label": "L 규칙 참조", "service": "LRuleEnforcer", "node": "lrule"},
                    {"key": "generate", "label": "문서 작성", "service": "ProjectService", "node": "project"},
                    {"key": "render", "label": "DOCX 반영", "service": "core.docx RenderService", "node": "render"},
                ],
            },
            {
                "key": "revise",
                "label": "문서 수정·보완",
                "description": "기존 문서를 새 작성 입력으로 사용하고 사용자 지시를 함께 전달해 수정본을 생성합니다.",
                "steps": [
                    {"key": "upload", "label": "기존 문서 입력", "service": "Web", "node": "web"},
                    {"key": "route", "label": "수정 요청 분석", "service": "DomainRouter", "node": "router"},
                    {"key": "rules", "label": "관련 L 규칙 참조", "service": "LRuleEnforcer", "node": "lrule"},
                    {"key": "generate", "label": "수정본 생성", "service": "ProjectService", "node": "project"},
                    {"key": "render", "label": "새 결과 저장", "service": "core.docx RenderService", "node": "render"},
                ],
            },
            {
                "key": "convert",
                "label": "문서 변환",
                "description": "입력 확장자와 목표 형식에 따라 canonical 변환 서비스를 호출합니다.",
                "steps": [
                    {"key": "upload", "label": "문서 입력", "service": "Web", "node": "web"},
                    {"key": "detect", "label": "형식 확인", "service": "Web", "node": "web"},
                    {"key": "convert", "label": "변환", "service": "core.docx hwp_docx_convert", "node": "converter"},
                    {"key": "output", "label": "결과 파일", "service": "FileResponse", "node": "web"},
                ],
            },
        ]

    def overview(self) -> dict:
        nodes = self.nodes()
        return {
            "nodes": nodes,
            "normal": sum(1 for n in nodes if n["status"] == "NORMAL"),
            "warning": sum(1 for n in nodes if n["status"] == "WARNING"),
            "disconnected": sum(1 for n in nodes if n["status"] == "DISCONNECTED"),
            "python_files": sum(1 for _ in (self.repo_root / "app").rglob("*.py")) if (self.repo_root / "app").exists() else 0,
        }
