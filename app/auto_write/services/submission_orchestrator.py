"""submission_orchestrator.py

template+공고+brief -> '바로 제출 가능한' 사업계획서 자동 생성 end-to-end 파이프라인.
기존 엔진을 순서대로 조합한다(신규 생성 로직 최소):

  generate(텍스트) -> eval loop(공고 채점·취약섹션 재생성) -> finalize(제출 마감)
  -> 서식 quality gate -> 이미지 최후 삽입

이미지를 '최후'에 넣는 이유: finalize/quality 의 텍스트 정리(빈 문단 제거 등)가
먼저 삽입된 이미지를 지울 수 있으므로, 모든 텍스트 처리 후 마지막에 삽입한다.

안전: 원본 양식 절대 미변경. 산출물은 results_root 아래 새 파일. quality gate 가 내부 백업.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils import log_line
from .document_quality_orchestrator import DocumentQualityOrchestrator
from .eval_loop_runner import EvalLoopRunner
from .plan_builder import build_fill_plan
from .submittable_filler import SubmittableFiller
from .usage_acceptance import (
    AcceptanceConfig, SEV_FAIL, backup_existing_output, force_draft_name, run_acceptance,
)


class SubmissionPipeline:
    def __init__(self, project_service: Any, evaluation_service: Any, storage: Any, settings: Any) -> None:
        self.project_service = project_service
        self.evaluation_service = evaluation_service
        self.storage = storage
        self.settings = settings

    def run(
        self,
        project_id: str,
        announcement_text: str = "",
        *,
        target_score: int = 92,
        max_iterations: int = 3,
        enable_images: bool = True,
        enable_notebooklm: bool = True,
        fill_plan_dir: str | Path | None = None,
        acceptance_gate: bool = True,
        blind_review: bool = False,
        required_format: str | None = None,
        submit_clean: bool = False,
        max_pages: int | None = None,
        ai_section_max: int | None = None,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {"project_id": project_id, "steps": [], "needs_input": []}
        results_root = Path(self.settings.results_root)
        results_root.mkdir(parents=True, exist_ok=True)

        def _protect_output(p: Path) -> None:
            # 재실행 보호(PIPE-2): 고정 산출명이 이전 산출물을 무경고 파괴하지 않게 백업
            bak = backup_existing_output(p)
            if bak:
                report.setdefault("overwrite_backups", []).append(bak)

        # 1. 텍스트 생성(이미지는 최후에 별도 삽입하므로 generate 단계는 이미지 끔)
        project_input = self.storage.load_project_input(project_id)
        project_input.project_meta = dict(project_input.project_meta or {})
        project_input.project_meta["disable_images"] = True
        self.storage.save_project_input(project_id, project_input)
        self.project_service.generate(project_id)
        report["steps"].append("generate")

        # 2. 공고 평가 루프(공고문 있을 때만)
        if announcement_text.strip():
            runner = EvalLoopRunner(self.evaluation_service, self.project_service, self.storage)
            loop_report = runner.run(
                project_id,
                announcement_text,
                target_score=target_score,
                max_iterations=max_iterations,
            )
            report["eval"] = self.evaluation_service.to_report_dict(loop_report)
            report["needs_input"] = list(loop_report.needs_input)
            report["eval_passed"] = bool(
                loop_report.final_pass_ratio >= target_score / 100.0 and not loop_report.needs_input
            )
            report["steps"].append("evaluate")

        output_docx = self.storage.project_dir(project_id) / "output" / "output.docx"

        # 3. 제출 마감(finalize)
        profile = self.project_service.load_profile_for_project(project_id)
        project_input = self.storage.load_project_input(project_id)
        plan = build_fill_plan(profile, project_input, external_plan_dir=fill_plan_dir)
        submit_path = results_root / f"제출초안_{project_id}.docx"
        _protect_output(submit_path)
        fill_report = SubmittableFiller(plan).finalize(output_docx, submit_path)
        report["submit_docx"] = str(submit_path)
        report["finalize"] = {k: v for k, v in fill_report.items() if k != "residual_remaining"}
        report["residual_remaining"] = len(fill_report.get("residual_remaining", []))
        report["steps"].append("finalize")

        final_docx = submit_path
        # 이 실행이 만든 '제출 이름' 산출물 목록 — 게이트 fail/판정불가 시 최종본만이
        # 아니라 전부 _DRAFT 마킹한다(중간본이 제출용 이름으로 잔존하는 것 차단).
        artifacts: list[Path] = [submit_path]

        # 4. 서식 품질 게이트(내부 백업 수행)
        try:
            quality = DocumentQualityOrchestrator(
                results_root, openai_service=getattr(self.project_service, "openai_service", None)
            )
            quality_out = results_root / f"제출초안_{project_id}_품질.docx"
            _protect_output(quality_out)
            q_result = quality.run(submit_path, quality_out, write_report=False)
            report["quality_docx"] = str(quality_out)
            # HarnessResult 는 as_dict() 를 노출한다(to_dict 아님). 구버전은 to_dict() 를
            # 호출해 AttributeError → except 로 quality 리포트가 항상 빈값이었음.
            try:
                report["quality"] = q_result.as_dict()
            except Exception:
                report["quality"] = {}
            report["steps"].append("quality")
            final_docx = quality_out
            artifacts.append(quality_out)
        except Exception as exc:
            report["quality_error"] = f"{type(exc).__name__}: {exc}"

        # 5. 이미지 최후 삽입(모든 텍스트 처리 후)
        #    이미지 단계 예외가 비싼 generate/eval 결과 리포트 전체를 날리지 않게
        #    보호한다(PIPE-8) — 실패해도 images_error 만 남기고 수용검사로 진행.
        if enable_images:
            try:
                try:
                    evidence = self.project_service.evidence_service.search(project_input.evidence_requests)
                except Exception:
                    evidence = []
                assets_dir = self.storage.project_dir(project_id) / "generated_assets"
                images = self.project_service.image_service.build_images(
                    profile.image_slots, project_input.answers, evidence, assets_dir
                )
                img_report = self.project_service.render_service.insert_images_into_docx(
                    profile, images, final_docx
                )
                report["images"] = {
                    "generated": len(images),
                    "inserted": int(img_report.get("images_written", 0)),
                    "errors": img_report.get("errors", []),
                }
                report["steps"].append("images")
            except Exception as exc:
                report["images_error"] = f"{type(exc).__name__}: {exc}"

        # 6. NotebookLM 슬라이드 프롬프트 삽입(모든 텍스트/이미지 처리 후 최종본에).
        #    공개 이미지 API 가 없는 NotebookLM 은 '수동 슬라이드 생성용 프롬프트'를
        #    그림 위치(표 뒤/본문 앵커)에 넣어, 사용자가 붙여넣어 슬라이드를 만들게 한다.
        if enable_notebooklm:
            nlm_out = results_root / f"제출초안_{project_id}_노트북LM.docx"
            _protect_output(nlm_out)
            # 호출 '전'에 산출물 목록에 올린다 — apply_images 가 파일 생성 후 죽으면
            # 부분 생성본이 제출 이름의 고아로 남는 것을 막는다(미생성이면 게이트가
            # exists() 로 건너뛴다).
            artifacts.append(nlm_out)
            try:
                from .image_apply import apply_images

                nlm_report = apply_images(
                    str(final_docx),
                    str(nlm_out),
                    openai_service=getattr(self.project_service, "openai_service", None),
                )
                report["notebooklm"] = {
                    "prompts_inserted": nlm_report.prompts_inserted,
                    "anchors_missing": nlm_report.anchors_missing,
                }
                report["steps"].append("notebooklm")
                final_docx = nlm_out
            except Exception as exc:
                report["notebooklm_error"] = f"{type(exc).__name__}: {exc}"
                if nlm_out.exists():
                    # 생성 도중 실패한 부분 생성본은 게이트 결과와 무관하게 제출 이름을
                    # 박탈한다(내용 미완·자가삽입 블록 잔존 가능). 마킹 실패도 알린다.
                    _np, _err = force_draft_name(nlm_out)
                    if _err:
                        report["needs_input"].append(
                            f"노트북LM 부분 생성본 _DRAFT 마킹 실패({_err}) — "
                            f"제출 금지: {nlm_out.name}"
                        )

        # 6.5 (옵션) 제출 정리(--submit-clean, US-6): 프롬프트를 md 로 보존(손실 0)한
        #     뒤 작업용 블록을 제거한다. 산출은 중립명(_정리본) — 최종 이름은 게이트
        #     결과가 결정한다(통과 시에만 _제출용, '_제출용_DRAFT' 모순명 금지).
        if submit_clean:
            try:
                from .image_apply import extract_notebooklm_prompts, strip_notebooklm_blocks

                prompts = extract_notebooklm_prompts(str(final_docx))
                if prompts:
                    md_path = results_root / f"제출초안_{project_id}_슬라이드프롬프트.md"
                    _protect_output(md_path)
                    md_path.write_text("\n\n---\n\n".join(prompts), encoding="utf-8")
                    report["prompt_md"] = str(md_path)
                clean_out = results_root / f"제출초안_{project_id}_정리본.docx"
                _protect_output(clean_out)
                strip_rep = strip_notebooklm_blocks(str(final_docx), str(clean_out))
                report["strip_removed"] = strip_rep.paragraphs_removed
                report["steps"].append("submit_clean")
                final_docx = clean_out
            except Exception as exc:
                report["submit_clean_error"] = f"{type(exc).__name__}: {exc}"

        # 7. 실사용 수용검사 게이트(R7/R8) — fail 결함이 있으면 '제출' 이름으로
        #    내보내지 않고 파일명에 _DRAFT 를 강제한다(autopilot 4단계와 동일 정책).
        #    NotebookLM 프롬프트가 삽입된 출력은 작업용 중간본이라 DRAFT 가 정상이다.
        #    게이트 자신이 죽어도 통과로 취급하지 않는다(fail-closed): 판정 불가 = 제출 금지.
        if acceptance_gate:
            acc = None
            try:
                acc = run_acceptance(str(final_docx), AcceptanceConfig(
                    blind_review=blind_review, max_pages=max_pages, ai_section_max=ai_section_max))
            except Exception as exc:
                report["acceptance_error"] = f"{type(exc).__name__}: {exc}"
                report["needs_input"].append(
                    f"수용검사 실행 실패({type(exc).__name__}) — 판정 불가 상태이므로 제출 금지(_DRAFT 표시)."
                )
            if acc is not None:
                report["acceptance"] = {
                    "submittable": acc.submittable,
                    "verdict": "제출가능" if acc.submittable else "제출불가(DRAFT)",
                    "fail_defects": acc.fail_defects,
                    "failed_checks": [
                        f"{r.label}: {r.detail}"
                        for r in acc.results if r.severity == SEV_FAIL and not r.passed
                    ],
                    "draft_marked": False,
                }
                report["steps"].append("acceptance")
                if not acc.submittable:
                    report["needs_input"].append(
                        f"수용검사 fail {acc.fail_defects}건 — 결함 해결 전 제출 금지(_DRAFT 표시)."
                    )
            if acc is None or not acc.submittable:
                # 최종본만이 아니라 이 실행이 만든 중간 산출물(제출초안_*)에도 _DRAFT 를
                # 전파한다 — fail 실행의 중간본이 '제출' 이름으로 남으면 사용자가 그것을
                # 집어 제출할 수 있다(R9 잔여 #9: 중간본 명명 정책).
                final_old = Path(final_docx)
                # 최종본이 artifacts 에 없을 수 있다(예: --submit-clean 의 _정리본은
                # artifacts 에 등록되지 않음) — 항상 포함시켜 fail 시 최종본이 _DRAFT
                # 마킹에서 누락(제출 이름으로 유출)되지 않게 한다(R7/R9).
                draft_targets = list(artifacts)
                if final_old not in draft_targets:
                    draft_targets.append(final_old)
                for old in draft_targets:
                    if not old.exists():
                        continue
                    new_path, mark_error = force_draft_name(old)
                    if mark_error:
                        # rename 실패(파일 잠금 등)도 조용히 넘기지 않는다 — 보고와 실제
                        # 파일명이 어긋나는 것을 사용자에게 명시한다.
                        if old == final_old:
                            report["draft_mark_error"] = mark_error
                        report["needs_input"].append(
                            f"_DRAFT 마킹 실패({mark_error}) — 파일명이 제출 이름 그대로이니 "
                            f"직접 변경 전 제출 금지: {old.name}"
                        )
                        continue
                    if new_path != old:
                        # 같은 파일을 가리키던 리포트 경로도 함께 갱신(댕글링 방지).
                        for key in ("submit_docx", "quality_docx"):
                            if report.get(key) == str(old):
                                report[key] = str(new_path)
                    if old == final_old:
                        final_docx = new_path
                        if acc is not None:
                            report["acceptance"]["draft_marked"] = True

        # 제출 정리 경로의 최종 명명(US-6) — 게이트 '통과'가 확인된 경우에만
        # 중립명(_정리본)을 '_제출용' 으로 올린다(게이트 결과의 상호배타 단일 결정).
        if submit_clean and acceptance_gate:
            fp_clean = Path(final_docx)
            acc_ok = (bool((report.get("acceptance") or {}).get("submittable"))
                      and not report.get("acceptance_error"))
            # 형식 일치까지 확인된 경우에만 _제출용 승격 — 불일치면 _정리본 을 유지해
            # 직후 7.5 형식 게이트가 _정리본_DRAFT 로 강등하게 한다('_제출용_DRAFT' 모순명
            # 방지, L188 정책: 통과 시에만 _제출용).
            format_ok = (not required_format
                         or fp_clean.suffix.lstrip(".").lower() == required_format.lstrip(".").lower())
            if acc_ok and format_ok and fp_clean.stem.endswith("_정리본"):
                submit_name = fp_clean.with_name(fp_clean.name.replace("_정리본", "_제출용"))
                _protect_output(submit_name)
                fp_clean.replace(submit_name)
                final_docx = submit_name

        # 7.5 산출 형식 게이트(ACC-5) — 요구 형식(hwp 등)과 다르면 제출명 차단.
        #     판정은 이 파이프라인 레벨(최종 확장자)에서만 — run_acceptance 내부가 아님.
        fp = Path(final_docx)
        if required_format and fp.suffix.lstrip(".").lower() != required_format.lstrip(".").lower():
            report["format_mismatch"] = (
                f"요구 산출형식 .{required_format.lstrip('.')} ↔ 실제 {fp.suffix} — "
                f"scripts\\docx2hwp.py(대화형 PowerShell)로 변환 후 제출"
            )
            report["needs_input"].append(report["format_mismatch"])
            if not fp.stem.endswith(("_DRAFT", "_DRAFT2")):
                new_path, mark_error = force_draft_name(fp)
                if mark_error:
                    report["draft_mark_error"] = report.get("draft_mark_error") or mark_error
                else:
                    for key in ("submit_docx", "quality_docx"):
                        if report.get(key) == str(fp):
                            report[key] = str(new_path)
                    final_docx = new_path

        report["final_docx"] = str(final_docx)
        log_line(f"[Submission] project={project_id} final={Path(final_docx).name} steps={report['steps']}")
        return report
