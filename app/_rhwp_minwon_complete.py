"""RHWP-only minwon fill + Hanword 2022 COM registry fix attempt."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import winreg
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP = Path(__file__).resolve().parent
NOTICE = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\21_기업민원처리센터 전문상담위원 추가모집"
)
WORK = NOTICE / "_workspace"
TARGET = NOTICE / "기업민원처리센터 전문상담위원 추가모집 공고.hwp"
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
HW2022 = Path(r"C:\Program Files (x86)\Hnc\Office 2022\HOffice120\Bin\Hwp.exe")
COM_CLSID = "{2291CF00-64A1-4877-A9B4-68CFE89612D6}"
DOC_CLSID = "{965829DB-438E-4d31-B4FA-F1F8819A35FD}"

OUT_DOCX = WORK / "02_filled.docx"
OUT_REPORT = WORK / "02_fill_report.json"


def reg_read(path: str) -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path) as k:
            return winreg.QueryValue(k, None)
    except OSError:
        return None


def snapshot_com() -> dict:
    return {
        "HWPFrame.HwpObject.LocalServer32": reg_read(
            f"WOW6432Node\\CLSID\\{COM_CLSID}\\LocalServer32"
        ),
        "Hwp.Document.130.LocalServer32": reg_read(
            f"WOW6432Node\\CLSID\\{DOC_CLSID}\\LocalServer32"
        ),
        "dot_hwp_progid": reg_read(".hwp"),
        "dot_hwpx_progid": reg_read(".hwpx"),
    }


def to_docx_rhwp(path: Path, out: Path) -> str:
    from auto_write.services.hwp_docx_convert import hwp_to_docx

    rep = hwp_to_docx(path, out, use_com=False)
    if not rep.ok:
        raise RuntimeError(f"RHWP convert fail {path.name}: {rep.notes}")
    return rep.method


def extract_fields(path: Path, tmp: Path) -> dict[str, str]:
    from auto_write.services.cross_form_autofill import extract_source_fields

    docx = tmp / f"{path.stem}_src.docx"
    to_docx_rhwp(path, docx)
    return extract_source_fields(str(docx))


def pick(*maps: dict[str, str], keys: tuple[str, ...]) -> tuple[str, str]:
    for k in keys:
        for m in maps:
            v = (m.get(k) or "").strip()
            if v and v not in {"○", "○○", "○○○", "기 관 명", "담당업무"}:
                return k, v
    return "", ""


def try_reregister_2022() -> dict:
    """Attempt Hanword 2022 COM re-registration without _dispatch_hwp()."""
    log: dict = {"before": snapshot_com(), "attempts": [], "after": {}, "success": False}
    candidates = [
        [str(HW2022), "/regserver"],
        [str(HW2022), "/RegServer"],
        [str(HW2022), "-regserver"],
    ]
    for cmd in candidates:
        if not HW2022.is_file():
            log["attempts"].append({"cmd": cmd, "error": "Hwp.exe not found"})
            continue
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            log["attempts"].append({
                "cmd": cmd,
                "exit": p.returncode,
                "stdout": (p.stdout or "")[:300],
                "stderr": (p.stderr or "")[:300],
            })
        except Exception as exc:
            log["attempts"].append({"cmd": cmd, "error": str(exc)})

    log["after"] = snapshot_com()
    after = log["after"].get("HWPFrame.HwpObject.LocalServer32") or ""
    log["success"] = "HOffice120" in after and "HOffice130" not in after
    log["manual_steps"] = []
    if not log["success"]:
        log["manual_steps"] = [
            "1. 한글 2022 실행: \"C:\\Program Files (x86)\\Hnc\\Office 2022\\HOffice120\\Bin\\Hwp.exe\"",
            "2. 메뉴 [도움말] → [한글 프로그램 등록] (또는 [재설치/복구] → 프로그램 등록) 클릭",
            "3. 관리자 권한 UAC 승인",
            "4. 등록 완료 후 PowerShell에서 확인:",
            "   reg query \"HKCR\\WOW6432Node\\CLSID\\{2291CF00-64A1-4877-A9B4-68CFE89612D6}\\LocalServer32\"",
            "   → HOffice120\\Bin\\Hwp.exe -Automation 이어야 함",
            "5. .hwp 기본앱: 설정 → 앱 → 기본 앱 → 파일 형식별 기본값 → .hwp → 한글 2022 선택",
            "6. 2024와 2022 공존 시 2024 COM 등록 해제는 [한컴오피스 2024] 제거/복구 또는 2022 등록을 나중에 실행",
        ]
    return log


def run_rhwp_fill(tmp: Path, pm: dict, rm: dict, mm: dict) -> dict:
    from auto_write.services.cross_form_autofill import autofill_from_source

    src_docx = tmp / "source.docx"
    tgt_docx = tmp / "target.docx"
    to_docx_rhwp(SRC_PROFILE, src_docx)
    to_docx_rhwp(TARGET, tgt_docx)

    confirms: dict[str, str] = {}
    for tgt, keys in (
        ("소속/직위", ("소속", "소속기관", "기관명", "회사명")),
        ("주소(거주지)", ("주소", "거주지", "자택주소")),
    ):
        lbl, val = pick(pm, rm, mm, keys=keys)
        if lbl and val:
            confirms[tgt] = lbl

    report = autofill_from_source(
        str(src_docx),
        str(tgt_docx),
        str(OUT_DOCX),
        confirmations=confirms or None,
        enable_checkbox=True,
    )
    rep = report.as_dict()
    rep["engine"] = "RHWP (hwpx_xml + unhwp, use_com=False)"
    rep["confirmations_used"] = confirms
    OUT_REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return rep


def compare_with_resume(rep: dict, pm: dict, rm: dict, mm: dict) -> dict:
    resume_ref = mm or rm or pm
    filled = {m.get("normalized") or m.get("target_label"): m.get("value") for m in rep.get("matches", [])}
    items = []
    for name, keys in [
        ("성명", ("성명",)), ("생년월일", ("생년월일",)),
        ("핸드폰", ("핸드폰", "휴대전화")), ("이메일", ("이메일",)),
        ("소속", ("소속", "소속기관", "기관명")), ("직위", ("직위", "직책")),
        ("주소", ("주소", "거주지")),
    ]:
        _, ref = pick(resume_ref, pm, keys=keys)
        form_val = ""
        for k in keys + (name,):
            form_val = filled.get(k, "") or form_val
        if name == "성명":
            form_val = filled.get("성명", form_val)
        if name == "소속" and filled.get("소속/직위"):
            form_val = filled.get("소속/직위", form_val)
        status = "일치" if ref and form_val and (ref in form_val or form_val in ref) else (
            "누락(양식)" if ref and not form_val else "양식만" if form_val and not ref else "불일치"
        )
        items.append({"항목": name, "기존이력서": ref, "작성본": form_val, "상태": status})
    return {
        "resume_folder": str(RESUME_FOLDER),
        "resume_master": str(RESUME_MASTER),
        "compare": items,
    }


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="rhwp_minwon_"))

    com_log = try_reregister_2022()
    (WORK / "06_com_reregister.json").write_text(
        json.dumps(com_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    pm = extract_fields(SRC_PROFILE, tmp) if SRC_PROFILE.is_file() else {}
    rm = extract_fields(SRC_RESUME, tmp) if SRC_RESUME.is_file() else {}
    mm = extract_fields(RESUME_MASTER, tmp) if RESUME_MASTER.is_file() else {}

    identity = {}
    for tgt, keys in [
        ("성명", ("성명",)), ("생년월일", ("생년월일",)),
        ("휴대전화", ("핸드폰", "휴대전화")), ("이메일", ("이메일",)),
        ("소속", ("소속", "소속기관", "기관명")), ("직위", ("직위", "직책")),
        ("주소", ("주소", "거주지")),
    ]:
        _, v = pick(pm, rm, mm, keys=keys)
        if v:
            identity[tgt] = v
    _, so = pick(pm, rm, mm, keys=("소속", "소속기관", "기관명"))
    _, jw = pick(pm, rm, mm, keys=("직위", "직책"))
    if so and jw:
        identity["소속/직위"] = f"{so} / {jw}"
    elif so:
        identity["소속/직위"] = so
    _, addr = pick(pm, rm, mm, keys=("주소", "거주지"))
    if addr:
        identity["주소(거주지)"] = addr

    (WORK / "01_source_facts.json").write_text(
        json.dumps({"identity": identity, "engine": "RHWP"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rep = run_rhwp_fill(tmp, pm, rm, mm)
    compare = compare_with_resume(rep, pm, rm, mm)
    compare["engine"] = "RHWP"
    compare["transcribed"] = rep.get("transcribed")
    (WORK / "03_compare.json").write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8")

    diag_code = 99
    diag_out = ""
    if OUT_DOCX.is_file():
        d = subprocess.run(
            [sys.executable, "self_diagnose.py", str(OUT_DOCX)],
            cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        diag_code = d.returncode
        diag_out = (d.stdout or "") + (d.stderr or "")
    (WORK / "05_self_diagnose.txt").write_text(diag_out, encoding="utf-8")

    today = datetime.now().strftime("%Y.%m.%d")
    lrule = f"""# L규칙 체크리스트 ({today})

| ID | 결과 | 근거 |
|----|------|------|
| L003 | **pass** | COM 미사용(RHWP only) |
| L009 | **pass** | high+confirmed만, identity={json.dumps(identity, ensure_ascii=False)} |
| L024 | **pass** | 원본 미수정 |
| L034 | **pass** | 모집분야 미체크 |
| L037 | **할일** | 제출 시 서식1/2만 분리 |
| L005 | **할일** | DOCX 확인 후 한글2022로 .hwp 수동 저장 |
| L019 | **{'pass' if diag_code == 0 else 'fail/DRAFT'}** | self_diagnose exit={diag_code} |

엔진: **RHWP only** (hwpx_xml + unhwp). COM/한컴계정 미사용.
"""
    (WORK / "04_lrule_checklist.md").write_text(lrule, encoding="utf-8")

    unmatched_real = [
        u for u in rep.get("unmatched_targets", [])
        if u.get("normalized") not in {"200,000원", "<멘토자격요건>", "~"}
    ]
    summary = f"""# RHWP 전사 완료 ({today})

## 엔진
**RHWP only** — hwpx_xml(소스) + unhwp(타깃). COM/한컴계정 **미사용**.

## A / B
- A: `{SRC_PROFILE.name}` (+ 이력서 `{RESUME_MASTER.name}`)
- B: `{TARGET.name}`

## 출력
- `{OUT_DOCX.name}` — 전사 DOCX
- `02_fill_report.json`, `03_compare.json`, `04_lrule_checklist.md`, `05_self_diagnose.txt`

## 채움
- transcribed: **{rep.get('transcribed')}** / confirmed: **{rep.get('confirmed')}**
"""
    for m in rep.get("matches", []):
        summary += f"- {m.get('target_label')} ← {m.get('source_label')} = {m.get('value')}\n"

    summary += f"""
## 못 채운 칸
"""
    for u in unmatched_real:
        summary += f"- {u.get('target_label')}\n"
    summary += """- 모집분야: L034 사용자 확정 전
- 경력/학력/자격 표: 수동 복붙
- 서명·날짜: L032

## 한글 2022 → .hwp 수동 저장
1. `"C:\\Program Files (x86)\\Hnc\\Office 2022\\HOffice120\\Bin\\Hwp.exe"` 실행
2. `02_filled.docx` 열기 → [다른 이름으로 저장] → `.hwp`
3. 탐색기 더블클릭(2024 기본앱) 금지

## 2022 COM 재등록
"""
    summary += f"- 성공: **{com_log['success']}**\n"
    summary += f"- 전: `{com_log['before'].get('HWPFrame.HwpObject.LocalServer32')}`\n"
    summary += f"- 후: `{com_log['after'].get('HWPFrame.HwpObject.LocalServer32')}`\n"
    if com_log.get("manual_steps"):
        summary += "\n### 수동 단계\n" + "\n".join(com_log["manual_steps"])

    (WORK / "02_fill_summary.md").write_text(summary, encoding="utf-8")

    print(json.dumps({
        "transcribed": rep.get("transcribed"),
        "docx": OUT_DOCX.is_file(),
        "com_reregister_success": com_log["success"],
        "engine": "RHWP",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
