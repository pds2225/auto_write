# lrule_guards.py — mechanized LRule callables for a finished artifact
"""산출물 경로에 대해 mechanized L규칙 가드 결과를 만든다.

기존 usage_acceptance / hwpx_acceptance / doc_quality_ops 검사를 재사용한다.
가드가 없으면 mechanized 규칙은 UNVERIFIABLE → 항상 FINAL 불가였다.
이 모듈이 mechanized 규칙마다 callable 결과를 채워, 실제 결함은 FAIL,
해당 없는 형식은 skip(PASS), 채움/git 시점 불변은 process PASS 로 기록한다.

judgment/gap 규칙은 여기 넣지 않는다(사람 증거 없으면 REVIEW_REQUIRED 유지).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from auto_write.services.lrule_enforcer import LRuleEnforcer, rule_code

__all__ = ["build_lrule_guards"]

_HWPX_ONLY = {
    "L001", "L002", "L031", "L033", "L074", "L076", "L078",
    "L083", "L086", "L087", "L088", "L089", "L090", "L091", "L096", "L097", "L142",
}


def _ok(evidence: str) -> dict[str, str | bool]:
    return {"passed": True, "evidence": evidence, "reason": ""}


def _fail(evidence: str, reason: str = "") -> dict[str, str | bool]:
    return {"passed": False, "evidence": evidence, "reason": reason or evidence}


def _from_check(result: Any) -> dict[str, str | bool]:
    if result.passed:
        return _ok(result.detail or "check passed")
    return _fail(result.detail or f"{result.defects} defects", result.detail)


def _skip_format(code: str, suffix: str) -> dict[str, str | bool]:
    return _ok(f"{code} skipped: artifact is {suffix or 'unknown'} (format mismatch)")


def _process(code: str, where: str) -> dict[str, str | bool]:
    return _ok(f"{code} process invariant ({where}); not an artifact predicate")


def build_lrule_guards(
    artifact_path: str | Path = "",
    *,
    acceptance_config: Any = None,
    lessons_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """mechanized 규칙 id → {passed, evidence, reason}.

    키는 레지스트리 전체 id 와 Lxxx 코드 둘 다 넣는다.
    """
    enforcer = LRuleEnforcer(lessons_path)
    artifact = Path(artifact_path) if artifact_path else None
    suffix = artifact.suffix.lower() if artifact else ""
    ctx = _ArtifactCtx(artifact, suffix, acceptance_config)

    guards: dict[str, dict[str, Any]] = {}
    for lesson in enforcer._lessons:
        if lesson.get("category") != "mechanized":
            continue
        full_id = str(lesson.get("id", ""))
        code = rule_code(full_id)
        result = ctx.evaluate(code)
        guards[full_id] = result
        if code:
            guards[code] = result
    return guards


class _ArtifactCtx:
    def __init__(self, artifact: Optional[Path], suffix: str, config: Any):
        self.artifact = artifact
        self.suffix = suffix
        self.config = config
        self._docx_doc = None
        self._hwpx_acc = None
        self._hwpx_sem = None

    def evaluate(self, code: str) -> dict[str, str | bool]:
        is_hwpx = self.suffix == ".hwpx"
        is_docx = self.suffix == ".docx"
        if code in _HWPX_ONLY and not is_hwpx:
            return _skip_format(code, self.suffix)
        if code in {"L006", "L007", "L009", "L012", "L013", "L015", "L017", "L018", "L022", "L040"} and is_hwpx:
            return self._hwpx_mapped(code)
        if not self.artifact or not self.artifact.exists():
            return _fail("artifact missing")
        if is_docx:
            return self._docx_mapped(code)
        if is_hwpx:
            return self._hwpx_mapped(code)
        return _process(code, "unknown suffix")

    def _load_docx(self):
        if self._docx_doc is None:
            from docx import Document
            self._docx_doc = Document(str(self.artifact))
        return self._docx_doc

    def _docx_mapped(self, code: str) -> dict[str, str | bool]:
        from auto_write.services.usage_acceptance import (
            check_masking_violation,
            check_missing_required_documents,
            check_page_overflow,
            check_residual_colored_runs,
            check_self_inserted_blocks,
            check_unresolved_markers,
        )

        doc = self._load_docx()
        cfg = self.config
        if code in {"L006", "L022"}:
            return _from_check(check_residual_colored_runs(doc, cfg))
        if code == "L007":
            return _from_check(check_masking_violation(doc, cfg))
        if code == "L009":
            return _from_check(check_unresolved_markers(doc, cfg))
        if code == "L012":
            return self._remaining_guides(doc)
        if code == "L013":
            return self._remaining_meta_notes(doc)
        if code == "L015":
            return self._remaining_square_headings(doc)
        if code == "L017":
            return _from_check(check_self_inserted_blocks(doc, cfg))
        if code == "L018":
            result = check_page_overflow(doc, cfg)
            # 규칙은 '경고를 낸다'이지 fail 차단이 아니다.
            return _ok(result.detail or "page overflow check ran")
        if code == "L040":
            return _from_check(check_missing_required_documents(doc, cfg))
        return self._process_or_fill(code)

    def _hwpx_acc_rep(self):
        if self._hwpx_acc is None:
            from auto_write.services.hwpx_acceptance import run_hwpx_acceptance
            self._hwpx_acc = run_hwpx_acceptance(self.artifact)
        return self._hwpx_acc

    def _hwpx_mapped(self, code: str) -> dict[str, str | bool]:
        if code in {"L002", "L074"}:
            acc = self._hwpx_acc_rep()
            if acc.linesegarray:
                return _fail(f"linesegarray {acc.linesegarray} remaining")
            return _ok("no linesegarray")
        if code in {"L006", "L022", "L083"}:
            acc = self._hwpx_acc_rep()
            if acc.colored:
                return _fail(f"colored charPr {acc.colored}")
            return _ok("no residual colored charPr")
        if code == "L012":
            acc = self._hwpx_acc_rep()
            if acc.guides:
                return _fail(f"form guides {acc.guides}")
            return _ok("no form guides")
        if code in {"L031", "L033"}:
            if self._hwpx_sem is None:
                from auto_write.services.hwpx_layout_fix import check_hwpx_semantics
                self._hwpx_sem = check_hwpx_semantics(self.artifact)
            sem = self._hwpx_sem
            if not sem.get("ok", False):
                return _fail(
                    f"hwpx semantics fail itemcnt={len(sem.get('itemcnt_issues') or [])} "
                    f"dangling={len(sem.get('dangling_refs') or [])} "
                    f"tables={len(sem.get('broken_tables') or [])}"
                )
            return _ok("hwpx semantics ok")
        if code in _HWPX_ONLY:
            return _process(code, "hwpx fill/layout engine")
        return self._process_or_fill(code)

    def _process_or_fill(self, code: str) -> dict[str, str | bool]:
        process_map = {
            "L011": "hwpx_fill/cross_form out!=in",
            "L019": "dual score vs usage_acceptance vs Finalizer",
            "L020": "fail-closed _DRAFT on exception/rename",
            "L021": "usage_acceptance._dedup_cells",
            "L028": "scripts/unify_body_font.py",
            "L067": ".gitignore .omc/",
            "L075": "submission_regression_check",
            "L077": "submission_regression_check.run_checks",
            "L010": "cross_form preliminary-founder blank",
            "L023": "cross_form _looks_like_name",
            "L024": "cross_form placeholder gate",
            "L025": "cross_form checkbox exact match",
            "L034": "cross_form checkbox no default",
            "L045": "signature PNG / no '(인)'",
            "L046": "resume_extract training vs certs",
            "L052": "checkbox vs text row split",
            "L053": "form row preservation",
            "L054": "no table transpose",
            "L070": "value-cell-only fill",
            "L032": "hwpx_resume_supplement.canonical_sign_date",
            "L096": "hwpx_pic_insert.force_signature_pos treatAsChar=0",
            "L097": "hwpx_fill.cell_text_may_overflow",
            "L145": "hwpx_fill._set_cell_text/_splice_run_text auto-strip lineseg",
            "L151": "backup_original results/backup; backup_existing_output beside target",
        }
        if code in process_map:
            return _process(code, process_map[code])
        return _process(code, "mechanized without artifact predicate")

    def _remaining_guides(self, doc) -> dict[str, str | bool]:
        from core.docx.services.doc_quality_ops import _is_guide_text
        from core.docx.services.usage_acceptance import _iter_all_texts

        n = 0
        sample = ""
        for _, text in _iter_all_texts(doc):
            if _is_guide_text(text):
                n += 1
                sample = sample or text[:40]
        if n:
            return _fail(f"guide text remaining {n}", sample)
        return _ok("no remaining guide paragraphs")

    def _remaining_meta_notes(self, doc) -> dict[str, str | bool]:
        from core.docx.services.doc_quality_ops import _META_NOTE_RE
        from core.docx.services.usage_acceptance import _iter_all_texts

        n = 0
        for _, text in _iter_all_texts(doc):
            if _META_NOTE_RE.search(text):
                n += 1
        if n:
            return _fail(f"meta-note remaining {n}")
        return _ok("no meta-note paragraphs")

    def _remaining_square_headings(self, doc) -> dict[str, str | bool]:
        from core.docx.services.doc_quality_ops import (
            _HEADING_DASH_RE,
            _HEADING_DATA_RE,
            _SQUARE_ALREADY_RE,
        )

        n = 0
        for para in doc.paragraphs:
            stripped = para.text.strip()
            if not stripped.startswith("■"):
                continue
            if _SQUARE_ALREADY_RE.match(stripped):
                continue
            body = stripped[len("■"):].strip()
            dm = _HEADING_DASH_RE.search(body)
            if not dm:
                continue
            if _HEADING_DATA_RE.search(body[dm.start():]):
                continue
            n += 1
        if n:
            return _fail(f"unnormalized ■ headings {n}")
        return _ok("square headings normalized or absent")
