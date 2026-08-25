"""M4 GENERATE_MISSING — gpt-image-1 only, missing_only opt-in (mock-first).

Contracts (ralplan acceptance #24):
- provider mock records OpenAI model ``gpt-image-1`` only
- Gemini call count is always 0 on gpt/hybrid paths
- calls <= min(missing_count, max_paid_calls)
- no network when ``enabled=False`` or ``missing_only`` and no gaps
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from auto_write.image_automation.models import (
    AnchorCandidate,
    MatchAction,
    MatchDecision,
    PipelineStage,
    VisualAsset,
)
from auto_write.services.image_providers import GPT_IMAGE_MODEL, build_missing_gpt_writer


@dataclass
class GenerateCallLog:
    """In-memory call log for tests / dry-run receipts."""

    provider: str
    model: str
    anchor_id: str
    prompt_hash: str
    out_rel: str


@dataclass
class GenerateMissingResult:
    generated: list[VisualAsset]
    skipped: list[str]
    call_log: list[GenerateCallLog]
    gemini_calls: int
    openai_calls: int
    receipt_path: Path | None = None
    draft: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


def _prompt_for_anchor(anchor: AnchorCandidate) -> str:
    # Non-identifying summary only — never ship full document body.
    parts = [
        f"psst={anchor.psst}",
        f"visual={anchor.needed_visual_type}",
        f"keywords={','.join(anchor.keywords[:5])}",
        f"preview={anchor.text_preview[:80]}",
    ]
    return " | ".join(parts)


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def missing_anchors(
    anchors: list[AnchorCandidate],
    decisions: list[MatchDecision],
) -> list[AnchorCandidate]:
    """Anchors without an AUTO match (review/skip/no decision) are missing."""
    auto_ids = {
        d.anchor_id
        for d in decisions
        if d.action == MatchAction.AUTO and d.asset_id
    }
    return [a for a in anchors if a.anchor_id not in auto_ids]


def _default_mock_writer(prompt: str, out_path: Path, *, model: str) -> None:
    """Deterministic 1x1 PNG stub — no network."""
    # Minimal valid PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png)


def _write_receipt(out_dir: Path, receipt: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / "generate_missing_receipt.json"
    tmp = receipt_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(receipt_path)
    return receipt_path


def generate_missing_assets(
    anchors: list[AnchorCandidate],
    decisions: list[MatchDecision],
    *,
    out_dir: Path,
    enabled: bool = False,
    missing_only: bool = True,
    max_paid_calls: int = 0,
    use_mock: bool = True,
    writer: Callable[..., None] | None = None,
    settings: Any | None = None,
    openai_service: Any | None = None,
) -> GenerateMissingResult:
    """Generate images only for unmatched anchors when explicitly enabled.

    Real OpenAI is never called from this module unless ``use_mock=False`` and
    ``settings``/``openai_service`` supply a key, or a custom ``writer`` is injected.
    Default path is mock PNG stubs.
    """
    out_dir = Path(out_dir)
    gaps = missing_anchors(anchors, decisions) if missing_only else list(anchors)
    call_log: list[GenerateCallLog] = []
    generated: list[VisualAsset] = []
    skipped: list[str] = []
    gap_ids = [a.anchor_id for a in gaps]

    if not enabled:
        return GenerateMissingResult(
            generated=[],
            skipped=gap_ids,
            call_log=[],
            gemini_calls=0,
            openai_calls=0,
            draft=True,
            extras={"reason": "disabled", "stage": PipelineStage.GENERATE_MISSING.value},
        )

    budget = max(0, int(max_paid_calls))
    if budget <= 0:
        receipt_path = _write_receipt(
            out_dir,
            {
                "stage": PipelineStage.GENERATE_MISSING.value,
                "model": GPT_IMAGE_MODEL,
                "gemini_calls": 0,
                "openai_calls": 0,
                "openai_calls_real": 0,
                "mock_calls": 0,
                "max_paid_calls": budget,
                "missing_count": len(gaps),
                "generated": [],
                "skipped": gap_ids,
                "calls": [],
                "use_mock": use_mock,
                "reason": "budget_zero",
            },
        )
        return GenerateMissingResult(
            generated=[],
            skipped=gap_ids,
            call_log=[],
            gemini_calls=0,
            openai_calls=0,
            receipt_path=receipt_path,
            draft=True,
            extras={
                "reason": "budget_zero",
                "stage": PipelineStage.GENERATE_MISSING.value,
                "use_mock": use_mock,
            },
        )

    write_fn = writer
    if write_fn is None and not use_mock:
        write_fn = build_missing_gpt_writer(settings, openai_service)
    if write_fn is None and use_mock:
        write_fn = _default_mock_writer
    if write_fn is None:
        return GenerateMissingResult(
            generated=[],
            skipped=gap_ids,
            call_log=[],
            gemini_calls=0,
            openai_calls=0,
            draft=True,
            extras={"reason": "no_writer", "stage": PipelineStage.GENERATE_MISSING.value},
        )

    is_mock = write_fn is _default_mock_writer
    provider = "mock" if is_mock else "openai"
    for i, anchor in enumerate(gaps):
        if i >= budget:
            skipped.append(anchor.anchor_id)
            continue
        prompt = _prompt_for_anchor(anchor)
        ph = _prompt_hash(prompt)
        rel = f"generated/{anchor.anchor_id}-{ph}.png"
        out_path = out_dir / rel
        try:
            write_fn(prompt, out_path, model=GPT_IMAGE_MODEL)
        except OSError:
            skipped.append(anchor.anchor_id)
            continue
        sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
        asset = VisualAsset(
            asset_id=f"gen-{anchor.anchor_id}",
            source_kind="generated",
            path_rel=rel.replace("\\", "/"),
            sha256=sha,
            width=1,
            height=1,
            psst=anchor.psst,
            visual_type=anchor.needed_visual_type,
            source_label=GPT_IMAGE_MODEL,
            text_hint=anchor.text_preview[:80],
        )
        generated.append(asset)
        call_log.append(
            GenerateCallLog(
                provider=provider,
                model=GPT_IMAGE_MODEL,
                anchor_id=anchor.anchor_id,
                prompt_hash=ph,
                out_rel=asset.path_rel,
            )
        )

    mock_calls = len(call_log) if is_mock else 0
    openai_calls_real = 0 if is_mock else len(call_log)
    # openai_calls = budgeted gpt-image-1 slot count (mock 포함 — 상한 계약용)
    receipt = {
        "stage": PipelineStage.GENERATE_MISSING.value,
        "model": GPT_IMAGE_MODEL,
        "gemini_calls": 0,
        "openai_calls": len(call_log),
        "openai_calls_real": openai_calls_real,
        "mock_calls": mock_calls,
        "max_paid_calls": budget,
        "missing_count": len(gaps),
        "generated": [a.model_dump() for a in generated],
        "skipped": skipped,
        "calls": [c.__dict__ for c in call_log],
        "use_mock": is_mock,
    }
    receipt_path = _write_receipt(out_dir, receipt)

    return GenerateMissingResult(
        generated=generated,
        skipped=skipped,
        call_log=call_log,
        gemini_calls=0,
        openai_calls=len(call_log),
        receipt_path=receipt_path,
        draft=is_mock or bool(skipped),
        extras={
            "stage": PipelineStage.GENERATE_MISSING.value,
            "use_mock": is_mock,
            "openai_calls_real": openai_calls_real,
            "mock_calls": mock_calls,
        },
    )
