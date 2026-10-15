# -*- coding: utf-8 -*-
"""rerun_l3_batch — 빈 원본 양식 일괄 3단계(해당→채움→통과) 회귀 측정.

채움 경로는 웹 콘솔 직접 채움(project_service._generate_hwpx_direct)과 같은 순서를
엔진 코드 수정 없이 따른다: apply_t02_analyzer_writes → direct_cell_plan +
commit_guidance_value_writes → submit_hwpx(preserve_template).
데이터는 전부 가짜 프로필이다. 원본은 읽기만 하고 산출물은 임시 폴더에 쓰고 지운다.

해당(빈 입력칸) = assess_fields 가 찾은 EMPTY/GUIDANCE 칸(NO_TARGET 제외), 세 갈래:
- profile: 신원·회사·연락처·날짜 등 프로필 값으로 채울 수 있는 라벨 칸 + 체크박스
- narrative: 서술·사람 판단이 필요한 칸
- other: 라벨 없는 빈칸·일정표·중첩표 등(분류 불가)
채움 = 같은 칸이 산출물에서 더 이상 EMPTY/GUIDANCE 가 아님(칸 단위).
통과 = submit_hwpx 게이트(ok) + final_check.check_hwpx_structure 에 FAIL 없음(렌더 증거는 요구 안 함).

    python app/tools/rerun_l3_batch.py <양식폴더> --out data/rerun130 \
        [--extra-dir <변환HWPX폴더>] [--exclude-token 회사명 ...]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 가짜 신청자 프로필(측정용). 실존 인물·기업 아님.
FAKE_IDENTITY: dict[str, str] = {
    "기업명": "가상측정(주)", "상호": "가상측정(주)", "회사명": "가상측정(주)", "업체명": "가상측정(주)",
    "신청기업명": "가상측정(주)", "기관명": "가상측정(주)", "팀명": "가상측정팀", "소속": "가상측정(주)",
    "대표자": "김가상", "대표자명": "김가상", "성명": "김가상", "신청자": "김가상", "신청인": "김가상",
    "이름": "김가상", "담당자": "김가상", "작성자": "김가상", "성별": "남", "생년월일": "1990.01.01",
    "사업자등록번호": "000-00-00000", "법인등록번호": "000000-0000000",
    "주소": "서울특별시 가상구 측정로 1", "사업장소재지": "서울특별시 가상구 측정로 1",
    "소재지": "서울특별시 가상구 측정로 1", "거주지": "서울특별시 가상구 측정로 1",
    "연락처": "010-0000-0000", "전화번호": "02-000-0000", "휴대전화": "010-0000-0000",
    "휴대폰": "010-0000-0000", "팩스": "02-000-0001", "이메일": "fake@example.com",
    "E-mail": "fake@example.com", "홈페이지": "https://example.com",
    "창업일": "2020.01.01", "개업연월일": "2020.01.01", "설립일": "2020.01.01",
    "업종": "소프트웨어 개발", "업태": "서비스", "종목": "소프트웨어",
    "아이템명": "가상 측정 서비스", "창업아이템명": "가상 측정 서비스", "사업명": "가상 측정 서비스",
    "과제명": "가상 측정 과제", "직위": "대표", "직책": "대표", "학력": "학사",
    "종업원수": "3", "직원수": "3", "자본금": "10,000,000", "작성일": "2026.10.15", "신청일": "2026.10.15",
}
ALLOWED_NAMES = ("김가상",)

PROFILE_KEYWORDS = (
    "기업명", "상호", "회사명", "업체명", "기관명", "팀명", "소속", "대표", "성명", "신청자", "신청인",
    "이름", "담당자", "작성자", "성별", "생년", "나이", "연령", "사업자", "법인", "주소", "소재지",
    "거주지", "연락처", "전화", "휴대", "핸드폰", "팩스", "이메일", "e-mail", "email", "홈페이지",
    "창업일", "개업", "설립", "업종", "업태", "종목", "아이템명", "사업명", "과제명", "직위", "직책",
    "학력", "종업원", "직원수", "자본금", "작성일", "신청일", "제출일", "일자", "년월일",
)
NARRATIVE_KEYWORDS = (
    "배경", "내용", "계획", "전략", "역량", "차별", "우수성", "시장", "효과", "개요", "목표", "현황",
    "필요성", "방안", "방법", "소개", "경쟁", "문제", "해결", "성과", "사업화", "추진", "실적", "경력",
    "비전", "모델", "특징", "기술",
)
NARRATIVE_TYPES = ("T07", "T15")

# 채운 사본·중간 산출물은 빈 원본이 아니다. 회사·사람 이름은 --exclude-token 으로 넘긴다.
EXCLUDE_TOKENS = ("제출본", "작성", "autowrite", "사람수정", "최종", "_step_", "filled",
                  "signed", "fixed", "result", "sample", "백업", "backup", "복사본")
_VERSION_RE = re.compile(r"(?:^|[_\s\-])v\d+(?:\.\d+)*(?=$|[_\s\-.])", re.I)
FILLED_COPY_MIN_FIELDS = 4
FILLED_COPY_RATIO = 0.6
FILLABLE_TYPES = ("T02", "T07", "T15", "T16")
CATS = ("profile", "narrative", "other")


def _norm(text: Any) -> str:
    return re.sub(r"[\s:：·•○●□■\-_()\[\]<>]", "", str(text or "")).lower()


def excluded_reason(name: str, extra: Iterable[str] = ()) -> str:
    low = name.lower()
    for tok in (*EXCLUDE_TOKENS, *extra):
        if tok and tok.lower() in low:
            return tok
    if _VERSION_RE.search(Path(name).stem):
        return "버전 사본(vN)"
    return ""


def list_targets(dirs: Iterable[Path], extra: Iterable[str] = ()) -> tuple[list[Path], list[tuple[Path, str]]]:
    extra = tuple(t for t in extra if t)
    keep: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for d in dirs:
        for p in sorted(Path(d).rglob("*")):
            if not p.is_file():
                continue
            suf = p.suffix.lower()
            if suf not in (".hwpx", ".hwp"):
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            if suf == ".hwp":
                skipped.append((p, "hwp 생략(HWPX만 측정)"))
                continue
            why = excluded_reason(p.name, extra)
            (skipped.append((p, why)) if why else keep.append(p))
    return keep, skipped


def classify(field: Any) -> str:
    label = _norm(getattr(field, "field_label", ""))
    ftype = str(getattr(field, "field_type", ""))
    kinds = " ".join(str(x) for x in (getattr(field, "structure_types", ()) or ())).upper()
    if "CHECK" in kinds:
        return "profile"
    # 서술 문구(배경·역량 등)가 라벨에 있으면 프로필 키워드(신청자 등)보다 우선한다.
    if ftype in NARRATIVE_TYPES or (label and any(k in label for k in NARRATIVE_KEYWORDS)):
        return "narrative"
    if label and any(k in label for k in PROFILE_KEYWORDS):
        return "profile"
    return "other"


def is_open(field: Any) -> bool:
    return (getattr(field, "content_state", "") in ("EMPTY", "GUIDANCE")
            and getattr(field, "decision", "") != "NO_TARGET")


def slot_key(f: Any) -> tuple:
    return (f.section_index, f.table_index, f.row, f.col,
            f.paragraph_index if f.table_index is None else None)


def is_filled_copy(fields: list[Any]) -> tuple[bool, float]:
    """채움 가능 슬롯(T02/T07/T15/T16)에 이미 값이 넷 이상이면 채운 사본으로 본다.
    빈 원본은 이 타입 칸이 전부 EMPTY/GUIDANCE 다."""
    slots: dict[tuple, str] = {}
    for f in fields:
        if str(getattr(f, "field_type", "")) in FILLABLE_TYPES:
            state = getattr(f, "content_state", "")
            if state in ("EMPTY", "GUIDANCE", "EXISTING"):
                slots[slot_key(f)] = state
    if not slots:
        return False, 0.0
    filled = sum(1 for s in slots.values() if s == "EXISTING")
    ratio = filled / len(slots)
    return filled >= FILLED_COPY_MIN_FIELDS, round(ratio, 3)


def slots_of(fields: list[Any]) -> dict[tuple, str]:
    rank = {"profile": 0, "narrative": 1, "other": 2}
    slots: dict[tuple, str] = {}
    for f in fields:
        if is_open(f):
            cat, key = classify(f), slot_key(f)
            if key not in slots or rank[cat] < rank[slots[key]]:
                slots[key] = cat
    return slots


def analyze(path: Path) -> tuple[list[Any], str]:
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
    from core.docx.services.hwpx_protected_regions import assess_fields

    index = index_hwpx_structure(path)
    return list(assess_fields(index)), str(getattr(index, "analysis_status", ""))


def real_fill(src: Path, out: Path, work: Path, identity: dict[str, str]):
    """project_service._generate_hwpx_direct 의 채움 순서(참고자료 없음)."""
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
    from core.docx.services.hwpx_fill import commit_guidance_value_writes
    from core.docx.services.hwpx_protected_regions import authorization_is_current, authorize_t02_writes
    from auto_write.services.hwpx_fill import commit_t02_label_writes
    from auto_write.services.hwpx_narrative_source import direct_cell_plan
    from auto_write.services.hwpx_submit import apply_t02_analyzer_writes, submit_hwpx

    staging = work / f"t02-{os.getpid()}.hwpx"
    cell_staging = work / f"cell-{os.getpid()}.hwpx"
    try:
        wire = apply_t02_analyzer_writes(
            src, staging, dict(identity),
            authorize_t02_writes=authorize_t02_writes,
            authorization_is_current=authorization_is_current,
            commit_t02_label_writes=commit_t02_label_writes,
        )
        cell_source = Path(wire.fill_source)
        grants, values, _n, _i = direct_cell_plan(index_hwpx_structure(cell_source), dict(identity), [], {})
        if grants:
            commit_guidance_value_writes(cell_source, cell_staging, grants, values)
            cell_source = cell_staging
        rep = submit_hwpx(cell_source, out, identity=dict(identity), acceptance_gate=True,
                          normalize_colors=False, submission_cleanup=False, preserve_template=True,
                          template_survival_baseline=src)
        rep.filled.update(wire.written)
        return rep
    finally:
        for t in (staging, cell_staging):
            try:
                t.unlink()
            except OSError:
                pass


def _blank_row(path: Path) -> dict[str, Any]:
    row: dict[str, Any] = {"file": str(path), "name": path.name, "kind": "양식", "passed": 0,
                           "engine_ok": "", "gate_pass": "", "form_intact": "", "fail_reason": "",
                           "crash": "", "analysis_status": "", "filled_copy_ratio": "", "seconds": 0.0,
                           "profile_rate": "", "narrative_rate": ""}
    for c in CATS:
        row[f"{c}_app"] = row[f"{c}_fill"] = 0
    return row


def measure(path: Path, tmp: Path, identity: dict[str, str] | None = None) -> dict[str, Any]:
    from auto_write.services.hwpx_form_diff import compare_hwpx_forms
    from auto_write.services.submit_finish.final_check import check_hwpx_structure

    identity = identity or FAKE_IDENTITY
    row = _blank_row(path)
    t0 = time.time()
    before = path.read_bytes()
    try:
        fields, row["analysis_status"] = analyze(path)
        copy, ratio = is_filled_copy(fields)
        row["filled_copy_ratio"] = ratio
        if copy:
            row["kind"] = "채운사본"
            row["fail_reason"] = f"이미 채워진 사본(프로필칸 {ratio:.0%} 값 있음)"
            return row
        slots = slots_of(fields)
        for c in CATS:
            row[f"{c}_app"] = sum(1 for v in slots.values() if v == c)
        out = tmp / f"out-{abs(hash(str(path)))}.hwpx"
        rep = real_fill(path, out, tmp, identity)
        final = Path(rep.final) if rep.final else out
        row["engine_ok"] = bool(rep.ok)
        if final.exists():
            after = slots_of(analyze(final)[0])
            for key, cat in slots.items():
                if key not in after:
                    row[f"{cat}_fill"] += 1
            row["form_intact"] = bool(compare_hwpx_forms(path, final).form_intact)
            findings = check_hwpx_structure(final, baseline_form=path, allowed_names=ALLOWED_NAMES)
            fails = [f for f in findings if getattr(f.status, "value", f.status) == "FAIL"]
            row["gate_pass"] = not fails
            if fails:
                row["fail_reason"] = "; ".join(f"{f.code}:{f.evidence or f.message}"[:120] for f in fails[:2])
        else:
            row["gate_pass"] = False
            row["fail_reason"] = "산출물 없음"
        for p in {out, final}:
            try:
                p.unlink()
            except OSError:
                pass
        if not rep.ok and not row["fail_reason"]:
            row["fail_reason"] = "엔진 게이트: " + str(rep.error or rep.draft_reason or "불통과")[:140]
        for c in ("profile", "narrative"):
            if row[f"{c}_app"]:
                row[f"{c}_rate"] = round(row[f"{c}_fill"] / row[f"{c}_app"], 3)
        if not row["fail_reason"]:
            if row["profile_app"] == 0:
                row["fail_reason"] = "프로필 칸 0(탐지 안 됨)"
            elif row["profile_fill"] == 0:
                row["fail_reason"] = "프로필 칸 채움 0"
            elif row["profile_fill"] < row["profile_app"]:
                row["fail_reason"] = f"프로필 칸 미채움 {row['profile_app'] - row['profile_fill']}"
        if row["engine_ok"] is True and row["gate_pass"] is True:
            row["passed"] = row["profile_fill"]
    except Exception as exc:  # noqa: BLE001 — 측정 도구: 크래시도 결과로 기록
        if type(exc).__name__ == "AnnouncementFormError":
            row["kind"] = "공고문"
            row["fail_reason"] = "공고문(엔진 정상 거부)"
        else:
            row["crash"] = f"{type(exc).__name__}: {exc}"[:300]
            row["fail_reason"] = "크래시"
            row["trace"] = traceback.format_exc()[-800:]
    finally:
        if path.read_bytes() != before:
            row["crash"] = (str(row["crash"]) + " | 원본 변경됨!").strip(" |")
        row["seconds"] = round(time.time() - t0, 1)
    return row


FIELDS = ["name", "kind", "profile_app", "profile_fill", "passed", "profile_rate",
          "narrative_app", "narrative_fill", "narrative_rate", "other_app", "other_fill",
          "engine_ok", "gate_pass", "form_intact", "fail_reason", "crash", "analysis_status",
          "filled_copy_ratio", "seconds", "file"]


def summarize(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for r in all_rows if r.get("kind") == "양식"]
    pa = sum(r["profile_app"] for r in rows)
    pf = sum(r["profile_fill"] for r in rows)
    na = sum(r["narrative_app"] for r in rows)
    nf = sum(r["narrative_fill"] for r in rows)
    rated = [r["profile_rate"] for r in rows if r["profile_rate"] != ""]
    return {
        "forms": len(rows),
        "announcements": sum(1 for r in all_rows if r.get("kind") == "공고문"),
        "filled_copies": sum(1 for r in all_rows if r.get("kind") == "채운사본"),
        "crashes": sum(1 for r in rows if r["crash"]),
        "pass_forms": sum(1 for r in rows if r["engine_ok"] is True and r["gate_pass"] is True),
        "profile_applicable": pa, "profile_filled": pf,
        "profile_passed": sum(r["passed"] for r in rows),
        "profile_fill_rate": round(pf / pa, 3) if pa else 0.0,
        "profile_avg_rate": round(sum(rated) / len(rated), 3) if rated else 0.0,
        "narrative_applicable": na, "narrative_filled": nf,
        "narrative_fill_rate": round(nf / na, 3) if na else 0.0,
        "other_applicable": sum(r["other_app"] for r in rows),
        "other_filled": sum(r["other_fill"] for r in rows),
        "zero_profile": sum(1 for r in rows if r["profile_app"] == 0 and not r["crash"]),
    }


def worst(rows: list[dict[str, Any]], n: int = 15) -> list[dict[str, Any]]:
    rows = [r for r in rows if r.get("kind") == "양식"]
    return sorted(rows, key=lambda r: (0 if r["crash"] else 1,
                                       r["profile_rate"] if r["profile_rate"] != "" else 2.0,
                                       -r["profile_app"]))[:n]


def write_outputs(out_dir: Path, rows: list[dict[str, Any]], skipped: list[tuple[Path, str]],
                  meta: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "rerun130_l3.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    s = summarize(rows)
    md = [f"# rerun130 3단계 측정 ({meta.get('commit', '')})", "",
          f"- 측정 양식 {s['forms']}개 (공고문 {s['announcements']}, 내용상 채운 사본 {s['filled_copies']}, "
          f"파일명 제외 {len(skipped)} 별도), 크래시 {s['crashes']}",
          f"- 통과 양식 {s['pass_forms']}/{s['forms']}",
          f"- **프로필 칸: 해당 {s['profile_applicable']} / 채움 {s['profile_filled']} / 통과 "
          f"{s['profile_passed']} (채움률 {s['profile_fill_rate']:.1%}, 양식 평균 {s['profile_avg_rate']:.1%})**",
          f"- 서술 칸: 해당 {s['narrative_applicable']} / 채움 {s['narrative_filled']} "
          f"({s['narrative_fill_rate']:.1%}), 참고자료 없이 측정",
          f"- 분류 불가 빈칸: {s['other_applicable']} (채움 {s['other_filled']})",
          f"- 프로필 칸 0개 양식 {s['zero_profile']}", "",
          "## 하위 15 (프로필 채움률 기준)", "",
          "| 양식 | 프로필 해당 | 채움 | 통과 | 채움률 | 서술 | 주요 원인 |", "|---|---|---|---|---|---|---|"]
    for r in worst(rows):
        reason = str(r["crash"] or r["fail_reason"]).replace("|", "/")[:90]
        md.append(f"| {r['name']} | {r['profile_app']} | {r['profile_fill']} | {r['passed']} | "
                  f"{r['profile_rate']} | {r['narrative_fill']}/{r['narrative_app']} | {reason} |")
    md += ["", "## 내용상 채운 사본으로 뺀 것", ""]
    md += [f"- {r['name']} ({r['fail_reason']})" for r in rows if r.get("kind") == "채운사본"]
    md += ["", "## 파일명으로 뺀 것", ""] + [f"- {p.name} ({why})" for p, why in skipped]
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
                    help="파일명에 이 문자열이 있으면 제외(반복 가능, 예: 회사·사람 이름)")
    ap.add_argument("--only", action="append", default=[], help="파일명에 이 문자열이 있는 것만(점검용)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--commit", default="")
    a = ap.parse_args(argv)
    targets, skipped = list_targets([Path(a.folder), *map(Path, a.extra_dir)], a.exclude_token)
    if a.only:
        targets = [p for p in targets if any(o in p.name for o in a.only)]
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
            print(f"[{i}/{len(targets)}] {r['kind']} P {r['profile_fill']}/{r['profile_app']} "
                  f"N {r['narrative_fill']}/{r['narrative_app']} {'CRASH ' if r['crash'] else ''}{p.name}",
                  flush=True)
    s = write_outputs(out_dir, rows, skipped, {"commit": a.commit, "folder": a.folder,
                                               "extra_dirs": a.extra_dir})
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
