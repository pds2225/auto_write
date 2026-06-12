"""self_diagnose.py — 실사용 기준 자가진단 CLI.

용도
----
1) 제출 직전 DOCX 가 '실제로 제출 가능한 상태'인지 하드페일 기준으로 판정한다.
2) 요구사항 원장(workspace/requirements_ledger.json)과 대조하여
   "사용자 요구 중 무엇이 아직 미달성인지"를 함께 보고한다.
3) 품질점수(doc_quality_score)가 통과인데 본 진단이 실패라면
   = 채점기 사각지대 → 자동개발 루프(/auto-write-selfdev)의 다음 개선 대상이 된다.

사용 (PowerShell)
-----------------
cd D:\auto_write\app
python self_diagnose.py "C:\경로\제출본.docx"
python self_diagnose.py 제출본.docx --json 진단결과.json

종료코드: 0 = 제출가능, 2 = 제출불가(DRAFT)
읽기 전용 — 문서를 수정하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from auto_write.services.usage_acceptance import AcceptanceConfig, run_acceptance

_LEDGER_DEFAULT = Path(__file__).resolve().parent.parent / "workspace" / "requirements_ledger.json"


def _load_ledger(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _requirement_status(req: dict, failed_ids: set[str], all_pass: bool) -> str:
    ids = req.get("check_ids") or []
    if not ids:
        return req.get("상태", "수동확인")
    if "__all__" in ids:
        return "달성" if all_pass else "미달성"
    hit = [i for i in ids if i in failed_ids]
    if not hit:
        return "달성"
    if len(hit) < len(ids):
        return "부분달성"
    return "미달성"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="실사용 기준 자가진단 (읽기 전용)")
    ap.add_argument("docx", help="진단할 DOCX 경로")
    ap.add_argument("--json", dest="json_out", help="결과 JSON 저장 경로")
    ap.add_argument("--ledger", default=str(_LEDGER_DEFAULT), help="요구사항 원장 경로")
    ap.add_argument("--blind-review", action="store_true",
                    help="블라인드 공고 모드 — ○○○ 마스킹 허용 + 실명 잔존 검출(fail)")
    args = ap.parse_args(argv)

    src = Path(args.docx)
    if not src.exists():
        print(f"[오류] 파일 없음: {src}")
        return 1

    report = run_acceptance(src, AcceptanceConfig(blind_review=args.blind_review))
    data = report.as_dict()

    print(f"\n=== 실사용 자가진단: {src.name} ===")
    print(f"판정: {data['verdict']}  (fail 결함 {data['fail_defects']} / warn {data['warn_defects']})\n")
    for c in report.results:
        mark = "PASS" if c.passed else ("FAIL" if c.severity == "fail" else "WARN")
        print(f"[{mark}] {c.label:<22} {c.detail}")
        for s in c.samples[:3]:
            print(f"       · {s}")

    failed_ids = {c.check_id for c in report.results if not c.passed and c.severity == "fail"}
    ledger = _load_ledger(Path(args.ledger))
    if ledger:
        print("\n--- 요구사항 원장 대조 ---")
        gaps = []
        for req in ledger.get("requirements", []):
            st = _requirement_status(req, failed_ids, report.submittable)
            print(f"{req['id']} [{st}] {req['요구'][:42]}")
            if st != "달성":
                gaps.append(req["id"])
        if gaps:
            print(f"\n다음 자동개발 대상 후보: {', '.join(gaps)}")
            print("→ Claude Code 에서 /auto-write-selfdev 실행 시 이 중 임팩트 1건을 골라 수정합니다.")
        data["ledger_gaps"] = gaps

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 저장: {args.json_out}")

    return 0 if report.submittable else 2


if __name__ == "__main__":
    sys.exit(main())
