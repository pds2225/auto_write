"""Complete fill + HWP export + field compare. Local Hangeul COM only."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NOTICE = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\21_기업민원처리센터 전문상담위원 추가모집"
)
WS = NOTICE / "_workspace"
WS.mkdir(parents=True, exist_ok=True)

TARGET = NOTICE / "기업민원처리센터 전문상담위원 추가모집 공고.hwp"
SOURCE = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\프로필 양식_박다솜_v5.hwpx")
SOURCE2 = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\1. 이력서 박다솜 20250308 "
    r"서울창조경제혁신센터 초기창업패키지 평가위원.hwp"
)
RESUME_DIR = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\01. 경영지도사 이력서")

OUT_DOCX = WS / "02_filled.docx"
OUT_HWP = WS / "02_filled.hwp"
REPORT_JSON = WS / "02_fill_report.json"


def kill_hwp() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Stop-Process -Name Hwp -Force -ErrorAction SilentlyContinue"],
        check=False,
    )


def run_fill(source: Path) -> dict:
    from auto_write.services.cross_form_autofill import autofill_from_source

    rep = autofill_from_source(str(source), str(TARGET), str(OUT_DOCX), enable_checkbox=True)
    data = rep.as_dict()
    REPORT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def export_hwp() -> dict:
    kill_hwp()
    from auto_write.services.hwp_docx_convert import docx_to_hwp

    conv = docx_to_hwp(OUT_DOCX, OUT_HWP)
    return {"ok": conv.ok, "notes": conv.notes, "output": str(OUT_HWP)}


def extract_fields(path: Path) -> dict[str, str]:
    from auto_write.services.cross_form_autofill import extract_source_fields
    from auto_write.services.hwp_docx_convert import hwp_to_docx
    import tempfile

    try:
        p = path
        tmp_docx = None
        if p.suffix.lower() in {".hwp", ".hwpx"}:
            tmp = Path(tempfile.mkdtemp()) / (p.stem + ".docx")
            rep = hwp_to_docx(p, tmp)
            if not rep.ok:
                return {"_error": "; ".join(rep.notes or ["hwp convert fail"])}
            p = tmp
            tmp_docx = tmp
        fields = extract_source_fields(str(p))
        if tmp_docx and tmp_docx.exists():
            tmp_docx.unlink(missing_ok=True)
        return fields
    except Exception as exc:
        return {"_error": str(exc)}


def compare_fields(filled: dict, refs: list[tuple[str, dict]]) -> list[dict]:
    key_labels = ["성명", "이름", "연락처", "휴대폰", "전화", "이메일", "E-mail", "소속", "직위", "학력", "경력"]
    rows = []
    for label in key_labels:
        filled_val = next((v for k, v in filled.items() if label in k), "")
        for ref_name, ref_fields in refs:
            ref_val = next((v for k, v in ref_fields.items() if label in k), "")
            if not ref_val and not filled_val:
                continue
            status = "일치" if filled_val and ref_val and filled_val.strip() == ref_val.strip() else (
                "누락(양식)" if ref_val and not filled_val else
                "누락(소스)" if filled_val and not ref_val else "불일치"
            )
            rows.append({
                "항목": label,
                "기준파일": ref_name,
                "기존값": ref_val,
                "양식값": filled_val,
                "상태": status,
            })
    return rows


def main() -> int:
    if not TARGET.is_file():
        print("TARGET missing", file=sys.stderr)
        return 1
    src = SOURCE if SOURCE.is_file() else SOURCE2
    if not src.is_file():
        print("SOURCE missing", file=sys.stderr)
        return 1

    print(f"SOURCE={src}")
    print(f"TARGET={TARGET}")
    fill = run_fill(src)
    print(json.dumps({"transcribed": fill.get("transcribed"), "ok": fill.get("ok")}, ensure_ascii=False))

    hwp = export_hwp()
    print(json.dumps(hwp, ensure_ascii=False))

    filled_fields = extract_fields(OUT_DOCX)
    ref_files = []
    for p in [SOURCE, SOURCE2]:
        if p.is_file():
            ref_files.append((p.name, extract_fields(p)))
    if RESUME_DIR.is_dir():
        for p in sorted(RESUME_DIR.rglob("이력서 박다솜*.hwp"), key=lambda x: x.stat().st_mtime, reverse=True)[:3]:
            ref_files.append((p.name, extract_fields(p)))

    cmp = compare_fields(filled_fields, ref_files)
    cmp_path = WS / "03_compare.json"
    cmp_path.write_text(json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(cmp[:30], ensure_ascii=False, indent=2))
    return 0 if fill.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
