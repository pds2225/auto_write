"""이미지 자동화 공통 데이터 계약 (기존 auto_write.models 와 분리)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    """내부 단계 ID. 보고서에서만 P1~P7 로 표시한다."""

    SLIDE_SPLIT = "SLIDE_SPLIT"
    CLASSIFY = "CLASSIFY"
    MATCH = "MATCH"
    INSERT = "INSERT"
    GENERATE_MISSING = "GENERATE_MISSING"
    NOTEBOOKLM = "NOTEBOOKLM"
    ORCHESTRATE = "ORCHESTRATE"


class CitationStatus(str, Enum):
    VERIFIED = "verified"
    MISSING_TITLE = "missing_title"
    MISSING_ORGANIZATION = "missing_organization"
    MISSING_YEAR = "missing_year"
    MISSING_URL = "missing_url"
    MISMATCH = "mismatch"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAIL = "fail"
    MANUAL_ACTION = "manual_action"
    SKIPPED = "skipped"


class SourceCitation(BaseModel):
    """출처 후보. 연도는 원문에 명시된 값만 보관한다(checked_at 재사용 금지)."""

    title: str = ""
    organization: str = ""
    year: str = ""
    url: str = ""
    used_on: str = ""
    status: CitationStatus = CitationStatus.MISSING_TITLE


class SourceDocument(BaseModel):
    kind: Literal["pdf", "pptx", "docx", "hwp", "hwpx", "unknown"] = "unknown"
    sha256: str = ""
    normalized_pdf_sha256: str = ""
    page_count: int = 0


class VisualAsset(BaseModel):
    asset_id: str
    source_kind: Literal["slide", "library", "generated"] = "slide"
    slide_index: int | None = None
    path_rel: str = ""
    sha256: str = ""
    width: int = 0
    height: int = 0
    dpi: int = 0
    psst: str = "99_unclassified"
    visual_type: str = ""
    source_label: str = ""
    parent_hint: str = ""
    text_hint: str = ""


class PsstClass(str, Enum):
    PROBLEM = "01_problem"
    SOLUTION = "02_solution"
    SCALE_UP = "03_scale_up"
    TEAM = "04_team"
    UNCLASSIFIED = "99_unclassified"


class AnchorCandidate(BaseModel):
    anchor_id: str
    section: str = ""
    psst: str = PsstClass.UNCLASSIFIED.value
    anchor_hash: str = ""
    location_id: str = ""
    needed_visual_type: str = ""
    keywords: list[str] = Field(default_factory=list)
    text_preview: str = ""


class MatchAction(str, Enum):
    AUTO = "auto"
    REVIEW = "review"
    SKIP = "skip"


class MatchDecision(BaseModel):
    anchor_id: str
    asset_id: str = ""
    score: float = 0.0
    score_detail: dict[str, float] = Field(default_factory=dict)
    action: MatchAction = MatchAction.SKIP
    insert_status: str = "pending"
    reason: str = ""
    runner_up_score: float | None = None


class NotebookLMCheckpoint(BaseModel):
    notebook_url_id: str = ""
    notebook_title_hash: str = ""
    upload_file_hash: str = ""
    state: str = ""
    download_rel: str = ""
    checked_source_count: int | None = None
    attempt: int = 1


class RunManifest(BaseModel):
    schema_version: str = "1.0"
    run_id: str
    stages: dict[str, StageStatus] = Field(default_factory=dict)
    error_codes: list[str] = Field(default_factory=list)
    artifact_rels: list[str] = Field(default_factory=list)
    receipts: list[str] = Field(default_factory=list)
    source_document: SourceDocument | None = None
    assets: list[VisualAsset] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    anchors: list[AnchorCandidate] = Field(default_factory=list)
    matches: list[MatchDecision] = Field(default_factory=list)
    notebooklm: NotebookLMCheckpoint | None = None
    draft: bool = False
    extras: dict[str, Any] = Field(default_factory=dict)
