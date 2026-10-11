"""제출 마감 파이프라인: 채운 HWPX → 직인 → 체크박스 → 구조검증 → PDF → 첨부 가림 → 합본 → Visual QA → 보고서.

각 단계는 기존 F1~F7 모듈을 호출만 한다. 최종 제출 여부는 판단하지 않는다(12장).
기술적 FAIL 이 있으면 '(제출)' 명칭 PDF 대신 '(검토용)' 명칭으로 만든다(산출물 생성 통제).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .final_check import check_hwpx_structure, should_block_submission_named_pdf
from .pdf_package import build_submission_name, convert_hwpx_to_pdf, merge_pdfs
from .pdf_checks import check_pdf_layout
from .pii_redact import redact_pdf
from .report import build_report, write_report
from .status import Finding, Status
from .visual_qa import NoneProvider, load_manual_findings, run_visual_qa


@dataclass
class SubmitFinishInputs:
    filled_hwpx: Path                      # F3/F4 가 채운 HWPX(원본 양식 아님)
    out_dir: Path
    doc_name: str
    company: str
    rep: str
    baseline_form: Path | None = None      # 원본 양식(양식 생존 비교용, 읽기 전용)
    seals: Sequence[Any] = ()              # SealSpec 목록
    write_names: bool = False
    checkbox_decisions: dict | None = None
    consents: dict | None = None           # 항목별 사용자 명시 승인만
    attachments: Sequence[Path] = ()       # 첨부 PDF(원본은 수정하지 않음)
    redact_attachments: bool = True
    visual_provider: Any = None            # None → NoneProvider(외부 호출 없음)
    manual_visual_json: Path | None = None # manual-agent visual check 결과
    converter: Callable | None = None      # None → 실제 한글 COM
    allowed_names: tuple[str, ...] = ()
    apply_submission_cleanup: bool = True  # 기존 공통 후처리: 검정 글씨·linesegarray 제거(양식 문구는 건드리지 않음)
    expected_page_order: Sequence[str] = ()  # 합본에서 이 순서로 나와야 하는 문서 식별 문구


@dataclass
class SubmitFinishResult:
    findings: list[Finding] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    report_json: Path | None = None
    report_md: Path | None = None
    named_pdf_blocked: bool = False


def run_submit_finish(inp: SubmitFinishInputs) -> SubmitFinishResult:
    from .checkbox_select import select_checkboxes
    from .seal_stamp import stamp_seals

    out = Path(inp.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res = SubmitFinishResult()
    F = res.findings
    cur = out / "01_filled.hwpx"
    shutil.copy2(inp.filled_hwpx, cur)  # 이후 단계는 사본만 수정한다
    n = 1

    def nxt(label: str) -> Path:
        nonlocal n
        n += 1
        return out / f"{n:02d}_{label}.hwpx"

    if inp.seals:
        dst = nxt("stamped")
        kw = {"write_names": True} if inp.write_names else {}
        r = stamp_seals(cur, dst, list(inp.seals), **kw)
        F.extend(r["findings"])
        cur = dst
    if inp.checkbox_decisions is not None or inp.consents is not None:
        dst = nxt("checked")
        r = select_checkboxes(cur, dst, inp.checkbox_decisions or {}, consents=inp.consents)
        F.extend(r["findings"])
        cur = dst
    if inp.apply_submission_cleanup:
        from auto_write.services.hwpx_submission_cleanup import finalize_submission_hwpx

        dst = nxt("cleaned")
        stats = finalize_submission_hwpx(cur, dst, force_black=True, remove_guides=False, strip_lineseg=True)
        F.append(Finding("SUBMISSION_CLEANUP", Status.PASS, "공통 후처리 적용: 검정 글씨·linesegarray 제거",
                         source="engine", evidence=str(stats)))
        cur = dst
    res.artifacts["final_hwpx"] = str(cur)

    # F7-A 구조 검증
    name_edits = sum(1 for f in F if f.meta.get("name_written") is True)
    F.extend(check_hwpx_structure(cur, baseline_form=inp.baseline_form, allowed_names=inp.allowed_names,
                                  expected_phrase_edits=name_edits))
    res.named_pdf_blocked = should_block_submission_named_pdf(F)

    # F6 신청서 PDF
    app_pdf = out / "10_application.pdf"
    conv = convert_hwpx_to_pdf(cur, app_pdf, converter=inp.converter)
    F.extend(conv.findings)
    real_env: dict[str, Any] = {"hancom_com_real": conv.real_com, "convert_attempts": conv.attempts}

    # F5 첨부 가림(원본 미수정, 사본 생성)
    merge_inputs: list[Path] = [app_pdf] if conv.ok else []
    redaction_ok = True
    for i, att in enumerate(inp.attachments, 1):
        att = Path(att)
        if inp.redact_attachments:
            red = out / f"2{i}_{att.stem}_가림.pdf"
            rr = redact_pdf(att, red)
            F.extend(rr.findings)
            if rr.undetected_pages or rr.status not in (Status.PASS, Status.NA):
                redaction_ok = False
            merge_inputs.append(red)
        else:
            redaction_ok = False  # 가림 확인 없는 첨부는 외부 AI 전송 금지
            merge_inputs.append(att)

    # F6 합본
    merged: Path | None = None
    if conv.ok:
        name = build_submission_name(inp.doc_name, inp.company, inp.rep)
        if res.named_pdf_blocked:
            name = name.replace("(제출)", "(검토용)", 1)
        mg = merge_pdfs(merge_inputs, out / name)
        F.extend(mg.findings)
        if mg.ok:
            merged = mg.out
            res.artifacts["merged_pdf"] = str(mg.out)
            real_env["merged_pages"] = mg.total_pages
            F.extend(check_pdf_layout(mg.out, expected_order=list(inp.expected_page_order) or None))
            real_env["manifest"] = mg.manifest

    # F7-B Visual QA (가림 확인 전에는 외부 전송 차단)
    usage: dict[str, Any] = {}
    if merged:
        provider = inp.visual_provider or NoneProvider()
        manual = load_manual_findings(inp.manual_visual_json) if inp.manual_visual_json else None
        vr = run_visual_qa(merged, out / "visual", provider, redaction_confirmed=redaction_ok,
                           cache_dir=out / "visual_cache", manual_findings=manual)
        F.extend(vr.findings)
        usage = vr.usage
        real_env["visual_provider"] = vr.provider_name
        real_env["visual_pages"] = vr.pages

    report = build_report(F, title=f"{inp.doc_name} 검수 보고서", visual_usage=usage,
                          artifacts=res.artifacts, real_environment=real_env)
    res.report_json, res.report_md = write_report(report, out)
    return res
