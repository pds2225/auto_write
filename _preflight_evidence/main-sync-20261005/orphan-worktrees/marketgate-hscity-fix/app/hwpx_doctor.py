"""hwpx_doctor.py — 한글이 못 여는 hwpx 를 진단·수정하는 CLI.

한글은 zip/XML 이 멀쩡해도 표 격자(rowAddr/colAddr) 충돌·ID 참조 오류·itemCnt
불일치가 있으면 문서 열기를 거부한다. 이 도구는 그 '의미 규칙'을 검사하고,
자동 교정 가능한 결함(깨진 표 격자)을 고쳐 원본 서식 그대로의 수정본을 만든다.

사용법 (PowerShell):
    cd D:\auto_write\app
  # 진단만 (무엇이 문제인지)
    python hwpx_doctor.py diagnose "C:\경로\문서.hwpx"
  # 수정본 생성 (원본 보존, 표 격자 자동 교정 + 레이아웃 캐시 정리)
    python hwpx_doctor.py repair "C:\경로\문서.hwpx"                 # → 문서_수정.hwpx
    python hwpx_doctor.py repair "문서.hwpx" -o "고친것.hwpx"

종료코드: 0=정상/수정성공, 2=결함있음(진단)/자동교정 실패, 1=입력오류.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auto_write.services.hwpx_layout_fix import check_hwpx_semantics, finalize_layout_hwpx


def _print_report(path: Path, rep: dict) -> None:
    print(f"=== hwpx 의미 검증: {path.name} ===")
    print(f"  섹션 수         : {rep['section_count']}")
    ic = rep["itemcnt_issues"]
    print(f"  itemCnt 일치    : {'OK' if not ic else '불일치 ' + str(ic)}")
    dr = rep["dangling_refs"]
    print(f"  ID 참조 정합    : {'OK' if not dr else '정의없음 ' + str(dr)}")
    bt = rep["broken_tables"]
    if not bt:
        print("  표 격자 타일링  : OK (전부 정상)")
    else:
        print(f"  표 격자 타일링  : ❌ {len(bt)}개 깨짐")
        for t in bt:
            print(f"     표#{t['index']} ({t['rows']}x{t['cols']}): "
                  f"겹침{t['overlaps']} 빈칸{t['empties']} 범위초과{t['oob']}")
    print(f"\n  → 판정: {'정상(한글에서 열림)' if rep['ok'] else '결함 있음(한글 열기 거부 가능)'}")


def _cmd_diagnose(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"파일 없음: {path}", file=sys.stderr)
        return 1
    rep = check_hwpx_semantics(path)
    _print_report(path, rep)
    if not rep["ok"] and rep["broken_tables"] and not rep["itemcnt_issues"] and not rep["dangling_refs"]:
        print("\n  💡 표 격자 결함은 자동 교정 가능: python hwpx_doctor.py repair \"" + str(path) + "\"")
    return 0 if rep["ok"] else 2


def _cmd_repair(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"파일 없음: {path}", file=sys.stderr)
        return 1
    out = Path(args.output) if args.output else path.with_name(path.stem + "_수정" + path.suffix)
    if out.resolve() == path.resolve():
        print("출력 경로가 원본과 같습니다(원본 보존).", file=sys.stderr)
        return 1

    before = check_hwpx_semantics(path)
    # 표 격자 교정 + 레이아웃 캐시 정리(한글 재계산). 자간·빈칸병합은 건드리지 않음(최소 변경).
    stats = finalize_layout_hwpx(
        path, out, repair_grid=True, relax_lines=True,
        merge_empty=False, spacing_floor=None)
    after = check_hwpx_semantics(out)

    print(f"진단(수정 전): 깨진 표 {len(before['broken_tables'])}개")
    print(f"교정: 표 격자 {stats['grid_cells_fixed']}칸 재주소화 · "
          f"레이아웃 캐시 {stats['linesegarray_removed']}개 정리")
    print(f"검증(수정 후): 깨진 표 {len(after['broken_tables'])}개")
    print(f"저장: {out}")
    if after["ok"]:
        print("→ ✅ 의미 규칙 전부 통과 — 한글에서 열립니다(원본 서식 유지).")
        return 0
    if after["broken_tables"]:
        print("→ ⚠ 일부 표는 병합 구조라 자동 교정 제외됨 — 수동 확인 필요.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hwpx_doctor", description="한글 hwpx 진단·수정")
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("diagnose", help="의미 규칙(격자·ID참조·itemCnt) 검사")
    d.add_argument("file", help="검사할 .hwpx")
    d.set_defaults(func=_cmd_diagnose)
    r = sub.add_parser("repair", help="깨진 표 격자 자동 교정한 수정본 생성")
    r.add_argument("file", help="고칠 .hwpx")
    r.add_argument("-o", "--output", help="수정본 저장 경로(기본: <이름>_수정.hwpx)")
    r.set_defaults(func=_cmd_repair)
    return p


def main(argv: list[str] | None = None) -> int:
    from auto_write.utils import force_utf8_console
    force_utf8_console()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
