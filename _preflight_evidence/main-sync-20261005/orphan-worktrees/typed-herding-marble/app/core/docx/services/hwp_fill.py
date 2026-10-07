"""hwp_fill.py — HWP 양식 표 채우기 + 본문 보강 end-to-end (Stream 3).

흐름:
    HWP/HWPX --(convert)--> DOCX
              --(SubmittableFiller)--> identity/overview/fill_plan 표 채움
              --(run_bizplan_autopilot, 선택)--> AI 본문/PSST 보강
              --(convert)--> HWP

설계 원칙(ralplan 합의)
----------------------
- **기존 자산 재사용**: convert(hwp_docx_convert)·SubmittableFiller·
  run_bizplan_autopilot 을 그대로 조합한다. 새 변환·채움 로직은 만들지 않는다.
- **표 자동채움 = 양식형 표 한정**: SubmittableFiller 의 identity/overview(라벨
  매칭) + 외부 fill_plan.json(row_rewrites/replacements 등). autopilot/AI 는
  본문·PSST prose 만 채우고 표 빈칸은 못 채운다(과대약속 금지).
- **날조 0**: identity·fill_plan 이 없으면 0칸 채움(no-op)이며 빈칸을 그대로
  둔다. 무출처 수치 [확인필요] 정책은 run_bizplan_autopilot 가 처리한다.
- **원본 미수정**: out==in 이면 ValueError. 중간본은 임시 디렉터리에만.
- **DRAFT 전파(AC7)**: 본문 보강 단계가 제출불가(_DRAFT)면 출력 HWP 도 _DRAFT.
- **COM 종속 정직 보고**: DOCX→HWP 는 한글 COM 대화형 전용이라 미가용/실패 시
  예외 대신 ok=False + DOCX-only 결과 + 안내를 담는다.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .conversion_fidelity import compare_docx_structure
from .hwp_docx_convert import convert, hwp_to_docx
from .submittable_filler import SubmittableFiller

_HWP_EXTS = {".hwp", ".hwpx"}
_DRAFT_TOKENS = ("_DRAFT", "_DRAFT2")


@dataclass
class HwpFillReport:
    input_hwp: str
    output: str = ""                       # 최종 산출 경로(HWP 또는 DOCX-only)
    ok: bool = False
    draft_marked: bool = False
    acceptance_verdict: str = ""
    filled: dict[str, Any] = field(default_factory=dict)   # 채움수 요약
    residual_blanks: list[str] = field(default_factory=list)
    fidelity: Optional[dict[str, Any]] = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_hwp": self.input_hwp,
            "output": self.output,
            "ok": self.ok,
            "draft_marked": self.draft_marked,
            "acceptance_verdict": self.acceptance_verdict,
            "filled": self.filled,
            "residual_blanks": self.residual_blanks,
            "fidelity": self.fidelity,
            "notes": self.notes,
        }


def _load_json(fill_plan_dir: Optional[str | Path]) -> dict[str, Any]:
    """fill_plan_dir 안의 *.json(특히 fill_plan.json 우선) 을 병합해 반환한다."""
    if not fill_plan_dir:
        return {}
    base = Path(fill_plan_dir)
    if not base.is_dir():
        return {}
    merged: dict[str, Any] = {}
    paths = sorted(base.glob("*.json"))
    # fill_plan.json 을 가장 마지막에 병합(최우선)하도록 정렬한다.
    paths.sort(key=lambda p: p.name.lower() == "fill_plan.json")
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            merged.update(data)
    return merged


def _is_draft_path(path: str | Path) -> bool:
    return Path(path).stem.endswith(_DRAFT_TOKENS)


def _force_draft(out_hwp: Path) -> Path:
    if out_hwp.stem.endswith(_DRAFT_TOKENS):
        return out_hwp
    return out_hwp.with_name(f"{out_hwp.stem}_DRAFT{out_hwp.suffix}")


def fill_hwp(
    in_hwp: str | Path,
    out_hwp: str | Path,
    *,
    identity: Optional[dict[str, Any]] = None,
    fill_plan_dir: Optional[str | Path] = None,
    brief: str = "",
    use_ai: bool = True,
) -> HwpFillReport:
    """HWP/HWPX 양식의 빈 표를 채우고(+본문 보강) HWP 로 되돌린다.

    Args:
        in_hwp: 입력 HWP/HWPX(원본, 절대 미수정).
        out_hwp: 출력 HWP 경로(.hwp/.hwpx). out==in 이면 ValueError.
        identity: 일반현황 표 라벨→값(예: {"기업명": "테스트(주)"}).
        fill_plan_dir: fill_plan.json 등 추가 채움 계획 폴더(선택).
        brief: 사업 브리프. use_ai 또는 brief 있으면 본문 보강.
        use_ai: AI 본문 작성 사용 여부(키 없으면 자동 비활성).

    Returns:
        HwpFillReport — 채움수·잔존빈칸·일치도·DRAFT 판정 통합.
    """
    src = Path(in_hwp)
    dst = Path(out_hwp)
    report = HwpFillReport(input_hwp=str(src), output=str(dst))

    # 1) 안전장치 — 원본 보존
    if src.resolve() == dst.resolve():
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    if not src.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {src}")
    if src.suffix.lower() not in _HWP_EXTS:
        raise ValueError(f"HWP/HWPX 입력만 지원합니다: {src.name}")
    if dst.suffix.lower() not in _HWP_EXTS:
        raise ValueError(f"출력은 .hwp/.hwpx 만 지원합니다: {dst.name}")

    tmp = tempfile.TemporaryDirectory(prefix="hwp_fill_")
    cleanup = True
    try:
        work = Path(tmp.name)

        # 2) HWP → DOCX
        step1 = work / "step1.docx"
        r_in = hwp_to_docx(src, step1, use_com=True)
        report.notes.extend(r_in.notes)
        if not r_in.ok:
            report.notes.append("HWP→DOCX 변환 실패 — 채움/보강을 진행할 수 없습니다.")
            return report

        # 3) 표 채움(build_fill_plan 미사용 — bare HWP 경로엔 profile 없음)
        plan: dict[str, Any] = {
            "identity": dict(identity or {}),
            "overview": {},
            **_load_json(fill_plan_dir),
        }
        step2 = work / "step2.docx"
        filler = SubmittableFiller(plan)
        fill_report = filler.finalize(step1, step2)
        report.filled = {
            "identity": int(fill_report.get("identity_filled", 0)),
            "overview": int(fill_report.get("overview_filled", 0)),
            "rows": int(fill_report.get("rows_rewritten", 0)),
            "replacements": int(fill_report.get("replacements", 0)),
        }
        report.residual_blanks = list(fill_report.get("residual_remaining", []) or [])
        cur = step2

        # 4) 본문 보강(use_ai 또는 brief) — run_bizplan_autopilot
        draft_signal = False
        if use_ai or brief:
            from .bizplan_autopilot import run_bizplan_autopilot

            step3 = work / "step3.docx"
            try:
                bp = run_bizplan_autopilot(
                    str(step2), str(step3),
                    brief=brief, use_ai=use_ai, write_report=False,
                )
                cur = Path(bp.output_docx)   # 엔진이 _DRAFT/경로를 바꿀 수 있음 → 추종
                report.acceptance_verdict = bp.acceptance_verdict
                draft_signal = (
                    bool(bp.draft_marked)
                    or not bp.acceptance_submittable
                    or _is_draft_path(cur)
                )
            except Exception as exc:
                report.notes.append(
                    f"본문 보강(run_bizplan_autopilot) 실패({type(exc).__name__}) — "
                    "표 채움 결과로 진행합니다.")
                cur = step2

        # 5) DRAFT 전파(AC7) + DOCX → HWP
        if draft_signal:
            dst = _force_draft(dst)
            report.output = str(dst)
            report.draft_marked = True
            report.notes.append(
                "본문 보강 결과가 제출불가(_DRAFT) — 출력 HWP 도 _DRAFT 로 명명합니다.")

        r_out = convert(cur, dst)
        report.notes.extend(r_out.notes)

        # 6) COM 부재/실패 — DOCX-only 결과로 보존(예외 전파 금지)
        if not r_out.ok:
            docx_keep = dst.with_suffix(".docx")
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                import shutil

                shutil.copyfile(str(cur), str(docx_keep))
            except Exception as exc:
                report.notes.append(f"DOCX 보존 실패: {exc}")
                return report
            report.ok = False
            report.output = str(docx_keep)
            report.notes.append(
                "DOCX→HWP 한글 COM 대화형 전용 — 이 PC 인터랙티브에서 변환 필요. "
                f"채움 완료된 DOCX: {docx_keep}")
            return report

        report.ok = True
        report.output = str(dst)

        # 7) 자가 일치도(선택, COM 가용 시) — 측정 실패해도 채움 결과는 보존
        try:
            back = work / "fidelity_back.docx"
            r_back = hwp_to_docx(dst, back, use_com=True)
            if r_back.ok:
                fid = compare_docx_structure(cur, back)
                report.fidelity = fid.as_dict()
            else:
                report.notes.append("자가 일치도 측정 생략 — HWP→DOCX 역변환 불가.")
        except Exception as exc:
            report.notes.append(f"자가 일치도 측정 실패(무시): {type(exc).__name__}")

        return report
    except Exception:
        # 디버그를 위해 중간본 보존(임시폴더 정리 안 함) 후 재전파.
        cleanup = False
        report.notes.append(f"중간 산출물 보존(디버그): {tmp.name}")
        raise
    finally:
        if cleanup:
            tmp.cleanup()
        else:
            tmp._finalizer.detach()  # type: ignore[attr-defined]
