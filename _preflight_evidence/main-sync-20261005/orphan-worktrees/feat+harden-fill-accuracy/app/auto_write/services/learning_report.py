"""learning_report.py — 실행 1건의 학습 결과를 사람이 읽는 리포트(md)로 만든다.

읽기 전용 입력(run_record/classified/selfdev_candidates) → 새 파일 1개만 만든다.
원본 문서를 절대 덮어쓰지 않는다 — self_diagnose 의 ``--checklist`` same-path
가드와 같은 방식으로, 저장하려는 폴더가 원본 문서 경로와 겹치면 거부한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_REPORT_FILENAME = "learning_report.md"


def _fmt_score(v: Any) -> str:
    return "(미계산)" if v is None else str(v)


def build_learning_report(
    run_record: dict[str, Any],
    classified: list[dict[str, Any]],
    playbook_updates: list[dict[str, Any]] | None = None,
    selfdev_candidates: list[dict[str, Any]] | None = None,
) -> str:
    playbook_updates = playbook_updates or []
    selfdev_candidates = selfdev_candidates or []

    lines: list[str] = []
    lines.append(f"# 자가학습 리포트 — {run_record.get('run_id', '(run_id 없음)')}")
    lines.append("")

    lines.append("## 실행 요약")
    lines.append(f"- 대상 파일: {run_record.get('final_file', '')}")
    lines.append(f"- 프로젝트: {run_record.get('project_id', '') or '(미지정)'}")
    lines.append(f"- 공고: {run_record.get('program_name', '') or '(미지정)'}")
    lines.append(f"- 양식 유형: {run_record.get('template_type', '')}")
    lines.append(f"- 판정: {run_record.get('verdict', '')}")
    if run_record.get("acceptance_error"):
        lines.append(f"- 검사 오류: {run_record['acceptance_error']}")
    lines.append(f"- 생성 시각: {run_record.get('created_at', '')}")
    lines.append("")

    lines.append("## 평가 결과")
    scores = run_record.get("scores") or {}
    if scores:
        lines.append(f"- 평가 점수(eval): {_fmt_score(scores.get('eval_score'))}"
                     f" / {_fmt_score(scores.get('eval_max'))}")
        lines.append(f"- 품질 점수(quality): {_fmt_score(scores.get('quality_score'))}")
        lines.append(f"- 수용검사 fail: {_fmt_score(scores.get('acceptance_fail'))}"
                     f" · warn: {_fmt_score(scores.get('acceptance_warn'))}")
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## 결함 분류")
    if classified:
        lines.append("| check_id | 심각도 | 개수 | 분류 | 다음 행동 |")
        lines.append("|---|---|---|---|---|")
        for c in classified:
            action = (c.get("next_action", "") or "").replace("\n", " ").replace("|", "/")
            lines.append(
                f"| {c.get('check_id', '')} | {c.get('severity', '')} | {c.get('defects', 0)} "
                f"| {c.get('category', '')} | {action} |"
            )
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## 자동 수정 대상 (auto_fix)")
    auto_items = [c for c in classified if c.get("category") == "auto_fix"]
    if auto_items:
        for c in auto_items:
            hint = c.get("command") or c.get("next_action", "")
            lines.append(f"- {c.get('label', c.get('check_id', ''))}: {hint}")
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## 사람 입력 필요 (human_input)")
    human_items = [c for c in classified if c.get("category") == "human_input"]
    if human_items:
        for c in human_items:
            lines.append(f"- {c.get('label', c.get('check_id', ''))}: {c.get('next_action', '')}")
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## 한글/워드 수동 확인 (manual_review)")
    manual_items = [c for c in classified if c.get("category") == "manual_review"]
    if manual_items:
        for c in manual_items:
            lines.append(f"- {c.get('label', c.get('check_id', ''))}: {c.get('next_action', '')}")
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## 프롬프트 규칙 후보 (prompt_rule)")
    prompt_items = [c for c in selfdev_candidates if c.get("type") == "prompt_rule"]
    if prompt_items:
        for c in prompt_items:
            lines.append(f"- {c.get('reason', '')}: {c.get('suggested_action', '')}")
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## 양식 매핑 후보 (field_mapping)")
    lines.append("없음 — 1차 미구현(§9 F5, 3차에서 cross_form_autofill 과 함께 추가 예정)")
    lines.append("")

    lines.append("## 코드 개선 후보 (code_improvement)")
    code_items = [c for c in selfdev_candidates if c.get("type") == "code_improvement"]
    if code_items:
        for c in code_items:
            flag = "" if c.get("requires_code_change") else " (코드 수정 아님)"
            lines.append(f"- {c.get('reason', '')}{flag}: {c.get('suggested_action', '')}")
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## Playbook 갱신")
    if playbook_updates:
        for p in playbook_updates:
            lines.append(f"- {p}")
    else:
        lines.append("없음")
    lines.append("")

    lines.append("## 다음 실행 반영 규칙")
    lines.append(
        "- 이 리포트는 참고용입니다. **코드는 자동으로 수정되지 않습니다** — "
        "code_improvement 후보는 사람이 검토한 뒤 `/auto-write-selfdev` 로 반영하세요."
    )
    lines.append(
        "- human_input 항목은 값이 자동으로 채워지지 않습니다(날조 금지) — "
        "실제 값을 직접 입력한 뒤 다시 실행하세요."
    )
    lines.append("")

    return "\n".join(lines)


def write_learning_report(
    out_dir: str | Path,
    run_record: dict[str, Any],
    classified: list[dict[str, Any]],
    playbook_updates: list[dict[str, Any]] | None = None,
    selfdev_candidates: list[dict[str, Any]] | None = None,
) -> Path:
    """learning_report.md 를 out_dir 밑에 새로 만든다(원본 same-path 저장 거부)."""
    out_dir_path = Path(out_dir)
    out_path = out_dir_path / _REPORT_FILENAME

    final_file = run_record.get("final_file")
    if final_file:
        final_path = Path(final_file)
        try:
            same = out_path.resolve() == final_path.resolve() or out_dir_path.resolve() == final_path.resolve()
        except OSError:
            same = str(out_path) == str(final_file) or str(out_dir_path) == str(final_file)
        if same:
            raise ValueError(f"학습 리포트 저장 경로가 원본 문서와 같습니다(원본 보호): {out_path}")

    out_dir_path.mkdir(parents=True, exist_ok=True)
    content = build_learning_report(run_record, classified, playbook_updates, selfdev_candidates)
    out_path.write_text(content, encoding="utf-8")
    return out_path
