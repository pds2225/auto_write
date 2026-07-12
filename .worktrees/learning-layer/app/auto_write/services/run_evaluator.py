"""run_evaluator.py — 실행 1건의 평가·수용검사 결과를 학습 레코드(run_record)로 통합한다.

읽기 전용(문서를 수정하지 않는다). 기존 usage_acceptance.run_acceptance /
acceptance_remediation.remedy_for 를 재사용할 뿐 새 판정 로직을 만들지 않는다.

§9 F2/F3 (필수):
- .docx 만 run_acceptance 를 호출한다. .hwpx/.hwp 는 절대 호출하지 않는다
  (변환 없이 직접 보는 hwpx_acceptance 가 있지만 그 결과의 check_id 체계가
  달라 이 모듈이 임의로 섞으면 오분류가 된다 — Phase 1.5 로 분리).
- .hwpx/.hwp 에 acceptance 가 주어지지 않으면 verdict="미검사"(검사불능과 구분).
  주어지면 원본 dict 를 그대로 보존만 한다(결함 분류는 CLI 가 하지 않는다).

§9 F4 (필수): 점수는 관용적 flat 키 스캔이 아니라 정확한 중첩 경로로만 추출한다.
없으면 None(0 아님 — 날조 금지).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .acceptance_remediation import KIND_HUMAN, remedy_for
from .usage_acceptance import AcceptanceConfig, AcceptanceReport, run_acceptance

# §9 M2: Windows py-3.11 에는 tzdata 가 없을 수 있어 zoneinfo("Asia/Seoul") 는
# 크래시 위험이 있다 — 고정 오프셋(KST=UTC+9)만 쓴다(models.py 의 timezone.utc 선례와 동일).
_KST = timezone(timedelta(hours=9))

_TEMPLATE_EXT_MAP = {".docx": "docx", ".hwpx": "hwpx", ".hwp": "hwp"}
_MAX_NEEDS_INPUT = 20


def _new_run_id() -> str:
    return datetime.now(_KST).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:4]


def _extract_quality_score(quality_report: dict | None) -> float | int | None:
    """document_quality_orchestrator 산출(HarnessResult.as_dict()) → score.total."""
    if not isinstance(quality_report, dict):
        return None
    try:
        v = quality_report["score"]["total"]
    except (KeyError, TypeError):
        return None
    return v if isinstance(v, (int, float)) else None


def _extract_eval_score(eval_report: dict | None) -> tuple[float | int | None, float | int | None]:
    """evaluation_service.to_report_dict / EvalLoopReport 산출 → (final_score, final_max)."""
    if not isinstance(eval_report, dict):
        return None, None
    v = eval_report.get("final_score")
    vmax = eval_report.get("final_max")
    if isinstance(v, (int, float)):
        return v, (vmax if isinstance(vmax, (int, float)) else None)
    # 폴백: 표준 to_report_dict 형태가 아니면 마지막 iteration 의 total_score 를 본다.
    try:
        last = eval_report["iterations"][-1]
        v = last.get("total_score")
        vmax = last.get("max_total")
    except (KeyError, IndexError, TypeError):
        return None, None
    if isinstance(v, (int, float)):
        return v, (vmax if isinstance(vmax, (int, float)) else None)
    return None, None


def _extract_from_submission(
    submission_report: dict | None,
) -> tuple[float | int | None, float | int | None, float | int | None]:
    """auto_write.submit / SubmissionPipeline.run 산출 dict → (eval_score, eval_max, quality_score)."""
    if not isinstance(submission_report, dict):
        return None, None, None
    eval_score = eval_max = None
    eval_block = submission_report.get("eval")
    if isinstance(eval_block, dict):
        v = eval_block.get("final_score")
        vmax = eval_block.get("final_max")
        eval_score = v if isinstance(v, (int, float)) else None
        eval_max = vmax if isinstance(vmax, (int, float)) else None
    quality_score = None
    quality_block = submission_report.get("quality")
    if isinstance(quality_block, dict):
        try:
            v = quality_block["score"]["total"]
            quality_score = v if isinstance(v, (int, float)) else None
        except (KeyError, TypeError):
            quality_score = None
    return eval_score, eval_max, quality_score


def _needs_input_from_acceptance_dict(acceptance_dict: dict) -> list[str]:
    """acceptance_remediation 을 단일 출처로 재사용해 사람이 입력해야 할 항목만 모은다.

    kind==human(값을 지어낼 수 없어 사람이 직접 입력해야 하는 결함)만 담는다 —
    auto/manual 은 needs_input 이 아니다(자동 명령이 있거나 한글에서 판단할 일).
    """
    out: list[str] = []
    for c in acceptance_dict.get("checks", []):
        if c.get("passed"):
            continue
        rem = remedy_for(c.get("check_id", ""))
        if rem.kind != KIND_HUMAN:
            continue
        for s in c.get("samples") or []:
            if len(out) >= _MAX_NEEDS_INPUT:
                return out
            out.append(s)
    return out


def build_run_record(
    final_file: str | Path,
    *,
    project_id: str = "",
    program_name: str = "",
    run_id: str | None = None,
    acceptance: AcceptanceReport | dict | None = None,
    acceptance_config: AcceptanceConfig | None = None,
    eval_report: dict | None = None,
    quality_report: dict | None = None,
    submission_report: dict | None = None,
) -> dict[str, Any]:
    """실행 1건의 학습 레코드(runs.jsonl 1행)를 만든다. 읽기 전용."""
    path = Path(final_file)
    ext = path.suffix.lower()
    template_type = _TEMPLATE_EXT_MAP.get(ext, ext.lstrip("."))
    is_docx = ext == ".docx"

    eval_score, eval_max = _extract_eval_score(eval_report)
    quality_score = _extract_quality_score(quality_report)
    if submission_report:
        sub_eval, sub_eval_max, sub_quality = _extract_from_submission(submission_report)
        if eval_score is None:
            eval_score = sub_eval
        if eval_max is None:
            eval_max = sub_eval_max
        if quality_score is None:
            quality_score = sub_quality

    acceptance_dict: dict[str, Any] | None = None
    acceptance_error: str | None = None

    if isinstance(acceptance, AcceptanceReport):
        acceptance_dict = acceptance.as_dict()
    elif isinstance(acceptance, dict):
        acceptance_dict = acceptance
    elif is_docx:
        # §9 F3: .docx 만 자체적으로 run_acceptance 를 시도한다(호출자가 이미
        # 시도해 실패했다면 acceptance=None 으로 넘어와 여기서 같은 예외가
        # 재현될 수 있다 — 읽기 전용·결정론이라 부작용 없이 안전하다).
        try:
            report = run_acceptance(path, acceptance_config)
            acceptance_dict = report.as_dict()
        except Exception as exc:  # noqa: BLE001 — 검사기 자체 실패를 판정 불가로 흡수
            acceptance_error = f"{type(exc).__name__}: {exc}"
    # .hwpx/.hwp 이고 acceptance 미제공 → acceptance_dict=None(미검사), run_acceptance 미호출.

    needs_input: list[str] = []
    if is_docx and acceptance_dict is not None:
        needs_input = _needs_input_from_acceptance_dict(acceptance_dict)

    if acceptance_error:
        verdict = "검사불능"
    elif acceptance_dict is None:
        verdict = "미검사"
    elif acceptance_dict.get("submittable"):
        verdict = "제출가능"
    else:
        verdict = "제출불가"

    scores = {
        "eval_score": eval_score,
        "eval_max": eval_max,
        "quality_score": quality_score,
        "acceptance_fail": acceptance_dict.get("fail_defects") if acceptance_dict else None,
        "acceptance_warn": acceptance_dict.get("warn_defects") if acceptance_dict else None,
    }

    record: dict[str, Any] = {
        "run_id": run_id or _new_run_id(),
        "project_id": project_id,
        "program_name": program_name,
        "template_type": template_type,
        "final_file": str(path),
        "scores": scores,
        "verdict": verdict,
        "needs_input": needs_input,
        "created_at": datetime.now(_KST).isoformat(),
    }
    if acceptance_error:
        record["acceptance_error"] = acceptance_error
    return record
