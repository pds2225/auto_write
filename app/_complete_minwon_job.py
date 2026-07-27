"""기업민원처리센터 — 로컬 한글2022 COM + RHWP(hwpx_fill) 전용 완료 스크립트.

한컴계정/웹/클라우드 경로 사용 금지.
- 소스 추출: hwpx_xml (RHWP, COM 없음)
- .hwp 변환·채움: HWPFrame.HwpObject 로컬 COM (Office 2022 HOffice120)
- 표 칸 채움: hwpx_fill (RHWP)
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP = Path(__file__).resolve().parent
NOTICE_DIR = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\21_기업민원처리센터 전문상담위원 추가모집"
)
WORK = NOTICE_DIR / "_workspace"
TARGET = NOTICE_DIR / "기업민원처리센터 전문상담위원 추가모집 공고.hwp"
SRC_PROFILE = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\프로필 양식_박다솜_v5.hwpx")
SRC_RESUME = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\1. 이력서 박다솜 20250308 "
    r"서울창조경제혁신센터 초기창업패키지 평가위원.hwp"
)
RESUME_MASTER = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\노트북(다솜) 백업 20231222\다솜\개인\★이력서"
    r"\01. 경영지도사 이력서\이력서 박다솜 20230804.hwp"
)
RESUME_FOLDER = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\01. 경영지도사 이력서"
)
HANWORD2022 = Path(r"C:\Program Files (x86)\Hnc\Office 2022\HOffice120\Bin\Hwp.exe")

OUT_HWP = WORK / "02_filled.hwp"
OUT_HWPX = WORK / "02_filled.hwpx"
OUT_DOCX = WORK / "02_filled.docx"
ENGINES_LOG = WORK / "00_engines.json"


def stop_hwp() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Stop-Process -Name Hwp -Force -ErrorAction SilentlyContinue"],
        capture_output=True,
    )


def to_docx_rhwp(path: Path, out: Path) -> str:
    """COM/unhwp 없이 RHWP 경로만."""
    from auto_write.services.hwp_docx_convert import hwp_to_docx

    ext = path.suffix.lower()
    if ext == ".docx":
        return "docx_native"
    rep = hwp_to_docx(path, out, use_com=False)
    if not rep.ok:
        raise RuntimeError(f"RHWP 변환 실패 {path.name}: {rep.notes}")
    return rep.method  # hwpx_xml or unhwp


def to_docx_local_com(path: Path, out: Path) -> str:
    """로컬 한글2022 COM만 (한컴계정/웹 없음)."""
    from auto_write.services.hwp_docx_convert import hwp_to_docx, hancom_com_available

    if not hancom_com_available():
        raise RuntimeError("로컬 HWPFrame.HwpObject COM 미등록 — 한글 2022 설치 확인")
    stop_hwp()
    rep = hwp_to_docx(path, out, use_com=True)
    if not rep.ok or rep.method != "hancom_com":
        raise RuntimeError(f"로컬 COM 변환 실패: method={rep.method} notes={rep.notes}")
    return "hancom_com"


def extract_fields_rhwp(path: Path, tmp: Path) -> dict[str, str]:
    from auto_write.services.cross_form_autofill import extract_source_fields

    docx = tmp / (path.stem + "_src.docx")
    method = to_docx_rhwp(path, docx)
    fields = extract_source_fields(str(docx))
    return fields, method


def pick(*maps: dict[str, str], keys: tuple[str, ...]) -> tuple[str, str]:
    for k in keys:
        for m in maps:
            v = (m.get(k) or "").strip()
            if v and v not in {"○", "○○", "○○○", "기 관 명", "담당업무"}:
                return k, v
    return "", ""


def build_identity(pm: dict, rm: dict, mm: dict) -> dict[str, str]:
    ident: dict[str, str] = {}
    mapping = [
        ("성명", ("성명", "성명(국문)", "이름")),
        ("성명(국문)", ("성명", "성명(국문)")),
        ("생년월일", ("생년월일",)),
        ("휴대전화", ("핸드폰", "휴대전화", "휴대폰", "연락처")),
        ("핸드폰", ("핸드폰", "휴대전화")),
        ("이메일", ("이메일", "E-mail")),
        ("이 메 일", ("이메일",)),
        ("소속", ("소속", "소속기관", "기관명", "회사명")),
        ("직위", ("직위", "직책", "직급")),
        ("소속/직위", ("소속/직위",)),  # filled below
        ("주소", ("주소", "거주지", "자택주소")),
        ("주소(거주지)", ("주소", "거주지")),
    ]
    for tgt, keys in mapping:
        if tgt == "소속/직위":
            continue
        _, v = pick(pm, rm, mm, keys=keys)
        if v:
            ident[tgt] = v
    _, so = pick(pm, rm, mm, keys=("소속", "소속기관", "기관명", "회사명"))
    _, jw = pick(pm, rm, mm, keys=("직위", "직책", "직급"))
    if so and jw:
        ident["소속/직위"] = f"{so} / {jw}"
    elif so:
        ident["소속/직위"] = so
    return ident


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    engines: dict = {
        "hanword2022_exe": str(HANWORD2022) if HANWORD2022.is_file() else "NOT_FOUND",
        "com_progid": "HWPFrame.HwpObject",
        "hancom_account_used": False,
        "steps": [],
    }

    tmp = Path(tempfile.mkdtemp(prefix="minwon_rhwp_"))

    # 1) 소스 추출 — RHWP only
    pm, pm_m = extract_fields_rhwp(SRC_PROFILE, tmp) if SRC_PROFILE.is_file() else ({}, "")
    rm, rm_m = extract_fields_rhwp(SRC_RESUME, tmp) if SRC_RESUME.is_file() else ({}, "")
    mm, mm_m = extract_fields_rhwp(RESUME_MASTER, tmp) if RESUME_MASTER.is_file() else ({}, "")
    engines["steps"].append({"phase": "source_extract", "engines": [pm_m, rm_m, mm_m]})

    identity = build_identity(pm, rm, mm)
    facts = {k: v for k, v in identity.items() if k in {
        "성명", "생년월일", "휴대전화", "이메일", "소속/직위", "주소(거주지)", "소속", "직위", "주소"
    }}
    (WORK / "01_source_facts.json").write_text(
        json.dumps({"identity": identity, "facts": facts, "profile_method": pm_m}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 2) HWP 채움 — 로컬 COM + hwpx_fill
    stop_hwp()
    from auto_write.services.hwp_com_fill import fill_hwp_via_hwpx

    hwp_rep = fill_hwp_via_hwpx(
        TARGET,
        OUT_HWP,
        identity=identity,
        use_com=True,
    )
    engines["steps"].append({
        "phase": "hwp_fill",
        "engine": "한글2022 COM (HWP↔HWPX) + hwpx_fill (RHWP)",
        "filled_count": hwp_rep.filled_count,
        "filled": hwp_rep.filled,
        "notes": hwp_rep.notes,
        "structure_preserved": hwp_rep.structure_preserved,
    })

    # HWPX 사본도 보존(한글 없이 열람 가능)
    if OUT_HWP.is_file():
        stop_hwp()
        from auto_write.services.hwp_docx_convert import _convert_via_com, _SAVE_FORMATS
        try:
            _convert_via_com(OUT_HWP, OUT_HWPX, _SAVE_FORMATS[".hwpx"])
            engines["steps"].append({"phase": "hwpx_export", "engine": "hancom_com"})
        except Exception as exc:
            engines["steps"].append({"phase": "hwpx_export", "error": str(exc)})

    # 3) DOCX 중간본 — cross_form (타깃은 로컬 COM 변환)
    stop_hwp()
    confirms = []
    for tgt, keys in (("소속/직위", ("소속", "소속기관", "기관명")),
                      ("주소(거주지)", ("주소", "거주지"))):
        lbl, _ = pick(pm, rm, mm, keys=keys)
        if lbl:
            confirms.append(f"{tgt}={lbl}")

    cmd = [
        sys.executable, "cross_form_fill.py",
        "--source", str(SRC_PROFILE),
        "--target", str(TARGET),
        "-o", str(OUT_DOCX),
        "--json",
    ]
    for c in confirms:
        cmd.extend(["--confirm", c])

    # cross_form 내부 hwp 변환은 COM 우선 — 사전에 COM docx 생성해 두면 unhwp 폴백 방지
    tgt_docx = tmp / "target_com.docx"
    try:
        com_method = to_docx_local_com(TARGET, tgt_docx)
        engines["steps"].append({"phase": "target_com_convert", "engine": com_method})
        cmd[cmd.index(str(TARGET))] = str(tgt_docx)
    except Exception as exc:
        engines["steps"].append({"phase": "target_com_convert", "error": str(exc), "fallback": "cross_form native"})

    p = subprocess.run(cmd, cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace")
    engines["steps"].append({"phase": "cross_form_fill", "exit": p.returncode, "stdout_tail": (p.stdout or "")[-800:]})

    report = {}
    rp = WORK / "02_fill_report.json"
    if rp.is_file():
        report = json.loads(rp.read_text(encoding="utf-8"))
    report["engines"] = engines["steps"]
    report["hwp_direct_fill"] = {
        "filled_count": hwp_rep.filled_count,
        "filled": hwp_rep.filled,
        "residual": hwp_rep.residual,
    }
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4) self_diagnose (DOCX)
    diag_out = ""
    diag_code = 99
    if OUT_DOCX.is_file():
        d = subprocess.run(
            [sys.executable, "self_diagnose.py", str(OUT_DOCX)],
            cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        diag_code = d.returncode
        diag_out = (d.stdout or "") + (d.stderr or "")
    (WORK / "05_self_diagnose.txt").write_text(diag_out, encoding="utf-8")

    # 5) 기존 이력서 비교
    resume_ref = mm or rm or pm
    filled_vals = {m.get("normalized") or m.get("target_label"): m.get("value") for m in report.get("matches", [])}
    filled_vals.update(hwp_rep.filled or {})

    compare_items = []
    for name, keys in [
        ("성명", ("성명",)), ("생년월일", ("생년월일",)),
        ("핸드폰", ("핸드폰", "휴대전화")), ("이메일", ("이메일",)),
        ("소속", ("소속", "소속기관", "기관명")), ("직위", ("직위", "직책")),
        ("주소", ("주소", "거주지")),
    ]:
        _, ref = pick(resume_ref, pm, keys=keys)
        form_val = ""
        for k in keys + (name,):
            form_val = filled_vals.get(k, "") or form_val
        if name == "성명":
            form_val = filled_vals.get("성명", form_val) or identity.get("성명", "")
        status = "일치" if ref and form_val and (ref in form_val or form_val in ref) else (
            "누락(양식)" if ref and not form_val else "양식만" if form_val and not ref else "불일치"
        )
        compare_items.append({"항목": name, "기존이력서": ref, "작성본": form_val, "상태": status})

    compare = {
        "resume_folder": str(RESUME_FOLDER),
        "resume_master": str(RESUME_MASTER),
        "compare": compare_items,
        "hwp_filled_count": hwp_rep.filled_count,
        "cross_form_transcribed": report.get("transcribed"),
    }
    (WORK / "03_compare.json").write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8")

    engines["hancom_account_used"] = False
    engines["summary"] = "한글2022 COM (HOffice120) + hwpx_fill(RHWP) + hwpx_xml(RHWP). 한컴계정/웹 미사용."
    ENGINES_LOG.write_text(json.dumps(engines, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6) L-rule + summary
    today = datetime.now().strftime("%Y.%m.%d")
    lrule = f"""# L규칙 체크리스트

| ID | 결과 | 근거 |
|----|------|------|
| L003 | **pass** | Stop-Process Hwp 후 로컬 COM |
| L009 | **pass** | identity={json.dumps(facts, ensure_ascii=False)} |
| L034 | **pass** | 모집분야 미체크 |
| L037 | **할일** | 제출 시 서식1/2만 분리 |
| L005 | **할일** | `{OUT_HWP.name}` 한글2022로 열람 |
| L019 | **{'pass' if diag_code == 0 else 'fail/DRAFT'}** | self_diagnose exit={diag_code} |

## 사용 엔진
- 한글2022: `{HANWORD2022}` (COM ProgID HWPFrame.HwpObject)
- hwpx_fill (RHWP), hwpx_xml/unhwp (RHWP, COM 없음)
- **한컴계정/웹/클라oud: 미사용**
"""
    (WORK / "04_lrule_checklist.md").write_text(lrule, encoding="utf-8")

    summary = f"""# 전사 완료 보고 ({today})

## 사용 엔진 (한컴계정 **미사용**)
- **한글2022 COM**: `{HANWORD2022}` — HWP↔HWPX 변환
- **hwpx_fill (RHWP)**: 표 칸 직접 채움
- **hwpx_xml (RHWP)**: 프로필/이력서 필드 추출

## A / B
- A: `{SRC_PROFILE.name}` (+ 이력서 비교용)
- B: `{TARGET.name}` (공고+서식1+서식2)

## 출력
- `{OUT_HWP.name}` — **제출용 HWP** (로컬 COM+hwpx_fill)
- `{OUT_HWPX.name}` — HWPX 사본 (있으면)
- `{OUT_DOCX.name}` — DOCX 중간본
- `02_fill_report.json`, `03_compare.json`, `04_lrule_checklist.md`, `00_engines.json`

## 채움 결과
- hwpx_fill 직접: **{hwp_rep.filled_count}**칸 — {json.dumps(hwp_rep.filled, ensure_ascii=False)}
- cross_form transcribed: **{report.get('transcribed', 0)}**

## 못 채운 칸
- 모집분야: L034 사용자 확정 전 체크 금지
- 경력/학력/자격 표: 양식 구조상 수동 복붙 필요
- 서명·날짜: L032

## 다음 액션
1. **한글 2022**로 `{OUT_HWP}` 열기 (웹/한컴계정 금지)
2. 모집분야 확정 → `--check` 또는 수동 체크
3. 경력·학력 표는 기존 이력서에서 복사
"""
    (WORK / "02_fill_summary.md").write_text(summary, encoding="utf-8")

    print(json.dumps({
        "ok": OUT_HWP.is_file(),
        "hwp_filled": hwp_rep.filled_count,
        "cross_transcribed": report.get("transcribed"),
        "engine": engines["summary"],
    }, ensure_ascii=False, indent=2))
    return 0 if OUT_HWP.is_file() else 2


if __name__ == "__main__":
    raise SystemExit(main())
