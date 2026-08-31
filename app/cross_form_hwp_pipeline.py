"""cross_form_hwp_pipeline.py — 공고 HWP/HWPX 양식 채움 단일 진입점 (Sprint 1).

재발 방지:
- 기본 산출 = HWPX (rhwp-hwpx-fill). 한글 기본은 --confirm-output-plan 불필요.
- DOCX·엔진 변경은 ``--confirm-output-plan`` 필수 (암묵적 DOCX 우회 금지)
- COM 은 ``hancom_com_guard`` 가 2024(HOffice130) 기동을 차단
- 본선 산출은 HWPX(서식만). DOCX는 명시적 ``docx-crossform`` 만.
- 구 스크립트 ``_finish_minwon_rhwp.py`` / ``_complete_minwon_job.py`` 사용 금지
- 이진 .hwp 는 Windows+한글 COM 전용. 이 환경은 .hwpx XML 채움.

사용 예 (PowerShell)::

    cd D:\\auto_write\\app
    py -3.11 cross_form_hwp_pipeline.py ^
        --notice-folder "C:\\...\\21_기업민원..."
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from auto_write.services.cross_form_output_policy import (
    FillEngine,
    OutputFormat,
    OutputPlan,
    OutputPolicyError,
    validate_output_plan,
)
from auto_write.services.output_naming import resolve_submit_path
from auto_write.services.cross_form_autofill import extract_source_fields
from auto_write.services.hwp_docx_convert import hwp_to_docx
from auto_write.services.hwpx_fill import fill_hwpx
from auto_write.services.hwpx_form_extract import extract_forms_only, looks_like_notice_blob
from auto_write.services.hwpx_resume_supplement import canonical_sign_date

APP = Path(__file__).resolve().parent


def _to_docx_rhwp(path: Path, out: Path) -> str:
    rep = hwp_to_docx(path, out, use_com=False)
    if not rep.ok:
        raise RuntimeError(f"RHWP 변환 실패 {path.name}: {rep.notes}")
    return rep.method


def _extract_identity(profile: Path, resume: Path, master: Path, tmp: Path) -> dict[str, str]:
    def fields(p: Path) -> dict[str, str]:
        if not p.is_file():
            return {}
        docx = tmp / f"{p.stem}_src.docx"
        _to_docx_rhwp(p, docx)
        return extract_source_fields(str(docx))

    pm, rm, mm = fields(profile), fields(resume), fields(master)

    def pick(*maps: dict[str, str], keys: tuple[str, ...]) -> str:
        for k in keys:
            for m in maps:
                v = (m.get(k) or "").strip()
                if v:
                    return v
        return ""

    ident: dict[str, str] = {}
    for tgt, keys in [
        ("성명", ("성명",)),
        ("생년월일", ("생년월일",)),
        ("휴대전화", ("핸드폰", "휴대전화")),
        ("이메일", ("이메일",)),
        ("소속", ("소속", "소속기관", "기관명")),
        ("직위", ("직위", "직책")),
        ("주소", ("주소", "거주지")),
    ]:
        v = pick(pm, rm, mm, keys=keys)
        if v:
            ident[tgt] = v
    so = pick(pm, rm, mm, keys=("소속", "소속기관", "기관명"))
    jw = pick(pm, rm, mm, keys=("직위", "직책"))
    if so and jw:
        ident["소속/직위"] = f"{so} / {jw}"
    elif so:
        ident["소속/직위"] = so
    addr = pick(pm, rm, mm, keys=("주소", "거주지"))
    if addr:
        ident["주소(거주지)"] = addr
        ident["주소"] = addr
    return ident


def _default_sources(notice: Path) -> tuple[Path, Path, Path]:
    desktop = Path.home() / "OneDrive" / "바탕 화면"
    profile = desktop / "프로필 양식_박다솜_v5.hwpx"
    resume = desktop / "1. 이력서 박다솜 20250308 서울창조경제혁신센터 초기창업패키지 평가위원.hwp"
    master = desktop / (
        "노트북(다솜) 백업 20231222/다솜/개인/★이력서/"
        "01. 경영지도사 이력서/이력서 박다솜 20230804.hwp"
    )
    return profile, resume, master


def _find_target(notice: Path) -> Path:
    for p in sorted(notice.glob("*.hwp")):
        if "공고" in p.name:
            return p
    hwps = list(notice.glob("*.hwp"))
    if not hwps:
        raise FileNotFoundError(f"공고 폴더에 .hwp 가 없습니다: {notice}")
    return hwps[0]


def _ensure_forms_base(work: Path, raw_base: Path, *, extract: bool) -> tuple[Path, dict]:
    """공고+서식 base → 서식만 ``10_forms_only.hwpx``."""
    forms_only = work / "10_forms_only.hwpx"
    meta: dict = {"extract_forms": extract, "source_base": str(raw_base)}
    if not extract:
        return raw_base, meta
    if not raw_base.is_file():
        raise FileNotFoundError(f"HWPX 베이스 없음: {raw_base}")
    # 이미 서식만이면 스킵
    import zipfile

    with zipfile.ZipFile(raw_base) as z:
        blob = "".join(
            z.read(n).decode("utf-8", "replace")
            for n in z.namelist()
            if n.endswith(".xml") and "section" in n
        )
    if looks_like_notice_blob(blob) or ("[서식 1]" in blob and "모집공고" in blob):
        rep = extract_forms_only(raw_base, forms_only)
        meta["extract_report"] = rep.as_dict()
        if not rep.ok:
            raise RuntimeError(f"서식 분리 실패: {rep.notes}")
        return forms_only, meta
    meta["extract_skipped"] = "notice markers not found — using base as-is"
    return raw_base, meta


def _default_facts(identity: dict[str, str]) -> dict:
    """하드코딩 금지 대체: 파이프라인 기본 facts(모집분야 체크 없음)."""
    today = canonical_sign_date()
    return {
        "education": [
            ["2025년 8월 (졸업)", "한양대학교 대학원", "경영컨설팅학과 (석사)"],
            ["2016년 2월 (졸업)", "강남대학교", "경영학과 (학사)"],
        ],
        "licenses": [
            ["경영지도사 (등록 제12040호)", "2020/01/01", "마케팅", "중소벤처기업부"],
            ["스타트업 AC 심사역(인증 제23-14호)", "2023/02/07", "-", "씨엔티테크"],
        ],
        "careers": [
            ["밸류업파트너스", "2022.11 ~ 현재", "대표", "정부지원사업·정책자금·투자유치 컨설팅"],
            ["한국경영기술지도사회 중부·여성지회", "2023.02 ~ 현재", "이사·부회장", "조직운영·전문가 강의"],
            ["IPO브릿지", "2022.02 ~ 2022.11", "선임컨설턴트", "사업계획서·IR자료 컨설팅"],
            ["오케이저축은행", "2020.03 ~ 2021.07", "계장", "기업금융·투자금융(IB)"],
            ["웰컴저축은행", "2016.11 ~ 2020.02", "계장", "기업금융(부동산·PF)"],
        ],
        "specialty_text": "",
        "check_columns": [],
        "sign_date": today,
        "sign_name": identity.get("성명", ""),
    }


def run_pipeline(
    notice_folder: Path,
    plan: OutputPlan,
    *,
    hwpx_base: Path | None = None,
    profile: Path | None = None,
    resume: Path | None = None,
    master: Path | None = None,
    supplement_resume: bool = False,
    extract_forms: bool = False,
    facts_json: Path | None = None,
    specialty_confirms: list[str] | None = None,
    run_diagnose: bool = True,
    submit_name: str | None = None,
    form_prefix: str = "전문상담위원_참여신청서",
    submit_version: str | None = None,
    write_submit_copy: bool = True,
) -> dict:
    validate_output_plan(plan)
    work = notice_folder / "_workspace"
    work.mkdir(parents=True, exist_ok=True)
    (work / "00_output_plan.json").write_text(
        json.dumps(plan.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    target = _find_target(notice_folder)
    prof, res, mas = profile, resume, master
    if prof is None or res is None or mas is None:
        dprof, dres, dmas = _default_sources(notice_folder)
        prof = prof or dprof
        res = res or dres
        mas = mas or dmas

    result: dict = {"plan": plan.as_dict(), "target": str(target), "outputs": {}}

    with tempfile.TemporaryDirectory(prefix="cf_hwp_pipe_") as td:
        tmp = Path(td)
        identity = _extract_identity(prof, res, mas, tmp)
        (work / "01_source_facts.json").write_text(
            json.dumps({"identity": identity, "engine": plan.engine.value}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if plan.engine is FillEngine.RHWP_HWPX:
            raw_base = hwpx_base or (work / "10_form_base.hwpx")
            base, extract_meta = _ensure_forms_base(work, raw_base, extract=extract_forms)
            result["form_extract"] = extract_meta

            out_hwpx = work / "02_filled.hwpx"
            fr = fill_hwpx(base, out_hwpx, identity=identity)
            result["outputs"]["hwpx"] = str(out_hwpx)
            result["filled"] = fr.filled
            result["filled_count"] = fr.filled_count

            if supplement_resume:
                from auto_write.services.hwpx_resume_supplement import (
                    load_resume_facts,
                    supplement_hwpx_from_resume,
                )
                from auto_write.services.hwpx_specialty_profile import (
                    SpecialtyConfirmError,
                    resolve_specialty_checks,
                )

                facts_path = facts_json
                if facts_path is None:
                    facts_path = work / "01_resume_table_facts.json"
                    if not facts_path.is_file():
                        facts_path.write_text(
                            json.dumps(_default_facts(identity), ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                facts_data = load_resume_facts(facts_path)
                # L034: confirm 없으면 check_columns 강제 비움 / confirm 있으면 맵핑
                confirms = list(specialty_confirms or [])
                if confirms:
                    try:
                        facts_data["check_columns"] = [
                            list(x) for x in resolve_specialty_checks(confirms)
                        ]
                    except SpecialtyConfirmError as exc:
                        raise RuntimeError(str(exc)) from exc
                else:
                    facts_data["check_columns"] = []
                    facts_data.setdefault("specialty_text", facts_data.get("specialty_text") or "")
                facts_path.write_text(
                    json.dumps(facts_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                result["specialty_confirms"] = confirms
                result["check_columns"] = facts_data.get("check_columns") or []

                mid = work / "_step_before_supplement.hwpx"
                if not mid.exists():
                    import shutil

                    shutil.copyfile(out_hwpx, mid)
                sup = supplement_hwpx_from_resume(out_hwpx, out_hwpx, facts_json=facts_path)
                result["supplement"] = sup.as_dict()
                result["facts_json"] = str(facts_path)

            # L037 휴리스틱
            import zipfile

            with zipfile.ZipFile(out_hwpx) as z:
                out_blob = "".join(
                    z.read(n).decode("utf-8", "replace")
                    for n in z.namelist()
                    if n.endswith(".xml") and "section" in n
                )
            result["l037_forms_only"] = not looks_like_notice_blob(out_blob)

            # Sprint 2: 채움률
            from auto_write.services.hwpx_fill_coverage import score_hwpx_coverage

            cov = score_hwpx_coverage(out_hwpx)
            result["coverage"] = cov.as_dict()
            (work / "03_fill_coverage.json").write_text(
                json.dumps(cov.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # Sprint 3: HWPX 진단
            if run_diagnose:
                from hwpx_self_diagnose import diagnose_hwpx

                diag = diagnose_hwpx(
                    out_hwpx,
                    require_specialty_checked=bool(specialty_confirms),
                )
                result["diagnose"] = diag.as_dict()
                (work / "05_hwpx_diagnose.json").write_text(
                    json.dumps(diag.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
                )

            (work / "02_fill_report.json").write_text(
                json.dumps(
                    {
                        "engine": "rhwp-hwpx-fill (hwpx_fill, use_com=False)",
                        "output": str(out_hwpx),
                        "filled": fr.filled,
                        "filled_count": fr.filled_count,
                        "residual": fr.residual,
                        "ok": fr.filled_count > 0,
                        "supplement": result.get("supplement"),
                        "l037_forms_only": result["l037_forms_only"],
                        "form_extract": extract_meta,
                        "specialty_confirms": result.get("specialty_confirms"),
                        "coverage": result.get("coverage"),
                        "diagnose_ok": (result.get("diagnose") or {}).get("ok"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        elif plan.engine is FillEngine.COM_HWPX:
            from auto_write.services.hwp_com_fill import fill_hwp_via_hwpx

            out_hwp = work / "02_filled.hwp"
            out_hwpx = work / "02_filled.hwpx"
            hwp_rep = fill_hwp_via_hwpx(target, out_hwp, identity=identity, use_com=True)
            result["filled"] = hwp_rep.filled
            result["filled_count"] = hwp_rep.filled_count
            if OutputFormat.HWP in plan.outputs and out_hwp.is_file():
                result["outputs"]["hwp"] = str(out_hwp)
            if OutputFormat.HWPX in plan.outputs:
                if out_hwpx.is_file():
                    result["outputs"]["hwpx"] = str(out_hwpx)
                elif out_hwp.is_file():
                    from auto_write.services.hwp_docx_convert import _SAVE_FORMATS, _convert_via_com

                    _convert_via_com(out_hwp, out_hwpx, _SAVE_FORMATS[".hwpx"])
                    result["outputs"]["hwpx"] = str(out_hwpx)

        elif plan.engine is FillEngine.DOCX_CROSSFORM:
            out_docx = work / "02_filled.docx"
            cmd = [
                sys.executable,
                "cross_form_fill.py",
                "--source",
                str(prof),
                "--target",
                str(target),
                "-o",
                str(out_docx),
                "--json",
            ]
            p = subprocess.run(
                cmd, cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            result["cross_form_exit"] = p.returncode
            if out_docx.is_file():
                result["outputs"]["docx"] = str(out_docx)
            rp = work / "02_fill_report.json"
            if rp.is_file():
                result["fill_report"] = json.loads(rp.read_text(encoding="utf-8"))

    # 제출용 자동 파일명: 전문상담위원_참여신청서_{성명}.hwpx
    if write_submit_copy:
        person = (submit_name or "").strip()
        if not person:
            try:
                facts = json.loads((work / "01_source_facts.json").read_text(encoding="utf-8"))
                person = ((facts.get("identity") or {}).get("성명") or "").strip()
            except (OSError, json.JSONDecodeError, TypeError):
                person = ""
        person = person or "미상"
        hwpx_src = result.get("outputs", {}).get("hwpx")
        if hwpx_src and Path(hwpx_src).is_file():
            from auto_write.services.submission_gates import (
                build_submit_layout_dir,
                missing_pdf_pair,
                try_generate_sibling_pdf,
            )

            submit_dir = build_submit_layout_dir(notice_folder)
            submit_dir.mkdir(parents=True, exist_ok=True)
            named = resolve_submit_path(
                submit_dir,
                form_prefix=form_prefix,
                name=person,
                ext=".hwpx",
                version=submit_version,
            )
            shutil.copyfile(hwpx_src, named)
            result["submit_copy"] = str(named)
            ws_named = work / named.name
            shutil.copyfile(hwpx_src, ws_named)
            result["workspace_named"] = str(ws_named)
            result["submit_filename"] = named.name
            gen = try_generate_sibling_pdf(named)
            if missing_pdf_pair(named):
                result.setdefault("needs_input", []).append(
                    f"L050: 제출 HWPX 동일명 PDF 없음 ({gen.reason})"
                )

    (work / "00_engines.json").write_text(
        json.dumps(
            {
                "pipeline": "cross_form_hwp_pipeline",
                "plan": plan.as_dict(),
                "result_summary": {
                    k: v for k, v in result.items() if k not in {"fill_report"}
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="공고 HWP/HWPX 양식 채움 (단일 진입점)")
    parser.add_argument("--notice-folder", required=True, type=Path)
    parser.add_argument(
        "--output",
        dest="outputs",
        action="append",
        choices=[o.value for o in OutputFormat],
        help="산출 형식. 기본 hwpx. docx는 명시적 docx-crossform + --confirm-output-plan.",
    )
    parser.add_argument(
        "--engine",
        default="rhwp-hwpx-fill",
        choices=[e.value for e in FillEngine],
        help="기본 rhwp-hwpx-fill. docx-crossform 은 명시+승인.",
    )
    parser.add_argument(
        "--confirm-output-plan",
        action="store_true",
        help="DOCX·엔진 변경 승인 (한글 기본 hwpx 는 불필요)",
    )
    parser.add_argument("--hwpx-base", type=Path, help="입력 HWPX (기본: _workspace/10_form_base.hwpx)")
    parser.add_argument("--source-profile", type=Path)
    parser.add_argument("--source-resume", type=Path)
    parser.add_argument("--source-master", type=Path)
    parser.add_argument(
        "--supplement-resume",
        action="store_true",
        help="학력·자격·경력·서명 표 보강(RHWP). 모집분야 체크는 facts의 check_columns만.",
    )
    parser.add_argument(
        "--extract-forms",
        action="store_true",
        help="공고 본문 제거 후 서식만 채움(L037)",
    )
    parser.add_argument(
        "--facts-json",
        type=Path,
        help="학력/자격/경력 facts JSON. 없으면 _workspace/01_resume_table_facts.json 생성",
    )
    parser.add_argument(
        "--confirm-specialty",
        action="append",
        default=[],
        help="모집분야 confirm (반복 가능). 예: --confirm-specialty 경영활동. 없으면 미체크(L034)",
    )
    parser.add_argument(
        "--no-diagnose",
        action="store_true",
        help="HWPX self_diagnose 생략",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="제출 파일명용 성명. 없으면 identity 성명 → 전문상담위원_참여신청서_{성명}.hwpx",
    )
    parser.add_argument(
        "--form-prefix",
        default="전문상담위원_참여신청서",
        help="제출 파일명 접두",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="파일명 버전 접미사 (예: v1 → …_박다솜_v1.hwpx)",
    )
    parser.add_argument(
        "--no-submit-copy",
        action="store_true",
        help="제출/ 폴더 자동 파일명 복사 생략",
    )
    args = parser.parse_args(argv)

    try:
        plan = OutputPlan.parse(
            output_names=args.outputs or ["hwpx"],
            engine_name=args.engine,
            user_confirmed=args.confirm_output_plan,
        )
        result = run_pipeline(
            args.notice_folder,
            plan,
            hwpx_base=args.hwpx_base,
            profile=args.source_profile,
            resume=args.source_resume,
            master=args.source_master,
            supplement_resume=args.supplement_resume,
            extract_forms=args.extract_forms,
            facts_json=args.facts_json,
            specialty_confirms=args.confirm_specialty,
            run_diagnose=not args.no_diagnose,
            submit_name=args.name,
            form_prefix=args.form_prefix,
            submit_version=args.version,
            write_submit_copy=not args.no_submit_copy,
        )
    except (OutputPolicyError, FileNotFoundError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Windows 콘솔 cp949 대비
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 산출 없으면 2, 진단 fail 이면 2 (게이트)
    if not result.get("outputs"):
        return 2
    diag = result.get("diagnose") or {}
    if diag and diag.get("ok") is False:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
