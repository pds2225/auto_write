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


def _set_cell(tc, value: str, *, char_pr: str | None = None) -> None:
    """칸 텍스트만 교체. 원본 단락·런 속성 유지(한글 열림 안정성)."""
    sub = tc.find(_q("subList"))
    if sub is None:
        return
    p = next(sub.iter(_q("p")), None)
    if p is None:
        p = etree.SubElement(sub, _q("p"))
        p.set("id", "2147483648")
        p.set("paraPrIDRef", "17")
        p.set("styleIDRef", "0")
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
    run = next(p.iter(_q("run")), None)
    if run is None:
        run = etree.SubElement(p, _q("run"))
        run.set("charPrIDRef", char_pr or "51")
    elif char_pr is not None:
        run.set("charPrIDRef", char_pr)
    t = next(run.iter(_q("t")), None)
    if t is None:
        t = etree.SubElement(run, _q("t"))
    t.text = value
    # 줄배치 메타가 비면 한글이 거부하는 경우가 있어 최소 lineseg 유지
    lsa = p.find(_q("linesegarray"))
    if lsa is None:
        lsa = etree.SubElement(p, _q("linesegarray"))
    if next(lsa.iter(_q("lineseg")), None) is None:
        ls = etree.SubElement(lsa, _q("lineseg"))
        ls.set("textpos", "0")
        ls.set("vertpos", "0")
        ls.set("vertsize", "1000")
        ls.set("textheight", "1000")
        ls.set("baseline", "850")
        ls.set("spacing", "600")
        ls.set("horzpos", "0")
        ls.set("horzsize", "1000")
        ls.set("flags", "393216")


def _cell_text(tc) -> str:
    parts = [str(el.text or "") for el in tc.iter(_q("t"))]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _text_para(text: str, *, template: etree._Element | None = None) -> etree._Element:
    if template is not None:
        p = copy.deepcopy(template)
        for child in list(p):
            if child.tag == _q("run") or child.tag == _q("linesegarray"):
                p.remove(child)
    else:
        p = etree.Element(_q("p"))
        p.set("id", "0")
        p.set("paraPrIDRef", "29")
        p.set("styleIDRef", "0")
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
    run = etree.SubElement(p, _q("run"))
    run.set("charPrIDRef", "2")
    t = etree.SubElement(run, _q("t"))
    t.text = text
    lsa = etree.SubElement(p, _q("linesegarray"))
    ls = etree.SubElement(lsa, _q("lineseg"))
    ls.set("textpos", "0")
    ls.set("vertpos", "0")
    ls.set("vertsize", "1000")
    ls.set("textheight", "1000")
    ls.set("baseline", "850")
    ls.set("spacing", "600")
    ls.set("horzpos", "0")
    ls.set("horzsize", "1000")
    ls.set("flags", "393216")
    return p


def _next_table_id(root) -> str:
    ids = []
    for tbl in root.iter(_q("tbl")):
        raw = tbl.get("id")
        if raw and raw.isdigit():
            ids.append(int(raw))
    return str((max(ids) + 1) if ids else 2000000001)


def _is_consulting_table(tbl) -> bool:
    rows = list(tbl.iter(_q("tr")))
    if len(rows) < 20:
        return False
    header = "".join(_cell_text(c) for c in rows[0].iter(_q("tc")))
    if "유형" in header and "사업명" in header:
        return True
    # 헤더가 비어 있어도 4열·날짜 패턴 데이터 행이면 수행리스트로 본다
    for tr in rows[1:4]:
        cells = [_cell_text(c) for c in tr.iter(_q("tc"))]
        if len(cells) >= 4 and re.search(r"20\d{2}", cells[0]):
            return True
    return False


def _parse_consulting_stats(root) -> dict[str, str]:
    for tbl in root.iter(_q("tbl")):
        if not _is_consulting_table(tbl):
            continue
        rows = list(tbl.iter(_q("tr")))
        items: list[tuple[str, str, str, str]] = []
        for tr in rows[1:]:
            cells = [_cell_text(c) for c in tr.iter(_q("tc"))]
            if len(cells) < 4 or not any(cells):
                continue
            items.append((cells[0], cells[1], cells[2], cells[3]))
        if not items:
            continue
        orgs = {x[2] for x in items if x[2]}
        dates = [x[0] for x in items if x[0]]

        def _date_sort_key(d: str) -> tuple[int, int]:
            m = re.search(r"(20\d{2})\.(\d{1,2})", d)
            if m:
                return int(m.group(1)), int(m.group(2))
            m = re.search(r"(20\d{2})", d)
            return (int(m.group(1)), 0) if m else (0, 0)

        def _period_label(d: str) -> str:
            return re.split(r"~", d)[0].strip()

        if dates:
            min_d = min(dates, key=_date_sort_key)
            max_d = max(dates, key=_date_sort_key)
            period = f"{_period_label(min_d)} ~ {_period_label(max_d)}"
        else:
            period = ""
        return {
            "cases": str(len(items)),
            "companies": str(len(orgs)),
            "period": period,
            "amount": "[확인필요]",
            "items": items,
        }
    raise RuntimeError("컨설팅 수행리스트 표를 찾지 못했습니다")


def _make_summary_table(
    template_tbl, stats: dict[str, str], *, new_id: str
) -> etree._Element:
    """자격/교육 표(5×4) 구조를 그대로 복제해 셀 텍스트만 교체.

    열 수·셀주소·폭을 건드리면 한글이 파일을 거부할 수 있어
    colCnt=4 구조를 유지하고 뒤 2칸은 비운다.
    """
    tbl = copy.deepcopy(template_tbl)
    tbl.set("id", new_id)
    rows = list(tbl.findall(_q("tr")))
    rows_data = [
        ("실적 총괄", "컨설팅/멘토링 수행실적 합계", "", ""),
        ("총 컨설팅기간", stats["period"], "", ""),
        ("수행건수", f"{stats['cases']}건", "", ""),
        ("수행기업(기관)", f"{stats['companies']}개사", "", ""),
        ("컨설팅 매출(합계)", stats["amount"], "", ""),
    ]
    for tr, values in zip(rows, rows_data):
        cells = list(tr.findall(_q("tc")))
        for i, value in enumerate(values):
            if i >= len(cells):
                break
            _set_cell(cells[i], value, char_pr="2" if i == 0 else None)
    return tbl


def _clean_consulting_orphans(root, items: list[tuple[str, str, str, str]]) -> int:
    type_set = {x[1] for x in items}
    title_set = {x[3] for x in items}
    org_set = {x[2] for x in items}
    wrap = None
    for p in root.findall(_q("p")):
        tbl = p.find(".//" + _q("tbl"))
        if tbl is not None and _is_consulting_table(tbl):
            wrap = p
            break
    if wrap is None:
        return 0
    parent = wrap.getparent()
    if parent is None:
        return 0
    remove_ps: list[etree._Element] = []
    for sib in list(parent)[parent.index(wrap) + 1 :]:
        if sib.tag != _q("p"):
            continue
        if sib.find(".//" + _q("tbl")) is not None:
            break
        t_raw = "".join(x.text or "" for x in sib.iter(_q("t")))
        t = re.sub(r"\s+", "", t_raw)
        if not t:
            continue
        if t.startswith("["):
            break
        if t in {"일시", "유형", "수진기업/기관", "사업명"}:
            remove_ps.append(sib)
            continue
        if re.fullmatch(r"20\d{2}(\.\d{1,2})?(~\d{1,2})?", t):
            remove_ps.append(sib)
            continue
        if t in type_set and len(t) <= 12:
            remove_ps.append(sib)
            continue
        if t in title_set or t in org_set:
            remove_ps.append(sib)
    for p in remove_ps:
        parent.remove(p)
    return len(remove_ps)


def _patch_summary_and_cleanup(section_path: Path) -> list[str]:
    notes: list[str] = []
    root = etree.parse(str(section_path)).getroot()
    stats = _parse_consulting_stats(root)
    items = stats.pop("items")  # type: ignore[misc]

    already = any(
        "실적 총괄" in "".join(t.text or "" for t in tbl.iter(_q("t")))
        for tbl in root.iter(_q("tbl"))
    )
    if not already:
        template_tbl = None
        insert_parent = None
        insert_idx = None
        for p in root.iter(_q("p")):
            t = "".join(x.text or "" for x in p.iter(_q("t")))
            if "[컨설팅/멘토링]" in t:
                insert_parent = p.getparent()
                insert_idx = insert_parent.index(p)
                break
        for tbl in root.iter(_q("tbl")):
            if len(list(tbl.iter(_q("tr")))) == 5:
                h = "".join(_cell_text(c) for c in next(tbl.iter(_q("tr"))).iter(_q("tc")))
                if "자격" in h:
                    template_tbl = tbl
                    break
        if insert_parent is not None and insert_idx is not None and template_tbl is not None:
            consult_p = insert_parent[insert_idx]
            title_p = _text_para("[실적 총괄]", template=consult_p)
            summary_tbl = _make_summary_table(
                template_tbl, stats, new_id=_next_table_id(root)
            )
            # 자격/교육 표를 감싼 단락을 복제해 표만 교체(단락/런 속성 보존)
            wrap_src = None
            for p in root.findall(_q("p")):
                tbl = p.find(_q("run") + "/" + _q("tbl"))
                if tbl is None:
                    tbl = p.find(".//" + _q("tbl"
                    ))
                if tbl is template_tbl or (
                    tbl is not None
                    and "자격" in "".join(_cell_text(c) for c in next(tbl.iter(_q("tr"))).iter(_q("tc")))
                ):
                    wrap_src = p
                    break
            if wrap_src is None:
                wrap_src = consult_p
            wrap = copy.deepcopy(wrap_src)
            for run in list(wrap.findall(_q("run"))):
                for child in list(run):
                    if child.tag == _q("tbl"):
                        run.remove(child)
                        run.append(summary_tbl)
                        break
                else:
                    continue
                break
            else:
                run = etree.SubElement(wrap, _q("run"))
                run.set("charPrIDRef", "35")
                run.append(summary_tbl)
            insert_parent.insert(insert_idx, title_p)
            insert_parent.insert(insert_idx + 1, wrap)
            notes.append(
                "실적총괄표 추가: "
                f"기간 {stats['period']} / {stats['cases']}건 / {stats['companies']}개사 / 매출 {stats['amount']}"
            )
        else:
            notes.append("경고: 실적총괄표 삽입 위치를 찾지 못함")
    else:
        notes.append("실적총괄표 유지")

    removed = _clean_consulting_orphans(root, items)
    if removed:
        notes.append(f"수행리스트 표 아래 깨진 중복 단락 {removed}개 정리")

    etree.ElementTree(root).write(
        str(section_path), encoding="utf-8", xml_declaration=True, standalone=True
    )
    return notes


def _set_cell(tc, value: str, *, char_pr: str | None = None) -> None:
    """칸 텍스트만 교체. 원본 단락·런 속성을 최대한 유지하되 잔여 t 제거."""
    sub = tc.find(_q("subList"))
    if sub is None:
        return
    # 칸에 단락이 여러 개면 첫 단락만 남김(중복 글자 방지)
    paras = list(sub.findall(_q("p")))
    if not paras:
        p = etree.SubElement(sub, _q("p"))
        p.set("id", "2147483648")
        p.set("paraPrIDRef", "17")
        p.set("styleIDRef", "0")
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
        paras = [p]
    for extra in paras[1:]:
        sub.remove(extra)
    p = paras[0]
    runs = list(p.findall(_q("run")))
    if not runs:
        run = etree.SubElement(p, _q("run"))
        run.set("charPrIDRef", char_pr or "51")
        runs = [run]
    # 첫 런만 남기고 나머지 run 제거(텍스트가 여러 t/run에 쪼개진 경우 잔여 방지)
    keep = runs[0]
    if char_pr is not None:
        keep.set("charPrIDRef", char_pr)
    for extra in runs[1:]:
        # 표를 담은 run은 건드리지 않음
        if extra.find(_q("tbl")) is not None or extra.find(_q("pic")) is not None:
            continue
        p.remove(extra)
    for child in list(keep):
        if child.tag == _q("t"):
            keep.remove(child)
    t = etree.SubElement(keep, _q("t"))
    t.text = value
    lsa = p.find(_q("linesegarray"))
    if lsa is None:
        lsa = etree.SubElement(p, _q("linesegarray"))
    if next(lsa.iter(_q("lineseg")), None) is None:
        ls = etree.SubElement(lsa, _q("lineseg"))
        ls.set("textpos", "0")
        ls.set("vertpos", "0")
        ls.set("vertsize", "1000")
        ls.set("textheight", "1000")
        ls.set("baseline", "850")
        ls.set("spacing", "600")
        ls.set("horzpos", "0")
        ls.set("horzsize", "1000")
        ls.set("flags", "393216")


def _bump_row_addrs(tbl, from_row: int, delta: int = 1) -> None:
    for tr in tbl.findall(_q("tr")):
        for tc in tr.findall(_q("tc")):
            addr = tc.find(_q("cellAddr"))
            if addr is None:
                continue
            row = int(addr.get("rowAddr", "0"))
            if row >= from_row:
                addr.set("rowAddr", str(row + delta))


def _patch_management_fields(section_path: Path) -> list[str]:
    notes: list[str] = []
    root = etree.parse(str(section_path)).getroot()
    first_tbl = next(root.iter(_q("tbl")))
    rows = list(first_tbl.findall(_q("tr")))
    if len(rows) < 3:
        return ["경고: 상단 표 구조 인식 실패"]

    cells = list(rows[1].findall(_q("tc")))
    if len(cells) >= 3:
        _set_cell(
            cells[2],
            "■ 마케팅      ■ 재무·자금      ■ 전략·기획      ■ 창업·투자유치",
        )
        notes.append("경영부문 체크 반영")

    row2_text = "".join(t.text or "" for t in rows[2].iter(_q("t")))
    if "경영분야" not in row2_text:
        lecture_row = rows[2]
        lecture_addr = None
        for tc in lecture_row.findall(_q("tc")):
            addr = tc.find(_q("cellAddr"))
            if addr is not None:
                lecture_addr = int(addr.get("rowAddr", "2"))
                break
        if lecture_addr is None:
            lecture_addr = 2

        # 기존 강의분야 행부터 아래 rowAddr를 +1 밀고, 그 자리에 경영분야 삽입
        _bump_row_addrs(first_tbl, from_row=lecture_addr, delta=1)
        new_row = copy.deepcopy(lecture_row)
        # deepcopy 후 lecture_row 도 이미 +1된 주소를 가지므로 new_row를 lecture_addr로 고정
        for tc in new_row.findall(_q("tc")):
            addr = tc.find(_q("cellAddr"))
            if addr is not None:
                addr.set("rowAddr", str(lecture_addr))
        new_cells = list(new_row.findall(_q("tc")))
        if len(new_cells) >= 2:
            _set_cell(new_cells[0], "경영분야")
            _set_cell(
                new_cells[1],
                "정부지원사업·정책자금·투자유치·창업/스타트업·사업화·수출·R&D",
                char_pr="52",
            )
            for extra in new_cells[2:]:
                _set_cell(extra, "")
            lecture_row.addprevious(new_row)
            # 강의분야 행 재확인(이미 _bump로 +1됨)
            for tc in lecture_row.findall(_q("tc")):
                addr = tc.find(_q("cellAddr"))
                if addr is not None and int(addr.get("rowAddr", "0")) != lecture_addr + 1:
                    addr.set("rowAddr", str(lecture_addr + 1))
            actual = len(list(first_tbl.findall(_q("tr"))))
            first_tbl.set("rowCnt", str(actual))
            notes.append(f"경영분야 행 추가 (rowCnt={actual})")
        else:
            notes.append("경고: 경영분야 행 셀 부족")
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
                if not _is_consulting_table(tbl):
                    continue
                consult_rows = len(rows) - 1
                break
            sec_date_orphans = 0
            for p in root.findall(_q("p")):
                if p.find(".//" + _q("tbl")) is not None:
                    continue
                t = re.sub(r"\s+", "", "".join(x.text or "" for x in p.iter(_q("t"))))
                if re.fullmatch(r"20\d{2}(\.\d{1,2})?(~\d{1,2})?", t):
                    sec_date_orphans += 1
            if sec_date_orphans > 0:
                return False, f"표 밖 날짜 단락 잔존: {sec_date_orphans}개"
            if consult_rows < 26:
                return False, f"수행리스트 표 행 부족: {consult_rows}건"
            pics = len(list(root.iter(_q("pic"))))
            if pics > 0:
                return False, f"타임라인 그림 잔존: {pics}장"
            summary_found = any(
                "실적 총괄" in "".join(t.text or "" for t in tbl.iter(_q("t")))
                for tbl in root.iter(_q("tbl"))
            )
            if not summary_found:
                return False, "실적총괄표 미발견"
            ids = [tbl.get("id") for tbl in root.iter(_q("tbl"))]
            if len(ids) != len(set(ids)):
                return False, f"표 ID 중복: {ids}"
            return True, f"표 {consult_rows}건, 실적총괄표 OK, 그림 0장, 표ID {len(ids)}개"
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
    notes.extend(_patch_summary_and_cleanup(sec))

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
