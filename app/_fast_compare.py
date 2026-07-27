"""Fast compare using existing filled docx + hwpx source only."""
import json, sys, zipfile, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

WS = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625\21_기업민원처리센터 전문상담위원 추가모집\_workspace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_write.services.cross_form_autofill import extract_source_fields

FILLED = WS / "02_filled.docx"
PROFILE = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\프로필 양식_박다솜_v5.hwpx")
RESUME = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\1. 이력서 박다솜 20250308 서울창조경제혁신센터 초기창업패키지 평가위원.hwp")
RESUME_DIR = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\01. 경영지도사 이력서")

def hwpx_text(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        parts = [z.read(n).decode("utf-8", errors="replace") for n in z.namelist() if n.endswith(".xml")]
    return re.sub(r"<[^>]+>", " ", " ".join(parts))

filled = extract_source_fields(str(FILLED))
report = json.loads((WS / "02_fill_report.json").read_text(encoding="utf-8"))

# profile via docx convert cache if exists else key fields from report matches
refs = {}
if PROFILE.is_file():
    import tempfile
    from auto_write.services.hwp_docx_convert import hwp_to_docx
    tmp = Path(tempfile.mkdtemp()) / "p.docx"
    hwp_to_docx(PROFILE, tmp)
    refs["프로필_v5"] = extract_source_fields(str(tmp))

keys = ["성명", "생년월일", "휴대", "핸드폰", "전화", "이메일", "주소", "소속", "직위", "학력", "경력"]
rows = []
for k in keys:
    fv = next((v for lk,v in filled.items() if k in lk), "")
    for rn, rf in refs.items():
        rv = next((v for lk,v in rf.items() if k in lk), "")
        if not fv and not rv:
            continue
        st = "일치" if fv and rv and fv.strip()==rv.strip() else ("누락(양식)" if rv and not fv else "불일치" if fv and rv else "양식만")
        rows.append({"항목":k,"기준":rn,"기존":rv,"양식":fv,"상태":st})

out = {"matches": report.get("matches"), "unmatched_count": len(report.get("unmatched_targets",[])), "compare": rows}
(WS / "03_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
