"""acceptance_remediation.py — 수용검사 결함별 '다음 행동' 안내(순수 로직).

self_diagnose 가 결함 '개수'만 보여주면 비개발자는 무엇을 해야 할지 모른다
(예: "self_inserted_blocks 2" 는 의미 불명). 이 모듈은 각 검사(check_id)를

  - KIND_AUTO   : 명령 한 줄로 자동 해결 (실행할 command 제공)
  - KIND_HUMAN  : 사람이 실제 값·선택을 입력해야 함 (없는 값 날조 금지)
  - KIND_MANUAL : 한글·워드에서 직접 손봐야 함 (판단 필요, 자동 도구 없음)

중 하나로 분류하고, 비개발자용 행동 한 줄과(자동이면) 실행 명령을 제공한다.

읽기 전용·순수 로직 — 문서를 열거나 수정하지 않는다. usage_acceptance 의
CheckResult 목록(AcceptanceReport.results)을 받아 안내 목록·표시 텍스트를 만든다.
check_id 목록은 usage_acceptance 가 단일 출처다 — 새 검사가 늘면
test_acceptance_remediation 이 '전용 안내 없음'으로 실패해 여기 추가를 강제한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .usage_acceptance import SEV_FAIL

KIND_AUTO = "auto"       # 명령 한 줄로 자동 해결
KIND_HUMAN = "human"     # 사람이 실제 값/선택 입력 (날조 금지)
KIND_MANUAL = "manual"   # 한글/워드에서 직접 수정 (판단 필요)

_KIND_LABEL = {
    KIND_AUTO: "자동으로 해결 (명령 실행)",
    KIND_HUMAN: "사람이 직접 입력 (값을 지어내지 마세요)",
    KIND_MANUAL: "한글/워드에서 직접 수정",
}
_KIND_ICON = {KIND_AUTO: "[자동]", KIND_HUMAN: "[입력]", KIND_MANUAL: "[수동]"}
_KIND_ORDER = (KIND_AUTO, KIND_HUMAN, KIND_MANUAL)

# 콘솔 '제출까지 남은 일' 블록에 결함당 몇 개의 구체 항목을 보일지(파일 체크리스트는
# 전부 보인다). 화면이 길어지지 않게 요약 표시용으로만 제한한다.
_MAX_ITEMS_IN_TEXT = 3

# 명령 템플릿의 문서 경로 자리표시 — build 시 실제 경로로 치환한다.
DOC_TOKEN = "{doc}"


@dataclass(frozen=True)
class Remedy:
    """한 검사의 해결 지침. command 는 KIND_AUTO 일 때만 채워진다(경로 {doc} 포함)."""

    kind: str
    action: str
    command: str = ""


_REMEDIES: dict[str, Remedy] = {
    # --- FAIL (제출 차단) ---
    "unresolved_markers": Remedy(
        KIND_HUMAN,
        "[확인필요]/[작성 필요]로 표시된 칸에 실제 값(매출·인원·일자 등)을 직접 "
        "입력하세요. 값이 없으면 제출 전 반드시 채워야 하며, 없는 값을 지어내면 안 됩니다.",
    ),
    "self_inserted_blocks": Remedy(
        KIND_AUTO,
        "NotebookLM 등 작업용 안내블록이 남아 있습니다. 아래 명령으로 자동 제거하세요.",
        f'python strip_notebooklm.py "{DOC_TOKEN}"',
    ),
    "template_placeholders": Remedy(
        KIND_AUTO,
        "양식 안내문구·자리표시는 아래 명령의 후처리로 지워집니다. 단 OOO·0000 같은 "
        "값 자리표시는 실제 값으로 사람이 바꿔야 합니다(날조 금지).",
        f'python auto_write_autopilot.py "{DOC_TOKEN}"',
    ),
    "unchecked_choices": Remedy(
        KIND_HUMAN,
        "선택란(□)에서 해당하는 항목을 ■로 체크하세요. 어느 것이 맞는지는 사람이 "
        "판단해야 합니다. (완성본이 있으면 cross_form_fill.py 로 자동 체크도 가능)",
    ),
    "empty_label_fields": Remedy(
        KIND_HUMAN,
        "표의 라벨(명칭·기업명·대표자명 등) 옆 빈 칸에 실제 값을 입력하세요.",
    ),
    "masking_violation": Remedy(
        KIND_MANUAL,
        "블라인드 심사인데 실명이 남아 있습니다. 해당 이름을 ○○○로 가린 뒤 "
        "--blind-review 로 다시 진단하세요.",
    ),
    "residual_colored_runs": Remedy(
        KIND_AUTO,
        "검정이 아닌 색 글씨(파란 안내문구 등)가 남아 있습니다. 아래 명령으로 "
        "검정 통일이 자동 적용됩니다.",
        f'python auto_write_autopilot.py "{DOC_TOKEN}"',
    ),
    "font_name_mixing": Remedy(
        KIND_AUTO,
        "여러 폰트가 섞여 있습니다. 아래 명령의 서식 정규화로 폰트를 통일하세요. "
        "특정 폰트가 공고 지정이면 한글에서 확인하세요.",
        f'python document_quality_orchestrator.py "{DOC_TOKEN}"',
    ),
    # --- WARN (경고 — 제출 차단 아님, strict_acceptance 시 fail 승격) ---
    "font_size_spread": Remedy(
        KIND_AUTO,
        "글자 크기가 들쭉날쭉합니다. 아래 명령으로 크기를 통일하세요(경고).",
        f'python document_quality_orchestrator.py "{DOC_TOKEN}"',
    ),
    "empty_table_rows": Remedy(
        KIND_MANUAL,
        "완전히 빈 표 행이 있습니다. 값을 채우거나 불필요하면 행을 삭제하세요(경고).",
    ),
    "recruit_date_conflict": Remedy(
        KIND_HUMAN,
        "일정·채용 날짜 표기가 서로 맞지 않습니다. 올바른 날짜로 통일하세요(경고).",
    ),
    "paren_choices": Remedy(
        KIND_HUMAN,
        "괄호형 선택란 ( )이 비어 있습니다. 해당하면 (V)로 표시하세요(경고).",
    ),
    "empty_label_fields_ext": Remedy(
        KIND_HUMAN,
        "라벨(사업자등록번호·연락처 등) 옆 칸이 비어 있을 수 있습니다. 값을 확인해 "
        "채우세요(경고 — 오탐일 수 있음).",
    ),
    "empty_image_slots": Remedy(
        KIND_MANUAL,
        "그림/사진 칸이 비어 있습니다. NotebookLM 프롬프트로 이미지를 만들어 넣으세요"
        "(python -m auto_write.submit 가 프롬프트를 삽입, 경고).",
    ),
    "page_overflow": Remedy(
        KIND_MANUAL,
        "분량이 제한을 넘을 수 있습니다. 핵심만 남기고 줄이세요(경고 — 근사 측정).",
    ),
    "unverified_claims": Remedy(
        KIND_HUMAN,
        "근거 없는 협업·실적 단정이 의심됩니다. 출처·근거를 덧붙이거나 표현을 "
        "완화하세요(경고).",
    ),
}

# 등록되지 않은 check_id 를 위한 안전 기본값(검사가 새로 생겼는데 안내 미등록일 때).
_DEFAULT = Remedy(KIND_MANUAL, "한글/워드에서 직접 확인·수정하세요.")


def remedy_for(check_id: str) -> Remedy:
    """check_id 에 맞는 해결 지침(없으면 안전 기본값 _DEFAULT)."""
    return _REMEDIES.get(check_id, _DEFAULT)


def build_remediation(results, doc_name: str) -> list[dict]:
    """통과하지 못한 검사만 골라 안내 목록을 만든다.

    - 통과(passed)한 검사는 제외 — 남은 일만 보여준다.
    - fail 먼저, 그 다음 warn (같은 심각도 안에서는 원래 검사 순서 유지 — stable sort).
    - KIND_AUTO 의 command 는 {doc} 를 doc_name 으로 치환해 바로 실행 가능하게 한다.
    - ``items`` 에 그 문서의 실제 결함 위치(검사가 캡처한 samples)를 담는다 — 안내가
      '명칭·기업명 등' 일반 예시가 아니라 "이 문서의 '대표자명' 옆 칸이 비었다" 처럼
      구체적이 되게 한다. 사람도 기계(autopilot·에이전트)도 바로 소비할 수 있다.
    """
    items: list[dict] = []
    for r in results:
        if r.passed:
            continue
        rem = remedy_for(r.check_id)
        command = rem.command.replace(DOC_TOKEN, doc_name) if rem.command else ""
        items.append({
            "check_id": r.check_id,
            "label": r.label,
            "severity": r.severity,
            "defects": r.defects,
            "kind": rem.kind,
            "action": rem.action,
            "command": command,
            "items": list(getattr(r, "samples", []) or []),
        })
    items.sort(key=lambda d: 0 if d["severity"] == SEV_FAIL else 1)
    return items


def remediation_summary(items: list[dict]) -> dict:
    """남은 일을 종류별로 집계한다 — "제출까지 얼마나 남았나"를 한눈에.

    - auto_commands : 실행해야 할 서로 다른 자동 명령 수(복붙 실행 횟수).
    - human_fields  : 사람이 직접 채워야 할 칸/항목 수(값 날조 금지 대상).
    - manual_items  : 한글/워드에서 판단해 손봐야 할 항목 수.
    - blocking_defects : 제출을 막는 fail 결함 총수(warn 제외).
    - remaining_checks : 통과하지 못한 검사 수.
    """
    return {
        "auto_commands": len(unique_commands(items)),
        "human_fields": sum(it["defects"] for it in items if it["kind"] == KIND_HUMAN),
        "manual_items": sum(it["defects"] for it in items if it["kind"] == KIND_MANUAL),
        "blocking_defects": sum(it["defects"] for it in items if it["severity"] == SEV_FAIL),
        "remaining_checks": len(items),
    }


def summary_line(summary: dict) -> str:
    """remediation_summary 를 사람이 읽는 한 줄 진행도로 만든다."""
    if not summary.get("remaining_checks"):
        return "제출까지 남은 일 요약: 없음 — 바로 제출 가능"
    parts: list[str] = []
    if summary.get("auto_commands"):
        parts.append(f"자동 명령 {summary['auto_commands']}개 실행")
    if summary.get("human_fields"):
        parts.append(f"사람이 채울 칸 {summary['human_fields']}개")
    if summary.get("manual_items"):
        parts.append(f"한글/워드 수동 확인 {summary['manual_items']}건")
    body = " · ".join(parts) if parts else f"확인할 항목 {summary['remaining_checks']}건"
    return "제출까지 남은 일 요약: " + body


def unique_commands(items: list[dict]) -> list[str]:
    """안내 목록에서 실행 명령을 첫 등장 순서로 중복 없이 모은다(복붙용)."""
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        cmd = it.get("command")
        if cmd and cmd not in seen:
            seen.add(cmd)
            out.append(cmd)
    return out


def format_remediation_text(items: list[dict]) -> list[str]:
    """사람이 읽는 '제출까지 남은 일' 블록을 줄 리스트로 만든다(빈 목록이면 완료 안내)."""
    if not items:
        return ["제출까지 남은 일: 없음 — 바로 제출 가능"]

    lines = ["--- 제출까지 남은 일 (결함별 다음 행동) ---", summary_line(remediation_summary(items))]
    for kind in _KIND_ORDER:
        group = [it for it in items if it["kind"] == kind]
        if not group:
            continue
        lines.append(f"{_KIND_ICON[kind]} {_KIND_LABEL[kind]}:")
        for it in group:
            sev = "" if it["severity"] == SEV_FAIL else " (경고)"
            lines.append(f"  · {it['label']}({it['defects']}){sev}: {it['action']}")
            # 이 문서의 실제 결함 위치를 몇 개 보여준다(전체는 --checklist 파일에).
            concrete = it.get("items") or []
            for s in concrete[:_MAX_ITEMS_IN_TEXT]:
                lines.append(f"      - {s}")
            if len(concrete) > _MAX_ITEMS_IN_TEXT:
                lines.append(f"      - … 외 {len(concrete) - _MAX_ITEMS_IN_TEXT}개 (전체는 --checklist 참조)")

    cmds = unique_commands(items)
    if cmds:
        lines.append("지금 실행하면 자동 해결되는 명령:")
        for c in cmds:
            lines.append(f"  $ {c}")
    return lines


def build_checklist_markdown(items: list[dict], doc_name: str, submittable: bool) -> str:
    """제출 준비 punch-list 를 마크다운 체크박스 문서로 만든다.

    사용자가 파일로 열어 하나씩 지워가며(- [ ] → - [x]) 제출 준비를 완성하도록.
    콘솔 요약과 달리 결함의 구체 항목(어느 칸이 비었는지)을 전부 나열한다.
    진단은 읽기 전용이므로 이 파일은 원본과 무관한 새 산출물이다(원본 미수정).
    """
    lines = [f"# 제출 준비 체크리스트 — {doc_name}", ""]
    lines.append("> 자가진단(self_diagnose) 결과입니다. 아래 항목을 하나씩 처리하며 제출 준비를 완성하세요.")
    lines.append("> 이 진단은 **읽기 전용**이라 원본 문서를 수정하지 않았습니다. "
                 "**없는 값을 지어내지 마세요** — 값이 없으면 빈칸으로 둡니다(날조 0).")
    lines.append("")

    if not items:
        lines.append("## ✅ 제출 준비 완료 — 채워야 할 것이 없습니다. 바로 제출하세요.")
        lines.append("")
        return "\n".join(lines)

    summary = remediation_summary(items)
    lines.append(f"**현재 판정: {'제출 가능' if submittable else '제출불가(DRAFT)'}**")
    lines.append("")
    lines.append(summary_line(summary))
    lines.append("")

    for kind in _KIND_ORDER:
        group = [it for it in items if it["kind"] == kind]
        if not group:
            continue
        lines.append(f"## {_KIND_ICON[kind]} {_KIND_LABEL[kind]}")
        lines.append("")
        for it in group:
            sev = "" if it["severity"] == SEV_FAIL else " (경고)"
            lines.append(f"- [ ] **{it['label']}**({it['defects']}){sev} — {it['action']}")
            for s in (it.get("items") or []):
                lines.append(f"  - {s}")
            if it.get("command"):
                lines.append(f"  - 실행: `{it['command']}`")
        lines.append("")

    cmds = unique_commands(items)
    if cmds:
        lines.append("---")
        lines.append("")
        lines.append("### 지금 실행하면 자동 해결되는 명령 (복사해서 실행)")
        lines.append("")
        lines.append("```powershell")
        lines.extend(cmds)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)
