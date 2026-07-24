#!/usr/bin/env python
"""사업계획서 이미지 자동화 CLI (M1: NotebookLM + 슬라이드 분리 + 출처목록).

예:
  py -3.11 scripts/run_business_plan_images.py --check-env
  py -3.11 scripts/run_business_plan_images.py --input doc.pdf --mode notebooklm --dry-run
  py -3.11 scripts/run_business_plan_images.py --input doc.pdf --mode notebooklm --allow-external-upload
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# app/ 가 import 루트
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from auto_write.image_automation.m1_pipeline import run_m1
from auto_write.image_automation.notebooklm_state import verify_slide_description_fixture
from auto_write.image_automation.repo_name import RepoNameError, canonical_repo_name


def check_env() -> int:
    errors: list[str] = []
    try:
        import fitz  # noqa: F401
    except ImportError:
        errors.append("PyMuPDF(fitz) 미설치")
    try:
        import pptx  # noqa: F401
    except ImportError:
        errors.append("python-pptx 미설치")
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        errors.append("pywin32 미설치 (PPTX/DOCX COM 변환용)")
    try:
        import playwright  # noqa: F401
    except ImportError:
        errors.append("playwright 미설치")
    try:
        verify_slide_description_fixture()
    except Exception as exc:
        errors.append(f"고정 설명 fixture 불일치: {exc}")
    try:
        name, origin = canonical_repo_name(APP_ROOT.parent)
        print(f"repo_name={name}")
        print(f"origin_present=yes")
        print(f"git_root={APP_ROOT.parent}")
    except RepoNameError as exc:
        errors.append(f"repo 이름 확정 실패: {exc}")

    if errors:
        print("ENV_CHECK_FAIL")
        for e in errors:
            print(f"- {e}")
        return 2
    print("ENV_CHECK_OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Business plan image automation (M1)")
    p.add_argument("--input", type=Path, help="입력 PDF/DOCX/HWP/HWPX")
    p.add_argument("--library", type=Path, help="이미지 라이브러리 (M2+)")
    p.add_argument(
        "--mode",
        choices=["library", "gpt", "notebooklm", "hybrid"],
        default="notebooklm",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--allow-external-upload",
        action="store_true",
        help="NotebookLM 등 외부 업로드 허용 (실행마다 명시 필요)",
    )
    p.add_argument("--resume", type=str, default="", help="run_id 재개 (M1 부분 지원)")
    p.add_argument("--results-root", type=Path, default=Path("results") / "image_runs")
    p.add_argument("--check-env", action="store_true")
    p.add_argument("--slides-input", type=Path, help="분리할 PDF/PPTX (NotebookLM 다운로드 대체)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check_env:
        return check_env()
    if not args.input:
        print("--input 이 필요합니다 (또는 --check-env).", file=sys.stderr)
        return 1

    if args.mode in {"notebooklm", "hybrid"} and not args.allow_external_upload and not args.dry_run:
        print(
            "경고: --allow-external-upload 없음 → NotebookLM 업로드/생성 차단. "
            "로컬 정규화·슬라이드 분리·출처목록만 수행합니다.",
            file=sys.stderr,
        )

    # 실제 업로드 전 대상 요약 (경로 자체는 콘솔만)
    print(f"input={args.input}")
    print(f"mode={args.mode}")
    print(f"allow_external_upload={bool(args.allow_external_upload)}")
    print(f"dry_run={bool(args.dry_run)}")

    result = run_m1(
        args.input,
        results_root=args.results_root,
        mode=args.mode,
        allow_external_upload=bool(args.allow_external_upload),
        dry_run=bool(args.dry_run),
        cwd=APP_ROOT.parent,
        slides_input=args.slides_input,
        run_id=args.resume or None,
    )
    print(json.dumps(result.report, ensure_ascii=False, indent=2))
    print(f"run_dir={result.run_dir}")
    print(f"draft={result.draft}")
    # exit: 0=성공(비DRAFT 또는 dry-run), 2=DRAFT/차단, 1=입력오류
    if result.draft and not args.dry_run:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
