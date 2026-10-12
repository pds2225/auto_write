"""제출 마감 파이프라인: 채운 HWPX → 직인 → 체크박스 → 구조검증 → PDF → 첨부 가림 → 합본 → Visual QA → 보고서.

각 단계는 기존 F1~F7 모듈을 호출만 한다. 최종 제출 여부는 판단하지 않는다(12장).
기술적 FAIL 이 있으면 '(제출)' 명칭 PDF 대신 '(검토용)' 명칭으로 만든다(산출물 생성 통제).
"""
from __future__ import annotations

import datetime as _dt
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .final_check import check_hwpx_structure, should_block_submission_named_pdf
from .pdf_package import build_submission_name, convert_hwpx_to_pdf, merge_pdfs
from .pdf_checks import check_pdf_layout, check_reading_order
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
    submit_date: str | None = None         # 'YYYY-MM-DD' — 사용자가 명시한 경우에만 서명 줄 빈 날짜에 기입
    layout_guard: bool = True              # 떠 있는 표 분리 + 원본 쪽 시작 제목 고정(baseline_form 필요)
    baseline_pdf: Path | None = None       # 원본 양식을 이미 렌더한 PDF(없으면 baseline_form 을 변환해 만든다)


@dataclass
class SubmitFinishResult:
    findings: list[Finding] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    report_json: Path | None = None
    report_md: Path | None = None
    named_pdf_blocked: bool = False


_MAX_COMPACT = 6  # 빈 문단 정리 반복 상한(렌더 1회 ≈ 15초)


def run_submit_finish(inp: SubmitFinishInputs) -> SubmitFinishResult:
    from .checkbox_select import select_checkboxes
    from .seal_stamp import stamp_seals

    out = Path(inp.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res = SubmitFinishResult()
    F = res.findings
    cur = out / "01_filled.hwpx"
    shutil.copy2(inp.filled_hwpx, cur)  # 이후 단계는 사본만 수정한다
    structure_baseline = inp.baseline_form
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
    if inp.submit_date:
        from .date_fill import fill_date_lines

        dst = nxt("dated")
        r = fill_date_lines(cur, dst, _dt.date.fromisoformat(inp.submit_date))
        F.extend(r["findings"])
        cur = dst
    if inp.apply_submission_cleanup:
        from auto_write.services.hwpx_submission_cleanup import finalize_submission_hwpx

        dst = nxt("cleaned")
        stats = finalize_submission_hwpx(cur, dst, force_black=True, remove_guides=False, strip_lineseg=True)
        F.append(Finding("SUBMISSION_CLEANUP", Status.PASS, "공통 후처리 적용: 검정 글씨·linesegarray 제거",
                         source="engine", evidence=str(stats)))
        cur = dst
    base_pdf: Path | None = None
    pre_conv = None  # 레이아웃 보정 중 마지막으로 렌더한 신청서 PDF 결과(그대로 F6 에 쓴다)
    if inp.layout_guard:
        from .layout_guard import (anchors_of, baseline_page_start_titles, compact_overflow,
                                   find_overflow_sections, repair_layout, section_spans)
        from .seal_align import align_to_markers, make_probe

        titles: list[str] = []
        if inp.baseline_form:
            base_pdf = Path(inp.baseline_pdf) if inp.baseline_pdf else None
            if base_pdf is None or not base_pdf.is_file():
                bc = convert_hwpx_to_pdf(inp.baseline_form, out / "00_baseline.pdf", converter=inp.converter,
                                         retries=1, overwrite=True)
                base_pdf = bc.pdf if bc.ok else None
                if not bc.ok:
                    F.append(Finding("LAYOUT_BASELINE_UNVERIFIED", Status.UNVERIFIED,
                                     "기술적 검증 미실행: 원본 양식 렌더 실패로 쪽 시작 위치 고정 생략",
                                     source="engine", evidence=" | ".join(bc.reasons)[:300]))
            if base_pdf is not None:
                titles = baseline_page_start_titles(inp.baseline_form, base_pdf)
        dst = nxt("layout")
        r = repair_layout(cur, dst, page_start_titles=titles)
        F.extend(r["findings"])
        cur = dst
        compact_steps: list[int] = []

        # 렌더 기반 보정 1: 값이 길어 한 부의 끝 몇 줄이 다음 쪽으로 넘어간 경우 빈 문단을 한 개씩 줄여 본다.
        app_pdf = out / "10_application.pdf"
        pre_conv = convert_hwpx_to_pdf(cur, app_pdf, converter=inp.converter, overwrite=True)
        if pre_conv.ok and base_pdf is not None and titles:
            anchors = anchors_of(cur)
            base_spans = section_spans(base_pdf, anchors)
            removed_total = 0
            for _ in range(_MAX_COMPACT):
                spans = section_spans(pre_conv.pdf, anchors)
                over = find_overflow_sections(spans, base_spans)
                if not over:
                    break
                dst = nxt("compact")
                cr = compact_overflow(cur, dst, over[0])
                if not cr["removed"]:
                    F.append(Finding("LAYOUT_OVERFLOW_TAIL", Status.REVIEW,
                                     "시각적 오류 의심: 값이 길어 한 부의 끝이 다음 쪽으로 넘어갔으나 줄일 빈 문단이 없음 — 사용자 확인 필요",
                                     source="engine", meta={"section": over[0]}))
                    break
                cur = dst
                removed_total += 1
                compact_steps.append(over[0])
                pre_conv = convert_hwpx_to_pdf(cur, app_pdf, converter=inp.converter, overwrite=True)
                if not pre_conv.ok:
                    break
            if removed_total:
                F.append(Finding("LAYOUT_COMPACT", Status.PASS,
                                 f"자동 검사 PASS: 넘친 쪽을 줄이려 원본의 빈 문단 {removed_total}개 정리(글자·표·그림 변경 없음)",
                                 source="engine", meta={"removed_spacers": removed_total}))
        if (r["split"] or compact_steps) and inp.baseline_form:
            # 문단 분리·빈 문단 정리는 구조 비교(문단 수)에 잡히므로, 원본에도 같은 처리를 되풀이한 사본을 기준으로 비교한다.
            norm = out / "00_baseline_layout.hwpx"
            repair_layout(inp.baseline_form, norm, page_start_titles=titles)
            for k, idx in enumerate(compact_steps):
                step = out / f"00_baseline_layout_{k}.hwpx"
                compact_overflow(norm, step, idx)
                norm = step
            structure_baseline = norm
        # 렌더 기반 보정 2: 직인을 서명 표식 위치에 맞춘다(렌더 실측).
        if pre_conv.ok and inp.seals and any(f.code == "F1_SEAL_INSERTED" for f in F):
            probe = nxt("sealprobe")
            if make_probe(cur, probe)["seals"]:
                pc = convert_hwpx_to_pdf(probe, out / "tmp_probe.pdf", converter=inp.converter, overwrite=True)
                if pc.ok:
                    dst = nxt("sealaligned")
                    ar = align_to_markers(probe, pc.pdf, dst)
                    F.extend(ar["findings"])
                    if ar["aligned"]:
                        cur = dst
                        pre_conv = convert_hwpx_to_pdf(cur, app_pdf, converter=inp.converter, overwrite=True)
                else:
                    F.append(Finding("SEAL_ALIGN_UNVERIFIED", Status.UNVERIFIED,
                                     "기술적 검증 미실행: 직인 위치 실측 렌더 실패 — 기본 위치 유지",
                                     source="engine", evidence=" | ".join(pc.reasons)[:300]))
    res.artifacts["final_hwpx"] = str(cur)

    # F7-A 구조 검증
    name_edits = sum(1 for f in F if f.meta.get("name_written") is True)
    name_edits += sum(int(f.meta.get("filled", 0)) for f in F if f.code == "DATE_FILLED")  # 날짜 줄 기입도 의도한 문구 변경
    F.extend(check_hwpx_structure(cur, baseline_form=structure_baseline, allowed_names=inp.allowed_names,
                                  expected_phrase_edits=name_edits))
    res.named_pdf_blocked = should_block_submission_named_pdf(F)

    # F6 신청서 PDF
    app_pdf = out / "10_application.pdf"
    conv = pre_conv if pre_conv is not None else convert_hwpx_to_pdf(cur, app_pdf, converter=inp.converter)
    F.extend(conv.findings)
    real_env: dict[str, Any] = {"hancom_com_real": conv.real_com, "convert_attempts": conv.attempts}
    if conv.ok and conv.pdf is not None:  # 본문이 엉뚱한 쪽으로 밀리는 사고(문서 순서 ≠ 배치 순서) 검출
        base_pair = (base_pdf, inp.baseline_form) if (inp.layout_guard and base_pdf is not None and inp.baseline_form) else None
        F.extend(check_reading_order(conv.pdf, cur, baseline=base_pair))

    # F5 첨부 가림(원본 미수정, 사본 생성)
    merge_inputs: list[Path] = [app_pdf] if conv.ok else []
    redaction_ok = True
    att_confirmed: list[set[int] | None] = []  # 첨부별 외부 전송 허용 쪽(0 기반). None=전부 불허
    for i, att in enumerate(inp.attachments, 1):
        att = Path(att)
        if inp.redact_attachments:
            red = out / f"2{i}_{att.stem}_가림.pdf"
            rr = redact_pdf(att, red)
            F.extend(rr.findings)
            if rr.undetected_pages or rr.status not in (Status.PASS, Status.NA):
                redaction_ok = False
            if rr.status in (Status.PASS, Status.NA) or (rr.status is Status.REVIEW and rr.undetected_pages):
                # 가림이 확인된 쪽만 허용한다(미확정 쪽은 undetected_pages). 그 외 REVIEW·FAIL 은 첨부 전체 불허.
                att_confirmed.append(set(range(rr.pages)) - set(rr.undetected_pages))
            else:
                att_confirmed.append(None)
            merge_inputs.append(red)
        else:
            redaction_ok = False  # 가림 확인 없는 첨부는 외부 AI 전송 금지
            att_confirmed.append(None)
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
        # 신청서 쪽은 우리가 만든 문서라 항상 허용, 첨부 쪽은 가림이 확인된 쪽만 허용(쪽 단위).
        confirmed_pages: set[int] = set()
        for entry, ok_pages in zip(real_env.get("manifest", []), [set(range(10**6))] + att_confirmed):
            if ok_pages is None:
                continue
            confirmed_pages.update(entry["start_page"] + k for k in ok_pages
                                   if entry["start_page"] + k <= entry["end_page"])
        vr = run_visual_qa(merged, out / "visual", provider, redaction_confirmed=redaction_ok,
                           cache_dir=out / "visual_cache", manual_findings=manual,
                           confirmed_pages=confirmed_pages)
        F.extend(vr.findings)
        usage = vr.usage
        real_env["visual_provider"] = vr.provider_name
        real_env["visual_pages"] = vr.pages

    report = build_report(F, title=f"{inp.doc_name} 검수 보고서", visual_usage=usage,
                          artifacts=res.artifacts, real_environment=real_env)
    res.report_json, res.report_md = write_report(report, out)
    return res
