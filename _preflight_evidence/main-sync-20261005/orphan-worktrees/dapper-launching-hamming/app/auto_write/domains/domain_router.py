# domain_router.py — Runtime domain routing
"""도메인 라우터.

실제 runtime에서 입력을 분석하여 올바른 도메인 파이프라인으로 라우팅한다.
모든 주요 entrypoint가 이 라우터를 통해 도메인을 해석한다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from auto_write.domains.domain_classifier import Domain, DomainResult, classify_domain

__all__ = [
    "Domain",
    "DomainResult",
    "DomainRouter",
    "DomainContext",
    "resolve_domain",
]


@dataclass
class DomainContext:
    """도메인 실행 컨텍스트."""
    domain: Domain
    domain_result: DomainResult
    document_type: str = ""
    project_id: str = ""
    workspace_dir: Optional[Path] = None
    results_dir: Optional[Path] = None

    def as_dict(self) -> dict:
        return {
            "domain": self.domain.value,
            "confidence": round(self.domain_result.confidence, 3),
            "reason": self.domain_result.reason,
            "ambiguous": self.domain_result.is_ambiguous(),
            "document_type": self.document_type,
            "project_id": self.project_id,
            "workspace_dir": str(self.workspace_dir) if self.workspace_dir else None,
            "results_dir": str(self.results_dir) if self.results_dir else None,
        }


class DomainRouter:
    """도메인 라우터 — 입력에서 도메인을 판정하고 컨텍스트를 생성한다."""

    def __init__(self, settings: Any = None):
        self._settings = settings

    def resolve(
        self,
        text: str = "",
        filename: str = "",
        document_type: str = "",
        explicit_domain: str = "",
    ) -> DomainContext:
        """입력으로부터 도메인을 판정하고 컨텍스트를 생성한다.

        우선순위:
        1. 사용자가 명시한 domain
        2. 명확한 document_type
        3. deterministic domain classifier
        4. 모호하면 other / REVIEW_REQUIRED
        """
        # 1. Explicit domain
        if explicit_domain:
            try:
                domain = Domain(explicit_domain)
            except ValueError:
                domain = Domain.OTHER
            domain_result = DomainResult(
                domain=domain,
                confidence=1.0,
                reason=f"explicit={explicit_domain}",
            )
        else:
            # 2-3. Classifier
            domain_result = classify_domain(
                text=text,
                filename=filename,
                document_type=document_type,
            )

        # Resolve workspace/results paths
        ws_dir = None
        res_dir = None
        if self._settings:
            from auto_write.config import get_domain_workspace, get_domain_results
            if domain_result.domain != Domain.OTHER:
                ws_dir = get_domain_workspace(domain_result.domain.value, self._settings)
                res_dir = get_domain_results(domain_result.domain.value, self._settings)

        return DomainContext(
            domain=domain_result.domain,
            domain_result=domain_result,
            document_type=document_type,
            workspace_dir=ws_dir,
            results_dir=res_dir,
        )

    def resolve_from_docx(self, docx_path: Path) -> DomainContext:
        """DOCX 파일로부터 도메인을 판정한다."""
        try:
            from auto_write.services.doc_text_extract import extract_text
            text = extract_text(docx_path)
        except Exception:
            text = ""
        return self.resolve(text=text, filename=docx_path.name)


def resolve_domain(
    text: str = "",
    filename: str = "",
    document_type: str = "",
    explicit_domain: str = "",
    settings: Any = None,
) -> DomainContext:
    """편의 함수 — 도메인을 판정하고 컨텍스트를 반환한다."""
    router = DomainRouter(settings)
    return router.resolve(
        text=text,
        filename=filename,
        document_type=document_type,
        explicit_domain=explicit_domain,
    )
