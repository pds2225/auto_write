#!/usr/bin/env python
"""사업계획서 이미지 자동화 CLI (M1 NotebookLM + M2 CLASSIFY/MATCH + M4 mock).

예:
  py -3.11 scripts/run_business_plan_images.py --check-env
  py -3.11 scripts/run_business_plan_images.py --input doc.pdf --mode notebooklm --dry-run
  py -3.11 scripts/run_business_plan_images.py --input doc.pdf --mode notebooklm --allow-external-upload
  py -3.11 scripts/run_business_plan_images.py --library "C:\\images" --mode library
  py -3.11 scripts/run_business_plan_images.py --input doc.pdf --library "C:\\images" --mode library
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# app/ 가 import 루트
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from auto_write.image_automation.m1_pipeline import run_m1
from auto_write.image_automation.m2_pipeline import run_m2
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
    p = argparse.ArgumentParser(description="Business plan image automation (M1+M2+M4 mock)")
    p.add_argument("--input", type=Path, help="입력 PDF/DOCX/HWP/HWPX")
    p.add_argument("--library", type=Path, help="이미지 라이브러리 (M2 CLASSIFY/MATCH)")
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
    p.add_argument("--resume", type=str, default="", help="run_id 재개")
    p.add_argument("--results-root", type=Path, default=Path("results") / "image_runs")
    p.add_argument("--check-env", action="store_true")
    p.add_argument("--slides-input", type=Path, help="분리할 PDF/PPTX (NotebookLM 다운로드 대체)")
    p.add_argument(
        "--slides-dir",
        type=Path,
        help="이미 분리된 slides 디렉터리 (M2에서 M1 산출물 재사용)",
    )
    p.add_argument(
        "--doc-text",
        type=Path,
        help="앵커 추출용 텍스트 파일(줄 단위). 없으면 기본 PSST 앵커 사용",
    )
    p.add_argument(
        "--enable-generate-missing",
        action="store_true",
        help="M4: 결손 앵커용 mock stub만 생성 (실 OpenAI 호출 없음, 기본 OFF)",
    )
    p.add_argument(
        "--max-paid-calls",
        type=int,
        default=0,
        help="M4: mock/유료 생성 호출 상한 (enable 시 >0 필요, 기본 0=생성 없음)",
    )
    return p


def _run_m4_generate_missing(m2: Any, *, max_paid_calls: int) -> int:
    """Run M4 mock generate_missing after M2. Returns 0 always (fail-safe)."""
    from auto_write.image_automation.generate_missing import generate_missing_assets

    if max_paid_calls <= 0:
        print(
            "경고: --enable-generate-missing 이지만 --max-paid-calls<=0 "
            "→ 생성 0건 (budget_zero). --max-paid-calls N 을 지정하세요.",
            file=sys.stderr,
        )

    gen = generate_missing_assets(
        list(m2.manifest.anchors),
        list(m2.manifest.matches),
        out_dir=m2.run_dir / "generate_missing",
        enabled=True,
        missing_only=True,
        max_paid_calls=int(max_paid_calls),
        use_mock=True,
    )
    reason = gen.extras.get("reason", "")
    print("--- M4 GENERATE_MISSING (mock stub, no real OpenAI) ---")
    print(
        json.dumps(
            {
                "use_mock": True,
                "openai_calls": gen.openai_calls,
                "openai_calls_real": gen.extras.get("openai_calls_real", 0),
                "mock_calls": gen.extras.get("mock_calls", 0),
                "gemini_calls": gen.gemini_calls,
                "generated": len(gen.generated),
                "skipped": gen.skipped,
                "draft": gen.draft,
                "reason": reason,
                "receipt": str(gen.receipt_path) if gen.receipt_path else "",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_doc_blocks(doc_text: Path | None) -> list[str] | None:
    if doc_text and Path(doc_text).is_file():
        return [
            line.strip()
            for line in Path(doc_text).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check_env:
        return check_env()

    m4_ran = False

    # M2 library-only: --library 만으로 실행 가능
    if args.mode == "library" or (args.library and not args.input and args.mode != "notebooklm"):
        if not args.library and not args.slides_dir:
            print("--mode library 에는 --library 또는 --slides-dir 가 필요합니다.", file=sys.stderr)
            return 1
        print(f"mode=library library={args.library} slides_dir={args.slides_dir}")
        blocks = _load_doc_blocks(args.doc_text)
        m2 = run_m2(
            results_root=args.results_root,
            library=args.library,
            slides_dir=args.slides_dir,
            document_text_blocks=blocks,
            run_id=args.resume or None,
        )
        print(json.dumps(m2.report, ensure_ascii=False, indent=2))
        print(f"run_dir={m2.run_dir}")
        print(f"draft={m2.draft}")
        if args.enable_generate_missing:
            _run_m4_generate_missing(m2, max_paid_calls=int(args.max_paid_calls))
            m4_ran = True
        return 0

    if not args.input:
        print("--input 이 필요합니다 (또는 --check-env / --mode library).", file=sys.stderr)
        return 1

    if args.mode in {"notebooklm", "hybrid"} and not args.allow_external_upload and not args.dry_run:
        print(
            "경고: --allow-external-upload 없음 → NotebookLM 업로드/생성 차단. "
            "로컬 정규화·슬라이드 분리·출처목록만 수행합니다.",
            file=sys.stderr,
        )

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

    # hybrid/library 후속: M1 슬라이드 + 라이브러리 분류·매칭
    if args.library and args.mode in {"library", "hybrid", "notebooklm"} and not args.dry_run:
        slides = result.run_dir / "slides"
        blocks = _load_doc_blocks(args.doc_text)
        m2 = run_m2(
            results_root=args.results_root,
            library=args.library,
            slides_dir=slides if slides.is_dir() else None,
            document_text_blocks=blocks,
            run_id=f"{result.run_id}-m2",
        )
        print("--- M2 CLASSIFY/MATCH ---")
        print(json.dumps(m2.report, ensure_ascii=False, indent=2))
        print(f"m2_run_dir={m2.run_dir}")
        if args.enable_generate_missing:
            _run_m4_generate_missing(m2, max_paid_calls=int(args.max_paid_calls))
            m4_ran = True

    if args.enable_generate_missing and not m4_ran:
        print(
            "경고: --enable-generate-missing 이 켜졌지만 M2가 실행되지 않아 M4를 스킵했습니다. "
            "(--library 필요, dry-run 에서는 M4 미실행)",
            file=sys.stderr,
        )

    if result.draft and not args.dry_run:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
