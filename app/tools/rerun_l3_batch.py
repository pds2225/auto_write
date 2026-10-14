# -*- coding: utf-8 -*-
"""rerun_l3_batch — 빈 원본 양식 일괄 3단계(해당→채움→통과) 회귀 측정.

- 해당: 원본 양식에서 기존 슬롯 탐지(assess_fields)가 찾은 빈 입력칸 수
  (content_state EMPTY/GUIDANCE, decision != NO_TARGET). 탐지기는 사람 확인이
  필요한 빈칸도 protected 로 표시하므로 protected 여부로 거르지 않는다.
  그중 엔진이 자동 기입을 허가한 칸(eligible)은 auto_eligible 열로 따로 센다.
- 채움: 실제 엔진 경로(submit_hwpx)로 가짜 신청자 데이터를 채운 뒤
  hwpx_form_diff 로 원본 대비 실제로 값이 들어간 칸(value_fills + choice_marks).
- 통과: final_check.check_hwpx_structure(R9 무결성·수용검사·양식 생존)에 FAIL 없음.
  L-rule 전수 게이트(lrule_gate) 결과는 별도 열(lrule_fail)로 남긴다. 렌더 증거가
  필요한 규칙(L002·L005 등)은 한글 렌더 없이 오프라인으로는 통과할 수 없어서다.
- 공고문(AnnouncementFormError)은 엔진이 정상 거부한 것으로 보고 크래시가 아닌 '공고문'으로 센다.

원본은 읽기만 한다. 산출물은 임시 폴더에 쓰고 지운다. 데이터는 전부 가짜다.

    python app/tools/rerun_l3_batch.py <양식폴더> --out data/rerun130 [--extra-dir <변환HWPX폴더>]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 가짜 신청자(측정용). 실존 인물·기업 아님.
FAKE_IDENTITY: dict[str, str] = {
    "기업명": "가상측정(주)", "상호": "가상측정(주)", "회사명": "가상측정(주)",
    "신청기업명": "가상측정(주)", "팀명": "가상측정팀",
    "대표자": "김가상", "대표자명": "김가상", "성명": "김가상", "신청자": "김가상",
    "사업자등록번호": "000-00-00000", "생년월일": "1990.01.01",
    "주소": "서울특별시 가상구 측정로 1", "사업장소재지": "서울특별시 가상구 측정로 1",
    "소재지": "서울특별시 가상구 측정로 1",
    "연락처": "010-0000-0000", "전화번호": "02-000-0000", "휴대전화": "010-0000-0000",
    "휴대폰": "010-0000-0000", "이메일": "fake@example.com", "E-mail": "fake@example.com",
    "창업일": "2020.01.01", "개업연월일": "2020.01.01", "설립일": "2020.01.01",
    "업종": "소프트웨어 개발", "업태": "서비스", "종목": "소프트웨어",
    "아이템명": "가상 측정 서비스", "창업아이템명": "가상 측정 서비스",
    "과제명": "가상 측정 과제", "직위": "대표", "소속": "가상측정(주)",
}
ALLOWED_NAMES = ("김가상",)

# 이미 채운 사본·제출본은 빈 원본이 아니므로 뺀다. 신청자 이름처럼 개인을 가리키는
# 토큰은 저장소에 두지 않고 실행할 때 --exclude-token 으로 넘긴다.
EXCLUDE_TOKENS = ("제출본", "작성", "autowrite", "사람수정", "최종")


def excluded_reason(name: str, extra: Iterable[str] = ()) -> str:
    low = name.lower()
    for tok in (*EXCLUDE_TOKENS, *extra):
        if tok.lower() in low:
            return tok
    return ""


def list_targets(dirs: Iterable[Path], extra: Iterable[str] = ()) -> tuple[list[Path], list[tuple[Path, str]]]:
    extra = tuple(t for t in extra if t)
    keep: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for d in dirs:
        for p in sorted(Path(d).rglob("*")):
            if not p.is_file() or p.suffix.lower() != ".hwpx":
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            why = excluded_reason(p.name, extra)
            if why:
                skipped.append((p, why))
            else:
                keep.append(p)
    return keep, skipped


def is_applicable(f: Any) -> bool:
    return (getattr(f, "content_state", "") in ("EMPTY", "GUIDANCE")
            and getattr(f, "decision", "") != "NO_TARGET")


def count_applicable(path: Path) -> tuple[int, int, str]:
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
    from core.docx.services.hwpx_protected_regions import assess_fields

    index = index_hwpx_structure(path)
    status = str(getattr(index, "analysis_status", ""))
    fields = assess_fields(index)
    return (sum(1 for f in fields if is_applicable(f)),
            sum(1 for f in fields if f.eligible), status)


def _unlink(*paths: Path) -> None:
    for p in paths:
        try:
            Path(p).unlink()
        except OSError:
            pass


def measure(path: Path, tmp: Path) -> dict[str, Any]:
    from auto_write.services.hwpx_form_diff import compare_hwpx_forms
    from auto_write.services.hwpx_submit import submit_hwpx
    from auto_write.services.submit_finish.final_check import check_hwpx_structure

    row: dict[str, Any] = {"file": str(path), "name": path.name, "applicable": 0, "auto_eligible": 0, "filled": 0,
                           "passed": 0, "fill_rate": "", "engine_ok": "", "gate_pass": "",
                           "form_intact": "", "lrule": "", "lrule_fail": "", "kind": "양식", "fail_reason": "", "crash": "",
                           "analysis_status": "", "seconds": 0.0}
    t0 = time.time()
    before = path.read_bytes()
    try:
        row["applicable"], row["auto_eligible"], row["analysis_status"] = count_applicable(path)
        if row["analysis_status"] not in ("", "COMPLETE"):
            row["fail_reason"] = f"분석 {row['analysis_status']}"
        out = tmp / f"{abs(hash(str(path)))}.hwpx"
        rep = submit_hwpx(path, out, identity=FAKE_IDENTITY, preserve_template=True,
                          lrule_gate=True, template_survival_baseline=path)
        final = Path(rep.final) if rep.final else out
        row["engine_ok"] = bool(rep.ok)
        lr = " ; ".join(str(x) for x in (rep.lrule_report, rep.error, rep.draft_reason) if x)
        row["lrule"] = lr[:200].replace("\n", " ")
        row["lrule_fail"] = ",".join(sorted(set(
            seg.split("|")[0].strip() for seg in lr.replace("\n", ";").split(";")
            if "status: FAIL" in seg and seg.split("|")[0].strip())))
        row["lrule_fail"] = ",".join(c.split(":")[-1].strip() for c in row["lrule_fail"].split(",") if c)
        if final.exists():
            diff = compare_hwpx_forms(path, final)
            row["filled"] = int(diff.value_fills) + int(diff.choice_marks)
            row["form_intact"] = bool(diff.form_intact)
            findings = check_hwpx_structure(final, baseline_form=path, allowed_names=ALLOWED_NAMES)
            fails = [f for f in findings if getattr(f.status, "value", f.status) == "FAIL"]
            row["gate_pass"] = not fails
            if fails and not row["fail_reason"]:
                row["fail_reason"] = "; ".join(f"{f.code}:{f.evidence or f.message}"[:120] for f in fails[:2])
        else:
            row["gate_pass"] = False
            row["fail_reason"] = row["fail_reason"] or "산출물 없음"
        _unlink(out, final)
        if row["applicable"]:
            row["fill_rate"] = round(min(1.0, row["filled"] / row["applicable"]), 3)
        if row["applicable"] == 0 and not row["fail_reason"]:
            row["fail_reason"] = "해당 칸 0(슬롯 미탐지)"
        elif row["filled"] == 0 and not row["fail_reason"]:
            row["fail_reason"] = "채움 0"
        ok = row["gate_pass"] is True
        row["passed"] = min(row["filled"], row["applicable"]) if ok else 0
    except Exception as exc:  # noqa: BLE001 — 측정 도구: 크래시도 결과로 기록
        if type(exc).__name__ == "AnnouncementFormError":
            row["kind"] = "공고문"
            row["fail_reason"] = "공고문(엔진 정상 거부)"
            row["seconds"] = round(time.time() - t0, 1)
            return row
        row["crash"] = f"{type(exc).__name__}: {exc}"[:300]
        row["fail_reason"] = row["fail_reason"] or "크래시"
        row["trace"] = traceback.format_exc()[-800:]
    if path.read_bytes() != before:
        row["crash"] = (str(row["crash"]) + " | 원본 변경됨!").strip(" |")
    row["seconds"] = round(time.time() - t0, 1)
    return row


FIELDS = ["name", "kind", "applicable", "auto_eligible", "filled", "passed", "fill_rate", "engine_ok", "gate_pass",
          "form_intact", "fail_reason", "crash", "analysis_status", "lrule_fail", "lrule", "seconds", "file"]


def summarize(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for r in all_rows if r.get("kind", "양식") == "양식"]
    app = sum(r["applicable"] for r in rows)
    fil = sum(min(r["filled"], r["applicable"]) for r in rows)
    rated = [r for r in rows if r["fill_rate"] != ""]
    return {
        "forms": len(rows),
        "announcements": len(all_rows) - len(rows),
        "lrule_clean_forms": sum(1 for r in rows if r["gate_pass"] is True and not r.get("lrule_fail")),
        "crashes": sum(1 for r in rows if r["crash"]),
        "pass_forms": sum(1 for r in rows if r["gate_pass"] is True),
        "applicable_total": app,
        "filled_total_capped": fil,
        "passed_total": sum(r["passed"] for r in rows),
        "pooled_fill_rate": round(fil / app, 3) if app else 0.0,
        "avg_fill_rate": round(sum(r["fill_rate"] for r in rated) / len(rated), 3) if rated else 0.0,
        "zero_applicable": sum(1 for r in rows if r["applicable"] == 0 and not r["crash"]),
    }


def worst(rows: list[dict[str, Any]], n: int = 15) -> list[dict[str, Any]]:
    rows = [r for r in rows if r.get("kind", "양식") == "양식"]
    return sorted(rows, key=lambda r: (0 if r["crash"] else 1,
                                       r["fill_rate"] if r["fill_rate"] != "" else -1.0,
                                       -r["applicable"]))[:n]


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], skipped: list[tuple[Path, str]],
                  meta: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "rerun130_l3.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    s = summarize(rows)
    md = [f"# rerun130 3단계 측정 ({meta.get('commit', '')})", "",
          f"- 대상 빈 양식 {s['forms']}개(공고문 {s['announcements']}개 별도), 제외 {len(skipped)}개, 크래시 {s['crashes']}개",
          f"- L-rule FAIL 없이 통과 {s['lrule_clean_forms']}/{s['forms']} (렌더 증거 규칙은 오프라인 미충족)",
          f"- 통과 양식 {s['pass_forms']}/{s['forms']}",
          f"- 해당 {s['applicable_total']} / 채움 {s['filled_total_capped']} / 통과 {s['passed_total']} "
          f"(채움률 합산 {s['pooled_fill_rate']:.1%}, 양식 평균 {s['avg_fill_rate']:.1%})",
          f"- 해당 0(슬롯 미탐지) {s['zero_applicable']}개", "",
          "## 하위 15", "", "| 양식 | 해당 | 채움 | 통과 | 채움률 | 주요 원인 |", "|---|---|---|---|---|---|"]
    for r in worst(rows):
        reason = str(r["crash"] or r["fail_reason"]).replace("|", "/")[:90]
        md.append(f"| {r['name']} | {r['applicable']} | {r['filled']} | {r['passed']} | "
                  f"{r['fill_rate']} | {reason} |")
    md += ["", "## 제외 목록", ""] + [f"- {p.name} ({why})" for p, why in skipped]
    (out_dir / "rerun130_l3.md").write_text("\n".join(md), encoding="utf-8")
    (out_dir / "rerun130_l3_summary.json").write_text(
        json.dumps({"summary": s, "meta": meta}, ensure_ascii=False, indent=2), encoding="utf-8")
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="빈 양식 일괄 해당→채움→통과 측정(가짜 데이터)")
    ap.add_argument("folder")
    ap.add_argument("--extra-dir", action="append", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude-token", action="append", default=[],
                    help="파일명에 이 문자열이 있으면 제외(반복 가능, 예: 신청자 이름)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--commit", default="")
    a = ap.parse_args(argv)
    targets, skipped = list_targets([Path(a.folder), *map(Path, a.extra_dir)], a.exclude_token)
    if a.limit:
        targets = targets[: a.limit]
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="rerun130_") as td, \
            open(out_dir / "progress.jsonl", "w", encoding="utf-8") as prog:
        for i, p in enumerate(targets, 1):
            r = measure(p, Path(td))
            rows.append(r)
            prog.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            prog.flush()
            print(f"[{i}/{len(targets)}] {r['applicable']}/{r['filled']}/{r['passed']} "
                  f"{'CRASH ' if r['crash'] else ''}{p.name}", flush=True)
    s = write_outputs(out_dir, rows, skipped, {"commit": a.commit, "folder": a.folder})
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
