# -*- coding: utf-8 -*-
"""hwpx_coverage — HWPX 값 채우기 커버리지 측정 하네스 (읽기전용).

목적
----
코퍼스의 각 `.hwpx` 양식에 대해 현재 `hwpx_fill` 엔진이 **무엇을 채우고 무엇을
놓치는지** 수치화한다. '표준 기업정보' identity 로 채움을 시도하고, 채운 수와
양식이 가진 '채움 기회'(빈 값칸·인라인 빈칸·체크박스) 구조 수를 함께 집계해
**커버리지 갭**을 드러낸다.

안전
----
원본은 절대 수정하지 않는다. 채움은 임시 출력 파일로만 하고 즉시 삭제한다.
결정론(AI 없음). 이 도구는 측정만 하며 엔진을 바꾸지 않는다.

사용
----
    cd D:\\auto_write-wt-hwpxparity\\app
    py -3.11 tools/hwpx_coverage.py "C:\\...\\00. 공고" [--limit N] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

# app/ 를 import 기준으로
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import etree  # noqa: E402

from auto_write.services.hwpx_fill import (  # noqa: E402
    _direct,
    _inline_texts,
    _q,
    fill_hwpx,
)
from auto_write.services.cross_form_autofill import (  # noqa: E402
    _is_visible_blank,
    _iter_line_fields,
)

_SECTION_RE = __import__("re").compile(r"Contents/section\d+\.xml$", __import__("re").I)

# 표준 기업정보(사업계획서 공통 칸) — 값은 식별 가능한 sentinel. 날조 아님(측정용).
STANDARD_IDENTITY: dict[str, str] = {
    "기업명": "◆측정기업(주)",
    "상호": "◆측정기업(주)",
    "회사명": "◆측정기업(주)",
    "신청기업명": "◆측정기업(주)",
    "대표자": "◆홍길동",
    "대표자명": "◆홍길동",
    "성명": "◆홍길동",
    "사업자등록번호": "◆111-11-11111",
    "법인등록번호": "◆110111-1111111",
    "생년월일": "◆1990.01.01",
    "주소": "◆서울시 측정구 측정로 1",
    "사업장소재지": "◆서울시 측정구 측정로 1",
    "소재지": "◆서울시 측정구 측정로 1",
    "연락처": "◆010-1111-1111",
    "전화번호": "◆02-111-1111",
    "휴대전화": "◆010-1111-1111",
    "이메일": "◆test@measure.co.kr",
    "창업일": "◆2020.01.01",
    "개업연월일": "◆2020.01.01",
    "업종": "◆정보통신업",
    "업태": "◆서비스업",
    "종목": "◆소프트웨어 개발",
    "사업아이템명": "◆측정 아이템",
    "신청분야": "◆측정 분야",
    "홈페이지": "◆www.measure.co.kr",
    "팩스": "◆02-111-1112",
}


def _iter_section_roots(path: Path):
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if _SECTION_RE.search(name):
                try:
                    yield etree.fromstring(z.read(name))
                except etree.XMLSyntaxError:
                    continue


def _cell_text(tc) -> str:
    parts = [str(t.text or "") for t in tc.iter(_q("t"))]
    return "".join(parts).strip()


def _structure_counts(path: Path) -> dict[str, int]:
    """양식의 '채움 기회' 구조 수 — 표/셀/빈 값칸/인라인 빈칸/체크박스."""
    tbls = cells = empty_cells = inline_blanks = checkboxes = 0
    for root in _iter_section_roots(path):
        for tbl in root.iter(_q("tbl")):
            tbls += 1
        for tc in root.iter(_q("tc")):
            cells += 1
            if not _cell_text(tc):
                empty_cells += 1
            # 인라인 빈칸: 셀 안 각 hp:p 직계 텍스트 흐름에서 가시 빈칸 필드
            for sub in _direct(tc, "subList"):
                for p in _direct(sub, "p"):
                    ts = _inline_texts(p)
                    if not ts:
                        continue
                    flat = "".join(t.text or "" for t in ts)
                    if ":" not in flat and "：" not in flat:
                        continue
                    for _lbl, val, _s, _e in _iter_line_fields(flat):
                        if _is_visible_blank(val):
                            inline_blanks += 1
        # 체크박스 □ 개수(전 텍스트)
        for t in root.iter(_q("t")):
            checkboxes += str(t.text or "").count("□")
    return {
        "tables": tbls,
        "cells": cells,
        "empty_cells": empty_cells,
        "inline_blanks": inline_blanks,
        "checkboxes": checkboxes,
    }


def _classify(counts: dict[str, int]) -> str:
    """양식(fillable) vs 공고문(non-form) 대략 분류."""
    fillable = counts["empty_cells"] + counts["inline_blanks"] + counts["checkboxes"]
    if counts["tables"] >= 1 and fillable >= 5:
        return "form"
    if counts["tables"] == 0:
        return "prose(공고문)"
    return "low-slot"


def measure_file(path: Path, tmp_dir: Path) -> dict[str, Any]:
    try:
        counts = _structure_counts(path)
    except Exception as exc:  # noqa: BLE001
        return {"file": str(path), "error": f"구조분석 실패: {exc}"}

    tmp_out = tmp_dir / f"{path.stem}.{os.getpid()}.cov.hwpx"
    filled: dict[str, str] = {}
    filled_count = residual_count = 0
    fill_error = ""
    try:
        rep = fill_hwpx(path, tmp_out, identity=STANDARD_IDENTITY)
        filled = rep.filled
        filled_count = rep.filled_count
        residual_count = len(rep.residual)
    except Exception as exc:  # noqa: BLE001
        fill_error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            if tmp_out.exists():
                tmp_out.unlink()
        except OSError:
            pass

    return {
        "file": str(path),
        "name": path.name,
        "kind": _classify(counts),
        **counts,
        "filled_count": filled_count,
        "filled_fields": sorted(filled.keys()),
        "residual_std_count": residual_count,
        "fill_error": fill_error,
    }


def run_folder(folder: Path, limit: int | None = None) -> dict[str, Any]:
    files = sorted(folder.rglob("*.hwpx")) + sorted(folder.rglob("*.HWPX"))
    files = sorted(set(files))
    if limit:
        files = files[:limit]
    tmp_dir = Path(tempfile.gettempdir())
    results = [measure_file(p, tmp_dir) for p in files]

    forms = [r for r in results if r.get("kind") == "form"]
    total_std_filled = sum(r.get("filled_count", 0) for r in forms)
    forms_with_fill = sum(1 for r in forms if r.get("filled_count", 0) > 0)
    total_inline = sum(r.get("inline_blanks", 0) for r in forms)
    total_checkbox = sum(r.get("checkboxes", 0) for r in forms)
    return {
        "folder": str(folder),
        "total_hwpx": len(results),
        "forms": len(forms),
        "prose": sum(1 for r in results if r.get("kind") == "prose(공고문)"),
        "low_slot": sum(1 for r in results if r.get("kind") == "low-slot"),
        "errors": sum(1 for r in results if r.get("error") or r.get("fill_error")),
        "forms_with_any_std_fill": forms_with_fill,
        "total_std_fields_filled": total_std_filled,
        "total_inline_blanks_in_forms": total_inline,
        "total_checkboxes_in_forms": total_checkbox,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HWPX 값 채우기 커버리지 측정(읽기전용)")
    ap.add_argument("folder", help="양식 폴더(재귀 탐색)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--json", dest="json_out", default=None, help="상세 결과 JSON 저장 경로")
    ap.add_argument("--forms-only", action="store_true", help="form 으로 분류된 것만 표 출력")
    args = ap.parse_args(argv)

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"폴더가 아닙니다: {folder}", file=sys.stderr)
        return 2

    summary = run_folder(folder, args.limit)

    print(f"\n=== HWPX 커버리지 요약: {folder.name} ===")
    print(f"총 .hwpx: {summary['total_hwpx']}  |  양식(form): {summary['forms']}  "
          f"|  공고문: {summary['prose']}  |  저슬롯: {summary['low_slot']}  "
          f"|  오류: {summary['errors']}")
    print(f"표준칸 채워진 양식: {summary['forms_with_any_std_fill']}/{summary['forms']}  "
          f"|  표준칸 총 채움: {summary['total_std_fields_filled']}")
    print(f"양식 내 인라인 빈칸 총: {summary['total_inline_blanks_in_forms']}  "
          f"|  체크박스(□) 총: {summary['total_checkboxes_in_forms']}")

    rows = [r for r in summary["results"]
            if (not args.forms_only or r.get("kind") == "form")]
    print(f"\n{'양식명':<42} {'종류':<12} {'표':>3} {'빈칸':>4} {'인라':>4} {'체크':>4} {'채움':>4}")
    print("-" * 88)
    for r in rows:
        if r.get("error"):
            print(f"{r['file'][-40:]:<42} ERROR {r['error'][:30]}")
            continue
        nm = (r["name"][:39] + "…") if len(r["name"]) > 40 else r["name"]
        print(f"{nm:<42} {r['kind']:<12} {r['tables']:>3} {r['empty_cells']:>4} "
              f"{r['inline_blanks']:>4} {r['checkboxes']:>4} {r['filled_count']:>4}")

    if args.json_out:
        try:
            Path(args.json_out).write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n상세 JSON 저장: {args.json_out}")
        except OSError as exc:
            print(f"JSON 저장 실패(무시): {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
