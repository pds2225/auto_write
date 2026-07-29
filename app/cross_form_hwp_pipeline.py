"""cross_form_hwp_pipeline.py — 공고 HWP/HWPX 양식 채움 단일 진입점.

재발 방지:
- ``--output`` + ``--engine`` + ``--confirm-output-plan`` 필수 (암묵적 DOCX 우회 금지)
- COM 은 ``hancom_com_guard`` 가 2024(HOffice130) 기동을 차단
- 구 스크립트 ``_finish_minwon_rhwp.py`` / ``_complete_minwon_job.py`` 는 사용 금지(래퍼만 유지)

사용 예 (PowerShell)::

    cd D:\\auto_write\\app
    # RHWP — COM 없이 HWPX 채움 (권장, 로그인 없음)
    py -3.11 cross_form_hwp_pipeline.py ^
        --notice-folder "C:\\...\\21_기업민원..." ^
        --engine rhwp-hwpx-fill --output hwpx --confirm-output-plan

    # COM + hwpx_fill — .hwp/.hwpx (한글 2022 COM 등록 필요)
    py -3.11 cross_form_hwp_pipeline.py ^
        --notice-folder "C:\\...\\21_기업민원..." ^
        --engine com-hwpx-fill --output hwpx --output hwp --confirm-output-plan

    # DOCX cross_form (명시적 선택 시만)
    py -3.11 cross_form_hwp_pipeline.py ^
        --notice-folder "C:\\...\\21_기업민원..." ^
        --engine docx-crossform --output docx --confirm-output-plan
"""

from __future__ import annotations

import argparse
import json
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
from auto_write.services.cross_form_autofill import extract_source_fields
from auto_write.services.hwp_docx_convert import hwp_to_docx
from auto_write.services.hwpx_fill import fill_hwpx

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
    addr = pick(rm, pm, mm, keys=("주소", "거주지"))
    if addr:
        ident["주소(거주지)"] = addr
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


def run_pipeline(
    notice_folder: Path,
    plan: OutputPlan,
    *,
    hwpx_base: Path | None = None,
    profile: Path | None = None,
    resume: Path | None = None,
    master: Path | None = None,
    supplement_resume: bool = False,
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
            base = hwpx_base or (work / "10_form_base.hwpx")
            if not base.is_file():
                raise FileNotFoundError(
                    f"HWPX 베이스가 없습니다: {base}. "
                    "한글 2022에서 공고 서식을 HWPX로 저장하거나 --hwpx-base 를 지정하세요."
                )
            out_hwpx = work / "02_filled.hwpx"
            fr = fill_hwpx(base, out_hwpx, identity=identity)
            result["outputs"]["hwpx"] = str(out_hwpx)
            result["filled"] = fr.filled
            result["filled_count"] = fr.filled_count
            if supplement_resume:
                from auto_write.services.hwpx_resume_supplement import supplement_hwpx_from_resume
                from datetime import datetime

                today_fmt = datetime.now().strftime("%Y년  %m월  %d일").replace(" 0", " ")
                sup = supplement_hwpx_from_resume(
                    out_hwpx,
                    out_hwpx,
                    education=[
                        ("2022.03 ~ 현재", "한양대학교", "경영컨설팅학과(석사 재학)"),
                        ("2011.03 ~ 2016.02", "강남대학교", "경영학과(학사)"),
                    ],
                    licenses=[
                        ("경영지도사", "2020.01.01", "12040", "중소벤처기업부"),
                        ("스타트업 액셀러레이터 심사역", "2023.02.07", "23-14", "씨엔티테크"),
                    ],
                    careers=[
                        ("밸류업파트너스", "2022.11 ~ 현재", "대표이사", "컨설팅·자문·사업계획서·IR"),
                        ("한국경영기술지도사회", "2023.02 ~ 현재", "중부지회 이사", "협회 운영"),
                        ("IPO브릿지", "2022.02 ~ 2022.11", "선임컨설턴트", "컨설팅·IR"),
                        ("오케이저축은행", "2020.03 ~ 2021.07", "계장", "기업금융·투자금융"),
                    ],
                    specialty_text="경영전략, 창업·도약",
                    check_columns=[(2, 4, "경영활동 전문상담"), (3, 4, "특화분야 전문상담")],
                    sign_date=today_fmt,
                    sign_name=identity.get("성명", ""),
                )
                result["supplement"] = sup.as_dict()
            (work / "02_fill_report.json").write_text(
                json.dumps(
                    {
                        "engine": "rhwp-hwpx-fill (hwpx_fill, use_com=False)",
                        "output": str(out_hwpx),
                        "filled": fr.filled,
                        "filled_count": fr.filled_count,
                        "residual": fr.residual,
                        "ok": fr.filled_count > 0,
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
        required=True,
        help="산출 형식 (복수 가능). 암묵적 기본값 없음.",
    )
    parser.add_argument(
        "--engine",
        required=True,
        choices=[e.value for e in FillEngine],
        help="채움 엔진. rhwp-hwpx-fill | com-hwpx-fill | docx-crossform",
    )
    parser.add_argument(
        "--confirm-output-plan",
        action="store_true",
        help="출력 형식·엔진 선택을 사용자가 승인했음을 명시 (필수)",
    )
    parser.add_argument("--hwpx-base", type=Path, help="RHWP 타깃 HWPX (기본: _workspace/10_form_base.hwpx)")
    parser.add_argument("--source-profile", type=Path)
    parser.add_argument("--source-resume", type=Path)
    parser.add_argument("--source-master", type=Path)
    parser.add_argument(
        "--supplement-resume",
        action="store_true",
        help="학력·자격·경력·모집분야·서명일 이력서 표 보강(RHWP)",
    )
    args = parser.parse_args(argv)

    try:
        plan = OutputPlan.parse(
            output_names=args.outputs,
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
        )
    except (OutputPolicyError, FileNotFoundError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("outputs") else 2


if __name__ == "__main__":
    raise SystemExit(main())
