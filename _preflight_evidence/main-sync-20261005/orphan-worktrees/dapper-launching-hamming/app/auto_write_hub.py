"""auto_write_hub.py — 어디서든 동일한 단일 진입점.

로컬 / 원격 / 다른 PC / 모바일(Python 가능 시) 모두 같은 명령:

    py -3.11 auto_write_hub.py env
    py -3.11 auto_write_hub.py diagnose 문서.docx|문서.hwpx
    py -3.11 auto_write_hub.py fill --notice-folder … --confirm-output-plan …

본선은 RHWP → **HWPX만** 산출. DOCX로 만들지 않음(명시적 docx-crossform+승인 제외).
COM 은 Windows+한글2022 에서만(없으면 정직히 실패, DOCX로 우회 금지).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cmd_env(_: argparse.Namespace) -> int:
    from auto_write.services.runtime_env import detect_capabilities

    caps = detect_capabilities()
    print(json.dumps(caps.as_dict(), ensure_ascii=False, indent=2))
    return 0 if caps.portable_core else 2


def cmd_diagnose(args: argparse.Namespace) -> int:
    """DOCX|HWPX 통합 진단 — self_diagnose 가 확장자로 라우팅."""
    from self_diagnose import main as diagnose_main

    argv = [str(args.path)]
    if args.json:
        argv += ["--json", args.json]
    if args.require_specialty:
        argv.append("--require-specialty")
    return diagnose_main(argv)


def cmd_fill(args: argparse.Namespace) -> int:
    from auto_write.services.runtime_env import assert_engine_allowed, detect_capabilities
    from cross_form_hwp_pipeline import main as pipe_main

    caps = detect_capabilities()
    engine = args.engine or caps.recommended_engine()
    try:
        assert_engine_allowed(engine)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    outputs = list(args.outputs or ["hwpx"])
    # 본선 계약: DOCX로 만들지 않음. 명시적 docx-crossform+승인만 예외.
    if "docx" in outputs and engine != "docx-crossform":
        print(
            "ERROR: DOCX 산출 금지. 본선은 --output hwpx 만. "
            "DOCX가 필요하면 --engine docx-crossform --confirm-output-plan 을 명시하세요.",
            file=sys.stderr,
        )
        return 2
    if engine == "rhwp-hwpx-fill" and "hwpx" not in outputs:
        print(
            "ERROR: rhwp-hwpx-fill 은 --output hwpx 필수 (DOCX-only 우회 금지)",
            file=sys.stderr,
        )
        return 2

    argv: list[str] = [
        "--notice-folder",
        str(args.notice_folder),
        "--engine",
        engine,
    ]
    for o in outputs:
        argv += ["--output", o]
    if args.confirm_output_plan:
        argv.append("--confirm-output-plan")
    if args.extract_forms:
        argv.append("--extract-forms")
    if args.supplement_resume:
        argv.append("--supplement-resume")
    if args.facts_json:
        argv += ["--facts-json", str(args.facts_json)]
    if args.hwpx_base:
        argv += ["--hwpx-base", str(args.hwpx_base)]
    for sp in args.confirm_specialty or []:
        argv += ["--confirm-specialty", sp]
    if args.no_diagnose:
        argv.append("--no-diagnose")
    if args.name:
        argv += ["--name", args.name]
    if args.form_prefix:
        argv += ["--form-prefix", args.form_prefix]
    if args.version:
        argv += ["--version", args.version]
    if args.no_submit_copy:
        argv.append("--no-submit-copy")

    # 환경 스냅샷은 파이프라인 JSON 앞에 참고용으로 stderr 한 줄
    print(
        f"[hub] engine={engine} portable_core={caps.portable_core} "
        f"com_hwp={caps.com_hwp} os={caps.os_name}",
        file=sys.stderr,
    )
    return pipe_main(argv)


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        description="auto_write 통합 허브 — 로컬/원격/다른PC/모바일 동일 CLI"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_env = sub.add_parser("env", help="환경 capability JSON")
    p_env.set_defaults(func=cmd_env)

    p_diag = sub.add_parser(
        "diagnose",
        help="기존 문서 진단 (.hwpx 권장; .docx는 레거시만). 채움 산출 아님 (exit 0/1/2/3)",
    )
    p_diag.add_argument("path", help="진단할 기존 파일 (.hwpx|.docx) — 새로 만들지 않음")
    p_diag.add_argument("--json", help="결과 JSON 경로")
    p_diag.add_argument("--require-specialty", action="store_true")
    p_diag.set_defaults(func=cmd_diagnose)

    p_fill = sub.add_parser("fill", help="공고 양식 HWPX 채움 (RHWP 본선)")
    p_fill.add_argument("--notice-folder", required=True)
    p_fill.add_argument(
        "--engine",
        default=None,
        help="기본=환경 recommended (rhwp-hwpx-fill)",
    )
    p_fill.add_argument(
        "--output",
        dest="outputs",
        action="append",
        choices=["hwpx", "hwp", "docx"],
    )
    p_fill.add_argument(
        "--confirm-output-plan",
        action="store_true",
        help="출력 형식·엔진 사용자 승인 (필수)",
    )
    p_fill.add_argument("--extract-forms", action="store_true")
    p_fill.add_argument("--supplement-resume", action="store_true")
    p_fill.add_argument("--facts-json")
    p_fill.add_argument("--hwpx-base")
    p_fill.add_argument("--confirm-specialty", action="append", default=[])
    p_fill.add_argument("--no-diagnose", action="store_true")
    p_fill.add_argument("--name", help="성명(파일명). 없으면 identity 성명")
    p_fill.add_argument("--form-prefix", default="전문상담위원_참여신청서")
    p_fill.add_argument("--version", default=None, help="예: v1")
    p_fill.add_argument("--no-submit-copy", action="store_true")
    p_fill.set_defaults(func=cmd_fill)

    args = parser.parse_args(argv)
    if args.cmd == "fill" and not args.confirm_output_plan:
        print(
            "ERROR: --confirm-output-plan 필수 (승인 없는 엔진/출력 우회 금지)",
            file=sys.stderr,
        )
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
