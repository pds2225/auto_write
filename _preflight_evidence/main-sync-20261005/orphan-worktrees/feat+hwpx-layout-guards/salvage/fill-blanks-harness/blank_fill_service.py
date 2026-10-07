"""blank_fill_service.py

빈칸 채우기 공통 골격 (1단계: AI 없이 plan 기반).

목적
----
완성된(혹은 양식) DOCX 의 **목차(섹션 제목) 뒤 빈 칸만** 사용자 제공 plan(JSON/dict)
으로 채운다. 실제 채움은 이미 검증된 제너릭 엔진 `SubmittableFiller` 가 담당하고,
본 모듈은 그 엔진을 안전하게 감싸는 '토대(오케스트레이션)' 역할만 한다.

설계 원칙(클린 아키텍처)
----------------------
- 채움 로직(도메인)은 `SubmittableFiller` 에 위임한다. 본 모듈은 입력검증·백업·
  안전복사 같은 '바깥 경계(boundary)' 책임만 가진다.
- 채울 데이터(plan)는 외부에서 주입한다. 특정 기업 정보를 하드코딩하지 않는다.
- 원본을 절대 덮어쓰지 않는다(출력 경로가 입력과 같으면 거부).
- 후처리 전 원본을 results/backup/<timestamp>/ 에 백업한다(orchestrator 패턴 재사용).

목차 보존 보장
-------------
`SubmittableFiller` 는 값이 있는 칸·제목 문단은 건드리지 않고 '비어있거나 더미인 곳'
만 보정하므로, 섹션 제목(목차)은 그대로 보존된다. 본 모듈은 제목을 삭제·변경하지
않는다.

멱등성(재실행 안전) 경고
----------------------
`SubmittableFiller._apply_paragraph_fills` 는 앵커 문단 '뒤'에 새 문단을 삽입한다.
따라서 **같은 plan 을 같은 본문에 두 번 적용하면 본문이 중복될 수 있다.** 안전한
재실행을 위해서는 항상 '원본'을 입력으로 삼아 1회만 적용하라(출력본을 다시 입력으로
넣지 말 것). fill_blanks 는 매 호출마다 백업을 남기므로, 원본→출력 1회 적용을
지키는 한 재실행은 안전하다.

향후 2단계(AI 채우기) 연결 지점
-----------------------------
지금은 plan 을 외부에서 주입받지만, 2단계에서는 AI(openai/anthropic service)가
문서를 분석해 동일 스키마의 plan dict 를 생성한 뒤 fill_blanks(..., plan=ai_plan)
으로 주입하면 된다. plan 이 None 이면 본 모듈은 '채울 데이터 없음'으로 보고
입력을 출력으로 안전 복사하므로(에러 아님), AI 단계가 비어 있어도 파이프라인은
깨지지 않는다. 즉 이 None 분기가 AI plan 주입을 위한 빈 자리다.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document

from .submittable_filler import SubmittableFiller


def _default_backup_root(input_path: Path) -> Path:
    """백업 루트 기본값을 결정한다.

    repo 관례상 산출물은 results/ 아래에 둔다. 입력 경로 주변에서 'results' 디렉토리를
    탐색하고, 없으면 입력 파일과 같은 폴더 아래 results/backup 을 만든다.
    """
    for parent in [input_path.parent, *input_path.parents]:
        candidate = parent / "results"
        if candidate.is_dir():
            return candidate / "backup"
    return input_path.parent / "results" / "backup"


def _backup_original(input_path: Path, backup_root: Path) -> Path:
    """원본을 results/backup/<YYYYMMDD_HHMMSS>/ 에 복사하고 백업 폴더를 반환한다.

    (orchestrator.backup_original 패턴 재사용 — 타임스탬프 폴더 + copy2)
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, backup_dir / input_path.name)
    return backup_dir


def fill_blanks(
    input_docx: Path | str,
    output_docx: Path | str,
    *,
    plan: dict[str, Any] | None = None,
    backup_root: Path | str | None = None,
) -> dict[str, Any]:
    """양식/완성 DOCX 의 빈칸을 plan 으로 채운다(목차는 보존).

    처리 순서
    --------
    1) 입력 검증: output==input 이면 ValueError(원본 덮어쓰기 금지).
    2) 백업: 원본을 results/backup/<timestamp>/ 에 복사.
    3) 채움: plan 이 있으면 SubmittableFiller(plan).finalize(...) 로 빈칸을 채움.
    4) plan 없음: 입력을 출력으로 안전 복사(에러 아님). report.filled=False.
    5) 반환: 채운 항목 수·백업 경로·plan 적용 여부·잔존 더미 스캔 결과 등 report dict.

    Parameters
    ----------
    input_docx : 원본(또는 양식) DOCX 경로. 절대 덮어쓰지 않는다.
    output_docx : 결과 DOCX 경로. input 과 같으면 ValueError.
    plan : 빈칸을 채울 데이터 dict. None 이면 안전 복사만 한다(향후 AI plan 주입 자리).
    backup_root : 백업 루트. None 이면 results/backup 을 자동 탐색/생성.

    Returns
    -------
    report dict — 주요 키:
      filled (bool), plan_applied (bool), backup_dir (str),
      input_docx (str), output_docx (str),
      (plan 적용 시) SubmittableFiller report 병합,
      residual_remaining (list) — 잔존 더미 스캔 결과.

    멱등성 경고
    ----------
    재실행 시에도 '원본'을 input 으로 넣어 1회만 적용하라. 출력본을 다시 input 으로
    넣으면 paragraph_fills 가 본문을 중복 삽입할 수 있다(모듈 docstring 참고).
    """
    input_path = Path(input_docx).resolve()
    output_path = Path(output_docx).resolve()

    # 1) 입력 검증 -------------------------------------------------------------
    if not input_path.exists():
        raise FileNotFoundError(f"입력 DOCX 없음: {input_path}")
    if input_path.suffix.lower() != ".docx":
        raise ValueError(f"DOCX 파일이 아님: {input_path}")
    if output_path == input_path:
        raise ValueError("원본 덮어쓰기 금지 (출력 경로가 입력과 동일합니다).")

    # 2) 백업 ------------------------------------------------------------------
    if backup_root is None:
        resolved_backup_root = _default_backup_root(input_path)
    else:
        resolved_backup_root = Path(backup_root)
    backup_dir = _backup_original(input_path, resolved_backup_root)

    report: dict[str, Any] = {
        "input_docx": str(input_path),
        "output_docx": str(output_path),
        "backup_dir": str(backup_dir),
        "plan_applied": False,
        "filled": False,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 4) plan 없음 → 안전 복사 (향후 AI plan 주입 자리) -------------------------
    if not plan:
        shutil.copy2(input_path, output_path)
        report["filled"] = False
        report["reason"] = "no plan provided"
        # 잔존 더미 스캔(복사본 기준) — 사람이 무엇이 비어있는지 알 수 있게.
        report["residual_remaining"] = SubmittableFiller({}).scan_residual(
            Document(str(output_path))
        )
        return report

    # 3) 채움: 제너릭 엔진에 위임 ----------------------------------------------
    fill_report = SubmittableFiller(plan).finalize(input_path, output_path)
    report.update(fill_report)  # identity_filled / residual_remaining 등 병합
    report["plan_applied"] = True
    report["filled"] = True
    return report
