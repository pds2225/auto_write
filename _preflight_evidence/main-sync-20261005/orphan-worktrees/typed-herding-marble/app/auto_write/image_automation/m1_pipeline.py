"""M1 파이프라인: NOTEBOOKLM(+선택) → SLIDE_SPLIT → CITATIONS."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from auto_write.image_automation.citation_report import (
    build_citations,
    extract_pdf_hyperlinks,
    requires_draft,
    write_citation_reports,
)
from auto_write.image_automation.download_verify import verify_download
from auto_write.image_automation.models import PipelineStage, RunManifest, StageStatus
from auto_write.image_automation.notebooklm_browser import NotebookLMBrowser, summarize_upload_consent
from auto_write.image_automation.notebooklm_state import ExternalUploadBlocked
from auto_write.image_automation.paths import (
    anonymous_upload_name,
    ensure_run_dirs,
    sha256_file,
)
from auto_write.image_automation.receipts import append_event, config_hash_of, monotonic_ms, write_receipt
from auto_write.image_automation.repo_name import canonical_repo_name
from auto_write.image_automation.slide_asset_extractor import extract_slides
from auto_write.image_automation.document_pdf import normalize_to_pdf
from auto_write.models import EvidenceSource


@dataclass
class M1Result:
    run_id: str
    run_dir: Path
    manifest: RunManifest
    draft: bool
    report: dict[str, Any]


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def run_m1(
    input_path: Path,
    *,
    results_root: Path,
    mode: str = "notebooklm",
    allow_external_upload: bool = False,
    evidence: Iterable[EvidenceSource] | None = None,
    dry_run: bool = False,
    cwd: Path | None = None,
    slides_input: Path | None = None,
    browser: NotebookLMBrowser | None = None,
    run_id: str | None = None,
) -> M1Result:
    """
    M1: 정규화 PDF 준비 → (옵션) NotebookLM → 슬라이드 PNG → 출처목록.

    실제 NotebookLM 업로드/생성은 allow_external_upload=True 이고 browser stub/실세션이
    있을 때만 진행. 기본은 업로드 차단 후 로컬 슬라이드 분리·출처 검증만 수행 가능.
    """
    input_path = Path(input_path)
    rid = run_id or new_run_id()
    dirs = ensure_run_dirs(rid, results_root)
    events = dirs["root"] / "events.jsonl"
    manifest = RunManifest(run_id=rid)
    report: dict[str, Any] = {"run_id": rid, "mode": mode, "manual_actions": []}

    # --- normalize ---
    t0 = monotonic_ms()
    append_event(events, run_id=rid, stage=PipelineStage.NOTEBOOKLM.value, attempt=1, event="START")
    norm = normalize_to_pdf(input_path, dirs["root"] / "normalized")
    repo_name, origin = canonical_repo_name(cwd or Path.cwd())
    upload_name = anonymous_upload_name(repo_name, norm.sha256)
    consent = summarize_upload_consent(
        provider="notebooklm",
        anon_name=upload_name,
        sha256=norm.sha256,
        page_count=norm.page_count,
    )
    report["upload_consent_summary"] = consent
    report["repo_name"] = repo_name
    report["origin_url_present"] = bool(origin)

    notebook_result = None
    if mode in {"notebooklm", "hybrid"}:
        if dry_run:
            report["notebooklm"] = "dry_run_skipped"
            manifest.stages[PipelineStage.NOTEBOOKLM.value] = StageStatus.SKIPPED
        elif not allow_external_upload:
            manifest.stages[PipelineStage.NOTEBOOKLM.value] = StageStatus.MANUAL_ACTION
            report["notebooklm"] = "external_upload_blocked"
            report["manual_actions"].append(
                "재실행 시 --allow-external-upload 를 명시하고 대상 PDF·NotebookLM 전송을 확인하세요."
            )
            append_event(
                events,
                run_id=rid,
                stage=PipelineStage.NOTEBOOKLM.value,
                attempt=1,
                event="MANUAL_ACTION",
                code="external_upload_blocked",
                duration_ms=monotonic_ms() - t0,
            )
        else:
            nb = browser or NotebookLMBrowser(allow_external_upload=True, cwd=cwd)
            try:
                notebook_result = nb.run_stub_happy_path(
                    norm.path,
                    download_to=None,
                ) if getattr(nb, "session", None) is not None else nb.run_pre_upload_gate()
            except ExternalUploadBlocked as exc:
                notebook_result = None
                report["notebooklm_error"] = str(exc)
                manifest.stages[PipelineStage.NOTEBOOKLM.value] = StageStatus.FAIL
            if notebook_result is not None:
                report["notebooklm"] = {
                    "state": notebook_result.state.value,
                    "code": notebook_result.code,
                    "file_chooser_calls": notebook_result.file_chooser_calls,
                    "generate_clicks": notebook_result.generate_clicks,
                    "checked_source_count": notebook_result.checked_source_count,
                    "upload_name": notebook_result.upload_name,
                }
                write_receipt(
                    dirs["receipts"],
                    PipelineStage.NOTEBOOKLM.value,
                    norm.sha256,
                    config_hash_of({"mode": mode, "upload_name": upload_name}),
                    {
                        "status": notebook_result.state.value,
                        "code": notebook_result.code,
                        "attempt": notebook_result.attempt,
                        "checked_source_count": notebook_result.checked_source_count,
                        "upload_name": notebook_result.upload_name,
                        "origin_url_hash": notebook_result.origin_url_hash,
                    },
                )
                if notebook_result.code == "done":
                    manifest.stages[PipelineStage.NOTEBOOKLM.value] = StageStatus.DONE
                    append_event(
                        events,
                        run_id=rid,
                        stage=PipelineStage.NOTEBOOKLM.value,
                        attempt=notebook_result.attempt,
                        event="END",
                        code="done",
                        duration_ms=monotonic_ms() - t0,
                        counters={"generate_clicks": notebook_result.generate_clicks},
                    )
                else:
                    manifest.stages[PipelineStage.NOTEBOOKLM.value] = StageStatus.MANUAL_ACTION
                    append_event(
                        events,
                        run_id=rid,
                        stage=PipelineStage.NOTEBOOKLM.value,
                        attempt=notebook_result.attempt,
                        event="MANUAL_ACTION",
                        code=notebook_result.code,
                        duration_ms=monotonic_ms() - t0,
                    )
    else:
        manifest.stages[PipelineStage.NOTEBOOKLM.value] = StageStatus.SKIPPED

    # --- slide split ---
    t1 = monotonic_ms()
    append_event(events, run_id=rid, stage=PipelineStage.SLIDE_SPLIT.value, attempt=1, event="START")
    split_src = Path(slides_input) if slides_input else norm.path
    # if notebook produced a download and verified, prefer it
    if notebook_result and notebook_result.download_path and Path(notebook_result.download_path).is_file():
        verified = verify_download(Path(notebook_result.download_path), allowed_preexisting=set())
        split_src = verified.path
        report["download"] = {
            "kind": verified.kind,
            "pages": verified.page_or_slide_count,
            "size": verified.size,
        }

    extract = extract_slides(split_src, dirs["slides"])
    manifest.assets = extract.assets
    manifest.stages[PipelineStage.SLIDE_SPLIT.value] = StageStatus.DONE
    manifest.artifact_rels.extend([a.path_rel for a in extract.assets])
    append_event(
        events,
        run_id=rid,
        stage=PipelineStage.SLIDE_SPLIT.value,
        attempt=1,
        event="END",
        code="done",
        duration_ms=monotonic_ms() - t1,
        counters={"png_count": extract.page_count},
    )
    report["slides"] = {
        "page_count": extract.page_count,
        "reused": extract.reused,
        "dpi": extract.dpi,
        "input_sha256_prefix": extract.input_sha256[:8],
    }

    # --- citations ---
    pdf_urls = extract_pdf_hyperlinks(norm.path)
    ev_list = list(evidence or [])
    citations = build_citations(ev_list, pdf_urls=pdf_urls)
    # mark used_on for verified ones as slide range summary
    for i, c in enumerate(citations, start=1):
        if not c.used_on:
            c.used_on = f"slide:{min(i, extract.page_count)}"
    paths = write_citation_reports(citations, dirs["citations"])
    manifest.citations = citations
    draft = requires_draft(citations)
    # external upload blocked also forces draft for notebooklm mode
    if mode in {"notebooklm", "hybrid"} and not allow_external_upload and not dry_run:
        draft = True
    if notebook_result and notebook_result.draft:
        draft = True
    manifest.draft = draft
    report["citations"] = {
        "count": len(citations),
        "draft": draft,
        "sources_json": str(paths["json"]),
        "sources_md": str(paths["md"]),
        "sources_csv": str(paths["csv"]),
    }
    report["draft"] = draft

    # persist manifest
    man_path = dirs["root"] / "manifest.json"
    man_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    (dirs["root"] / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return M1Result(run_id=rid, run_dir=dirs["root"], manifest=manifest, draft=draft, report=report)
