"""한컴 로그인 팝업 원인 진단 — COM/설치/연결 조사 (HWP 실행 없음)."""
from __future__ import annotations

import json
import sys
import winreg
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROGIDS = [
    "HWPFrame.HwpObject",
    "HWPFrame.HwpObject.1",
    "HncOffice.Hwp",
    "HWPApplication.HwpObject",
]

CANDIDATES = [
    r"C:\Program Files (x86)\Hnc\Office 2022\HOffice120\Bin\Hwp.exe",
    r"C:\Program Files (x86)\Hnc\Office 2022\HOffice110\Bin\Hwp.exe",
    r"C:\Program Files (x86)\Hnc\Office 2024\HOffice130\Bin\Hwp.exe",
    r"C:\Program Files (x86)\Hnc\Office 2020\HOffice100\Bin\Hwp.exe",
    r"C:\Program Files (x86)\Hnc\HOffice10\Bin\Hwp.exe",
    r"C:\Program Files (x86)\Hnc\Hwp80\Hwp.exe",
]


def reg_get(root, sub, name=None):
    try:
        with winreg.OpenKey(root, sub) as k:
            if name:
                return winreg.QueryValueEx(k, name)[0]
            return winreg.QueryValue(k)
    except OSError:
        return None


def resolve_progid(progid: str) -> dict:
    out = {"progid": progid, "registered": False}
    clsid = reg_get(winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID")
    if not clsid:
        return out
    out["registered"] = True
    out["clsid"] = clsid
    out["inproc"] = reg_get(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}\\InprocServer32")
    out["localserver"] = reg_get(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}\\LocalServer32")
    out["version"] = reg_get(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}\\Version")
    return out


def hwp_assoc() -> dict:
    out = {}
    for ext in (".hwp", ".hwpx"):
        progid = reg_get(winreg.HKEY_CLASSES_ROOT, ext)
        out[ext] = {"progid": progid}
        if progid:
            cmd = reg_get(
                winreg.HKEY_CLASSES_ROOT,
                f"{progid}\\shell\\open\\command",
            )
            out[ext]["open_command"] = cmd
    return out


def scan_hnc_dirs() -> list[dict]:
    found = []
    for base in [Path(r"C:\Program Files (x86)\Hnc"), Path(r"C:\Program Files\Hnc")]:
        if not base.is_dir():
            continue
        for p in base.rglob("Hwp.exe"):
            found.append({
                "path": str(p),
                "size": p.stat().st_size,
                "parent": p.parent.name,
            })
    return found


def main() -> None:
    report = {
        "progids": [resolve_progid(p) for p in PROGIDS],
        "hwp_file_assoc": hwp_assoc(),
        "hwp_exe_candidates": [],
        "installed_hnc_scan": scan_hnc_dirs(),
        "code_paths_that_invoke_com": [
            "hwp_docx_convert._dispatch_hwp → win32.Dispatch('HWPFrame.HwpObject')",
            "hwp_com_fill.fill_hwp_via_hwpx → _convert_via_com (HWP↔HWPX)",
            "hwp_com_fill.fill_hwp_com → _dispatch_hwp",
            "cross_form_autofill._to_docx_if_needed → hwp_to_docx(use_com=True default)",
            "hwp_fill.py → hwp_to_docx(use_com=True)",
            "hwp_docx.py convert → use_com default True",
            "_complete_minwon_job.py → fill_hwp_via_hwpx(use_com=True)",
            "_run_fill_job.py → autofill_from_source (COM if hwp target)",
        ],
        "code_paths_no_com": [
            "hwp_to_docx(use_com=False) → unhwp/hwpx_xml (pure Python, no login)",
            "hwpx_fill.fill_hwpx → ZIP/XML direct",
            "cross_form previous report: target converted via unhwp (no COM)",
        ],
        "os_startfile_risk": "notice_pipeline._open_folder → os.startfile(folder) opens Explorer, not HWP",
    }

    for c in CANDIDATES:
        p = Path(c)
        report["hwp_exe_candidates"].append({"path": c, "exists": p.is_file()})

    # LocalServer32 → 실제 COM이 기동하는 exe
    for item in report["progids"]:
        if item.get("localserver"):
            report["com_localserver"] = item["localserver"]
            break

    out = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\21_기업민원처리센터 전문상담위원 추가모집\_workspace\00_hancom_diag.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
