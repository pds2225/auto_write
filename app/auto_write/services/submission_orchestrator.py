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
from .usage_acceptance import SEV_FAIL, force_draft_name, run_acceptance


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
    ) -> dict[str, Any]:
        report: dict[str, Any] = {"project_id": project_id, "steps": [], "needs_input": []}
        results_root = Path(self.settings.results_root)
        results_root.mkdir(parents=True, exist_ok=True)

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
        fill_report = SubmittableFiller(plan).finalize(output_docx, submit_path)
        report["submit_docx"] = str(submit_path)
        report["finalize"] = {k: v for k, v in fill_report.items() if k != "residual_remaining"}
        report["residual_remaining"] = len(fill_report.get("residual_remaining", []))
        report["steps"].append("finalize")

        final_docx = submit_path

        # 4. 서식 품질 게이트(내부 백업 수행)
        try:
            quality = DocumentQualityOrchestrator(
                results_root, openai_service=getattr(self.project_service, "openai_service", None)
            )
            quality_out = results_root / f"제출초안_{project_id}_품질.docx"
            q_result = quality.run(submit_path, quality_out, write_report=False)
            report["quality_docx"] = str(quality_out)
            try:
                report["quality"] = q_result.to_dict()
            except Exception:
                report["quality"] = {}
            report["steps"].append("quality")
            final_docx = quality_out
        except Exception as exc:
            report["quality_error"] = f"{type(exc).__name__}: {exc}"

        # 5. 이미지 최후 삽입(모든 텍스트 처리 후)
        if enable_images:
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

        # 6. NotebookLM 슬라이드 프롬프트 삽입(모든 텍스트/이미지 처리 후 최종본에).
        #    공개 이미지 API 가 없는 NotebookLM 은 '수동 슬라이드 생성용 프롬프트'를
        #    그림 위치(표 뒤/본문 앵커)에 넣어, 사용자가 붙여넣어 슬라이드를 만들게 한다.
        if enable_notebooklm:
            try:
                from .image_apply import apply_images

                nlm_out = results_root / f"제출초안_{project_id}_노트북LM.docx"
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

        # 7. 실사용 수용검사 게이트(R7/R8) — fail 결함이 있으면 '제출' 이름으로
        #    내보내지 않고 파일명에 _DRAFT 를 강제한다(autopilot 4단계와 동일 정책).
        #    NotebookLM 프롬프트가 삽입된 출력은 작업용 중간본이라 DRAFT 가 정상이다.
        #    게이트 자신이 죽어도 통과로 취급하지 않는다(fail-closed): 판정 불가 = 제출 금지.
        if acceptance_gate:
            acc = None
            try:
                acc = run_acceptance(str(final_docx))
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
                old = Path(final_docx)
                new_path, mark_error = force_draft_name(old)
                if mark_error:
                    # rename 실패(파일 잠금 등)도 조용히 넘기지 않는다 — 보고와 실제
                    # 파일명이 어긋나는 것을 사용자에게 명시한다.
                    report["draft_mark_error"] = mark_error
                    report["needs_input"].append(
                        f"_DRAFT 마킹 실패({mark_error}) — 파일명이 제출 이름 그대로이니 "
                        f"직접 변경 전 제출 금지: {old.name}"
                    )
                else:
                    if new_path != old:
                        # 같은 파일을 가리키던 리포트 경로도 함께 갱신(댕글링 방지).
                        for key in ("submit_docx", "quality_docx"):
                            if report.get(key) == str(old):
                                report[key] = str(new_path)
                    final_docx = new_path
                    if acc is not None:
                        report["acceptance"]["draft_marked"] = True

        report["final_docx"] = str(final_docx)
        log_line(f"[Submission] project={project_id} final={Path(final_docx).name} steps={report['steps']}")
        return report
