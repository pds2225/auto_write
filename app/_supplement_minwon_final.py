"""민원 신청서 HWPX 최종 보강 — fill + resume supplement (RHWP, COM 없음)."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parent
NOTICE = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\21_기업민원처리센터 전문상담위원 추가모집"
)
WORK = NOTICE / "_workspace"
BASE = WORK / "10_form_base.hwpx"
OUT = WORK / "02_filled.hwpx"
PROFILE = Path(r"C:\Users\ekth3\OneDrive\바탕 화면\프로필 양식_박다솜_v5.hwpx")

sys.path.insert(0, str(APP))


def main() -> int:
    from cross_form_hwp_pipeline import _extract_identity, _to_docx_rhwp
    from auto_write.services.hwpx_fill import fill_hwpx
    from auto_write.services.hwpx_resume_supplement import supplement_hwpx_from_resume

    master = Path(
        r"C:\Users\ekth3\OneDrive\바탕 화면\노트북(다솜) 백업 20231222\다솜\개인\★이력서"
        r"\01. 경영지도사 이력서\이력서 박다솜 20230804.hwp"
    )
    recent = Path(
        r"C:\Users\ekth3\OneDrive\바탕 화면\1. 이력서 박다솜 20250308 "
        r"서울창조경제혁신센터 초기창업패키지 평가위원.hwp"
    )

    tmp = Path(tempfile.mkdtemp())
    identity = _extract_identity(PROFILE, recent, master, tmp)
    identity["소속/직위"] = "디엠컨설팅 / 대표"
    identity["주소(거주지)"] = identity.get("주소") or identity.get("주소(거주지)", "")

    mid = WORK / "_step_identity.hwpx"
    fill_hwpx(BASE, mid, identity=identity)

    today = datetime.now().strftime("%Y.%m.%d")
    sign_date = datetime.now().strftime("%Y년  %m월  %d일").replace(" 0", " ")

    sup = supplement_hwpx_from_resume(
        mid,
        OUT,
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
        check_columns=[
            (2, 4, "경영활동 전문상담"),
            (3, 4, "특화분야 전문상담"),
        ],
        sign_date=sign_date,
        sign_name="박다솜",
    )

    report = {
        "output": str(OUT),
        "identity": identity,
        "supplement": sup.as_dict(),
        "sign_date": sign_date,
        "모집분야_근거": "경영지도사(경영활동·경영전략), 창업 멘토(특화·창업) — 이력서 사실",
    }
    (WORK / "07_final_supplement.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if OUT.is_file() else 2


if __name__ == "__main__":
    raise SystemExit(main())
