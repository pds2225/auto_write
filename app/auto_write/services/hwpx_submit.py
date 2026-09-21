# -*- coding: utf-8 -*-
"""hwpx_submit — HWPX 채움→수용검사 게이트→_DRAFT 강제까지 한 번에(제출 파이프라인).

B②(게이트 배선) + B③(제출 파이프라인). 기존 자산만 조립한다(재구현 금지):

  1. ``hwpx_fill.fill_hwpx``            — 값 채움(원본미수정·원자적쓰기·날조0 내장)
  2. ``hwpx_acceptance.run_hwpx_acceptance`` — 산출물 결함 검출(유색·안내문구·linesegarray)
  3. ``usage_acceptance.force_draft_name``   — _DRAFT 강제 명명 정책 **단일 출처** 재사용

게이트 정책(fail-closed, R9)
----------------------------
- 게이트 ok       → 출력 이름 그대로(제출가능).
- 게이트 fail     → ``force_draft_name`` 으로 출력을 ``_DRAFT`` 이름으로 rename.
                    제출용 이름의 파일은 남기지 않는다.
- 게이트 **예외**(검사불능) → 판정 불가 = 제출불가. 똑같이 ``_DRAFT`` 강제 + error 기록.
  제출 이름으로 절대 통과시키지 않는다(fail-open 금지).
- rename 실패(파일 잠금 등)도 침묵 금지 — error/draft_reason 에 명시하고 ``final`` 은
  항상 실제 존재하는 경로를 가리킨다(댕글링 금지).

원본(in_hwpx)은 fill_hwpx 의 안전가드(out==in ValueError·읽기전용)로 절대 수정되지 않는다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .hwpx_acceptance import run_hwpx_acceptance
from .hwpx_fill import fill_hwpx
from .hwpx_layout_fix import normalize_colors_in_hwpx
from .hwpx_submission_cleanup import finalize_submission_hwpx
from .usage_acceptance import force_draft_name


@dataclass
class SubmitReport:
    """HWPX 제출 파이프라인 결과 — 경로는 전부 실제 최종 상태와 일치한다.

    - ``output``: 요청한 출력 경로(rename 전 이름).
    - ``final``: 실제 최종 파일 경로(_DRAFT 강제 시 바뀐 이름). 항상 실존 경로.
    - ``ok``: True = 제출가능(게이트 통과 또는 게이트 생략+채움 성공).
    - ``acceptance``: run_hwpx_acceptance 결과 dict. 검사불능이면
      ``{"ok": False, "exception": "..."}`` (CLI exit 3 판별 근거).
    """
    input: str
    output: str = ""
    final: str = ""
    ok: bool = False
    acceptance: dict[str, Any] = field(default_factory=dict)
    filled: dict[str, str] = field(default_factory=dict)
    residual: list[str] = field(default_factory=list)
    draft_marked: bool = False
    draft_reason: str = ""
    error: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "final": self.final,
            "ok": self.ok,
            "acceptance": dict(self.acceptance),
            "filled": dict(self.filled),
            "residual": list(self.residual),
            "draft_marked": self.draft_marked,
            "draft_reason": self.draft_reason,
            "error": self.error,
            "notes": list(self.notes),
        }


def _mark_draft(report: SubmitReport, out: Path, src: Path) -> Path:
    """out 을 _DRAFT 이름으로 강제한다(force_draft_name 단일 출처 재사용).

    rename 실패(파일 잠금 등) 시 침묵하지 않는다 — error 에 명시하고 파일이 실제로
    남아 있는 원래 경로를 반환한다(호출자는 final 을 이 반환값으로 맞춘다).
    """
    new_path, mark_err = force_draft_name(out, avoid=src)
    if mark_err:
        report.draft_marked = False
        msg = f"_DRAFT 마킹 실패(파일 잠금?): {mark_err} — 파일명이 제출용 그대로임"
        report.error = f"{report.error} / {msg}" if report.error else msg
        return out
    report.draft_marked = True
    return new_path


def submit_hwpx(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    *,
    identity: Optional[dict[str, str]] = None,
    replacements: Optional[dict[str, str]] = None,
    acceptance_gate: bool = True,
    normalize_colors: bool = True,
    submission_cleanup: bool = True,
) -> SubmitReport:
    """HWPX 양식을 채우고 수용검사 게이트로 판정해 제출 가능 여부를 확정한다.

    Args:
        in_hwpx: 입력 양식(.hwpx). 절대 수정되지 않는다.
        out_hwpx: 출력 경로(.hwpx). 게이트 fail/검사불능이면 ``_DRAFT`` 로 rename 된다.
        identity: 라벨→값(fill_hwpx 로 전달, 날조0).
        replacements: 직접 치환(선택, 라벨/실값 칸 보호).
        acceptance_gate: False 면 게이트를 생략한다(이름 유지, notes 에 명시).
        normalize_colors: True(기본)면 채움 직후 잔존 예시 유색체를 검정으로 정규화해
            수용검사 colored 결함을 자동 해소한다(채운 값 검정은 fill_hwpx 가 이미 처리).
            ``submission_cleanup=True`` 이면 cleanup 의 force_black 이 동일 역할을 하므로
            별도 normalize 단계는 건너뛴다(중복 방지).
        submission_cleanup: True(기본)면 ``finalize_submission_hwpx`` 로 안내문구 제거·
            유색→검정·linesegarray 제거를 적용한다(원본 out 은 temp 경유 후 교체 —
            out==in 금지 불변 유지). 한글 직접 납품용 전역 lineseg strip 포함.

    Returns:
        SubmitReport — final 은 항상 실제 존재하는 최종 경로.

    Raises:
        FileNotFoundError/ValueError: 입력 오류(파일 없음·out==in·비 hwpx 등,
        fill_hwpx 안전가드 그대로 전파 — CLI 는 exit 1 로 매핑).
    """
    src = Path(in_hwpx)
    out = Path(out_hwpx)
    report = SubmitReport(input=str(src), output=str(out))

    # 1) 채움 — 원본미수정·원자적쓰기·덮어쓰기금지는 fill_hwpx 에 내장.
    fill_rep = fill_hwpx(src, out, identity=identity, replacements=replacements)
    report.filled = dict(fill_rep.filled)
    report.residual = list(fill_rep.residual)
    report.notes.extend(fill_rep.notes)
    report.final = str(out)

    # 1.5) 제출본 공통 후처리(안내문구·유색·lineseg) — temp 경유 후 원자적 교체.
    if submission_cleanup:
        cleaned = out.with_name(f"{out.stem}.__cleanup__.{os.getpid()}{out.suffix}")
        try:
            stats = finalize_submission_hwpx(
                out,
                cleaned,
                force_black=normalize_colors,
                remove_guides=True,
                strip_lineseg=True,
            )
            cleaned.replace(out)
            report.notes.append(
                "제출 cleanup: "
                f"안내 {stats.get('guides_removed', 0)}·"
                f"검정 {stats.get('charpr_blacked', 0)}·"
                f"lineseg {stats.get('linesegarray_removed', 0)}"
            )
        except Exception as exc:  # noqa: BLE001 — cleanup 실패는 치명 아님(검사에서 잡힘)
            report.notes.append(f"제출 cleanup 스킵(오류): {type(exc).__name__}")
        finally:
            if cleaned.exists():
                try:
                    cleaned.unlink()
                except OSError:
                    pass
    elif normalize_colors:
        # cleanup opt-out 시에만 기존 유색→검정 단독 경로 사용.
        try:
            n_black = normalize_colors_in_hwpx(out)
            if n_black:
                report.notes.append(f"유색 예시체 검정 정규화 {n_black}건")
        except Exception as exc:  # noqa: BLE001
            report.notes.append(f"검정 정규화 스킵(오류): {type(exc).__name__}")

    # 2) 게이트 생략(opt-out) — 스킵 사실을 정직하게 남긴다.
    if not acceptance_gate:
        report.ok = bool(fill_rep.ok)
        report.notes.append(
            "수용검사 게이트 생략(acceptance_gate=False) — 제출 전 별도 점검 필요.")
        return report

    # 3) 수용검사 — 예외는 '검사불능'이며 fail-closed 로 _DRAFT 강제(R9).
    allowed_names = [
        str(v) for src in (identity, replacements) if src
        for v in src.values() if str(v or "").strip()
    ]
    try:
        acc = run_hwpx_acceptance(out, allowed_names=allowed_names)
    except Exception as exc:  # noqa: BLE001 — 판정 불가는 전부 제출불가로
        report.acceptance = {"ok": False,
                             "exception": f"{type(exc).__name__}: {exc}"}
        report.error = f"수용검사 불능(fail-closed): {type(exc).__name__}: {exc}"
        report.draft_reason = "검사불능 — 판정 불가는 제출불가로 처리(_DRAFT 강제)"
        report.final = str(_mark_draft(report, out, src))
        report.ok = False
        return report

    report.acceptance = acc.as_dict()
    if acc.ok:
        report.ok = True
        return report

    # 4) 게이트 fail — 결함 요약을 사유로 남기고 _DRAFT 강제.
    report.draft_reason = (
        f"수용검사 fail {acc.fail_defects}건 — 유색 {acc.colored}"
        f"·안내문구 {acc.guides}·linesegarray {acc.linesegarray}"
        f"·예시이름 {acc.dummy_names}"
        " (제출 전 후처리 필요)"
    )
    report.final = str(_mark_draft(report, out, src))
    report.ok = False
    return report
