"""v4 백업 → v5 복구: 경영분야만 반영, 수행리스트는 원본 표 유지(그림 변환 없음)."""
from __future__ import annotations

import copy
import re
import shutil
import sys
import zipfile
from pathlib import Path

from lxml import etree

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _q(tag: str) -> str:
    return f"{{{_HP}}}{tag}"


def _set_cell(tc, value: str, *, char_pr: str = "51") -> None:
    sub = tc.find(_q("subList"))
    if sub is None:
        return
    for old_p in list(sub):
        sub.remove(old_p)
    p = etree.SubElement(sub, _q("p"))
    p.set("id", "2147483648")
    p.set("paraPrIDRef", "45")
    p.set("styleIDRef", "19")
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")
    run = etree.SubElement(p, _q("run"))
    run.set("charPrIDRef", char_pr)
    t = etree.SubElement(run, _q("t"))
    t.text = value
    etree.SubElement(p, _q("linesegarray"))


def _patch_management_fields(section_path: Path) -> list[str]:
    notes: list[str] = []
    root = etree.parse(str(section_path)).getroot()
    first_tbl = next(root.iter(_q("tbl")))
    rows = list(first_tbl.iter(_q("tr")))
    if len(rows) < 3:
        return ["경고: 상단 표 구조 인식 실패"]

    cells = list(rows[1].iter(_q("tc")))
    if len(cells) >= 3:
        _set_cell(
            cells[2],
            "■ 마케팅      ■ 재무·자금      ■ 전략·기획      ■ 창업·투자유치",
        )
        notes.append("경영부문 체크 반영")

    # 이미 경영분야 행이 있으면 스킵
    row2_text = "".join(t.text or "" for t in rows[2].iter(_q("t")))
    if "경영분야" not in row2_text:
        new_row = copy.deepcopy(rows[2])
        new_cells = list(new_row.iter(_q("tc")))
        if len(new_cells) >= 2:
            _set_cell(new_cells[0], "경영분야")
            _set_cell(
                new_cells[1],
                "정부지원사업·정책자금·투자유치·창업/스타트업·사업화·수출·R&D",
                char_pr="52",
            )
            for extra in new_cells[2:]:
                _set_cell(extra, "")
            rows[1].addnext(new_row)
            notes.append("경영분야 행 추가")
    else:
        notes.append("경영분야 행 유지")

    etree.ElementTree(root).write(
        str(section_path), encoding="utf-8", xml_declaration=True, standalone=True
    )
    return notes


def _verify_hwpx(path: Path) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                return False, f"손상 ZIP 엔트리: {bad}"
            sec = [n for n in z.namelist() if n.startswith("Contents/section")][0]
            root = etree.fromstring(z.read(sec))
            tbls = list(root.iter(_q("tbl")))
            consult_rows = 0
            for tbl in tbls:
                rows = list(tbl.iter(_q("tr")))
                if len(rows) < 20:
                    continue
                header = "".join(
                    "".join(t.text or "" for t in c.iter(_q("t")))
                    for c in rows[0].iter(_q("tc"))
                )
                if "일 시" in header and "유형" in header and "사업명" in header:
                    consult_rows = len(rows) - 1
                    break
            pics = len(list(root.iter(_q("pic"))))
            if consult_rows < 26:
                return False, f"수행리스트 표 행 부족: {consult_rows}건"
            if pics > 0:
                return False, f"타임라인 그림 잔존: {pics}장"
            return True, f"표 {consult_rows}건, 그림 0장"
    except Exception as exc:
        return False, str(exc)


def restore_profile(src: Path, out: Path) -> list[str]:
    if src.resolve() == out.resolve():
        raise ValueError("출력 경로는 원본과 달라야 합니다")
    work = out.parent / "_restore_profile_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    with zipfile.ZipFile(src, "r") as zin:
        zin.extractall(work)

    sec = next(work.glob("Contents/section*.xml"))
    notes = _patch_management_fields(sec)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        mimetype = work / "mimetype"
        if mimetype.exists():
            zout.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for p in sorted(work.rglob("*")):
            if p.is_file() and p.name != "mimetype":
                zout.write(p, p.relative_to(work).as_posix())
    shutil.rmtree(work)

    ok, msg = _verify_hwpx(out)
    notes.append(f"검증: {'통과' if ok else '실패'} — {msg}")
    if not ok:
        raise RuntimeError(msg)
    return notes


def _resolve_src() -> Path:
    backup_dir = Path(r"D:\auto_write\results\backup_profile_v4")
    if backup_dir.exists():
        cands = sorted(backup_dir.glob("*.hwpx"), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            return cands[0]
    desk = Path(
        r"C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\01. 경영지도사 이력서"
    )
    v4 = desk / "프로필 양식_박다솜_v4.hwpx"
    if v4.exists():
        return v4
    raise FileNotFoundError("v4 백업/원본을 찾지 못했습니다")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    src = _resolve_src()
    desk = Path(
        r"C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\01. 경영지도사 이력서"
    )
    out = desk / "프로필 양식_박다솜_v5.hwpx"
    mirror = Path(r"D:\auto_write\results") / out.name

    notes = restore_profile(src, out)
    mirror.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out, mirror)

    print(f"소스: {src}")
    print(f"출력: {out}")
    print(f"미러: {mirror}")
    for n in notes:
        print(f"  + {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
