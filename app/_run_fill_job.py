"""One-shot job: list folders, run cross_form_fill, save report."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NOTICE = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\21_기업민원처리센터 전문상담위원 추가모집"
)
WORKSPACE = NOTICE / "_workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

TARGET = NOTICE / "기업민원처리센터 전문상담위원 추가모집 공고.hwp"
SOURCES = [
    Path(r"C:\Users\ekth3\OneDrive\바탕 화면\프로필 양식_박다솜_v5.hwpx"),
    Path(r"C:\Users\ekth3\OneDrive\바탕 화면\1. 이력서 박다솜 20250308 서울창조경제혁신센터 초기창업패키지 평가위원.hwp"),
    Path(r"C:\Users\ekth3\OneDrive\바탕 화면\노트북(다솜) 백업 20231222\다솜\개인\★이력서\01. 경영지도사 이력서\이력서 박다솜 20230804.hwp"),
]

RESUME_DIRS = [
    Path(r"C:\Users\ekth3\OneDrive\바탕 화면\노트북(다솜) 백업 20231222\다솜\개인\★이력서"),
    Path(r"C:\Users\ekth3\OneDrive\바탕 화면"),
]


def list_resume_files() -> list[dict]:
    out = []
    seen = set()
    for base in RESUME_DIRS:
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".hwp", ".hwpx", ".docx", ".pdf"}:
                continue
            if "이력서" not in p.name and "프로필" not in p.name and "박다솜" not in p.name:
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                out.append({"path": str(p), "name": p.name, "size": p.stat().st_size})
            except OSError:
                pass
    out.sort(key=lambda x: x["name"])
    return out


def main() -> int:
    info = {
        "notice_files": [],
        "target_exists": TARGET.is_file(),
        "target": str(TARGET),
        "sources_exist": {str(s): s.is_file() for s in SOURCES},
        "resume_files": list_resume_files(),
    }
    if NOTICE.is_dir():
        for f in NOTICE.iterdir():
            if f.is_file():
                info["notice_files"].append({"name": f.name, "size": f.stat().st_size})

    (WORKSPACE / "00_inventory.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(info, ensure_ascii=False, indent=2))

    if not TARGET.is_file():
        print("ERROR: target missing", file=sys.stderr)
        return 1

    source = next((s for s in SOURCES if s.is_file()), None)
    if not source:
        print("ERROR: no source found", file=sys.stderr)
        return 1

    from auto_write.services.cross_form_autofill import autofill_from_source

    out_docx = WORKSPACE / "02_filled.docx"
    out_hwp = WORKSPACE / "02_filled.hwp"
    report = autofill_from_source(
        str(source),
        str(TARGET),
        str(out_docx),
        enable_checkbox=True,
    )
    rep = report.as_dict()
    (WORKSPACE / "02_fill_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== AUTOFILL REPORT ===")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
