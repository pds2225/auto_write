"""Extract source fields + second-pass fill with confirmations."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from auto_write.services.cross_form_autofill import extract_source_fields, autofill_from_source
from auto_write.services.hwp_docx_convert import hwp_to_docx

NOTICE = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\21_기업민원처리센터 전문상담위원 추가모집")
WS = NOTICE / "_workspace"
TARGET = NOTICE / "기업민원처리센터 전문상담위원 추가모집 공고.hwp"
SOURCES = [
    Path(r"C:\Users\ekth3\OneDrive\바탕 화면\프로필 양식_박다솜_v5.hwpx"),
    Path(r"C:\Users\ekth3\OneDrive\바탕 화면\1. 이력서 박다솜 20250308 서울창조경제혁신센터 초기창업패키지 평가위원.hwp"),
]

def to_docx(p: Path) -> Path:
    if p.suffix.lower() == ".docx":
        return p
    out = Path(tempfile.mkdtemp()) / (p.stem + ".docx")
    rep = hwp_to_docx(p, out)
    if not rep.ok:
        raise RuntimeError(rep.notes)
    return out

all_fields = {}
for s in SOURCES:
    if not s.is_file():
        continue
    d = to_docx(s)
    f = extract_source_fields(str(d))
    all_fields[s.name] = f

print(json.dumps(all_fields, ensure_ascii=False, indent=2))

# high-confidence extra mappings from profile/resume labels
confirm = {}
prof = all_fields.get("프로필 양식_박다솜_v5.hwpx", {})
resume = all_fields.get("1. 이력서 박다솜 20250308 서울창조경제혁신센터 초기창업패키지 평가위원.hwp", {})

mapping = [
    ("소속/직위", "소속"),
    ("주소(거주지)", "주소"),
]
for tgt, src_key in mapping:
    for src in (prof, resume):
        for k, v in src.items():
            if src_key in k and v.strip():
                confirm[tgt] = k
                break
        if tgt in confirm:
            break

print("\nCONFIRM:", json.dumps(confirm, ensure_ascii=False))

if confirm:
    rep = autofill_from_source(
        str(SOURCES[0]), str(TARGET), str(WS / "02_filled.docx"),
        confirmations={t: s for t, s in confirm.items()},
        enable_checkbox=True,
    )
    data = rep.as_dict()
    (WS / "02_fill_report.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"transcribed": data["transcribed"], "matches": data["matches"]}, ensure_ascii=False, indent=2))
