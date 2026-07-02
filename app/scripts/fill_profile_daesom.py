"""프로필 양식(모두의장 전문가) — 박다솜 기본정보+확인된 경력/자격 채움."""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_write.services.hwp_com_fill import _SAVE_FORMATS, _convert_via_com
from auto_write.services.hwpx_fill import fill_hwpx

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _q(tag: str) -> str:
    return f"{{{_HP}}}{tag}"


def _cell_text(tc) -> str:
    parts = [str(el.text or "") for el in tc.iter(_q("t"))]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _set_cell(tc, value: str) -> None:
    ts = list(tc.iter(_q("t")))
    if ts:
        ts[0].text = value
        for extra in ts[1:]:
            extra.text = ""
        return
    paras = list(tc.iter(_q("p")))
    if not paras:
        return
    p = paras[0]
    runs = list(p.iter(_q("run")))
    if runs:
        run = runs[0]
    else:
        run = etree.SubElement(p, _q("run"))
        run.set("charPrIDRef", "0")
    t = etree.SubElement(run, _q("t"))
    t.text = value


def _set_row(cells, values: list[str]) -> None:
    for c, v in zip(cells, values):
        _set_cell(c, v)


def _patch_hwpx(hwpx: Path) -> tuple[Path, list[str]]:
    notes: list[str] = []
    work = hwpx.parent / "_edit"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    with zipfile.ZipFile(hwpx, "r") as zin:
        zin.extractall(work)

    sec = next(work.glob("Contents/section*.xml"))
    root = etree.parse(str(sec)).getroot()
    tbl = next(root.iter(_q("tbl")))
    rows = list(tbl.iter(_q("tr")))

    def row_texts(tr) -> list[str]:
        return [_cell_text(c) for c in tr.iter(_q("tc"))]

    for tr in rows:
        cells = list(tr.iter(_q("tc")))
        texts = row_texts(tr)

        if texts == ["198", "", "", ""]:
            _set_row(
                cells,
                ["[확인필요]", "[확인필요]", "[확인필요]", "경영컨설팅(석사)"],
            )
            notes.append("학력: 경영컨설팅 석사, 학교/연월 [확인필요]")

        if len(texts) == 5 and texts[0] == "소속기관" and not texts[2].strip():
            texts[2] = "오토라이트"
            _set_cell(cells[2], "오토라이트")
            notes.append("소속기관: 오토라이트")

        if texts == ["", "관", "", ""]:
            _set_cell(cells[1], "중소벤처기업부 경영지도사")
            notes.append("자격: 중소벤처기업부 경영지도사")

    # 경력 데이터행: 헤더(12행) 다음 빈 4칸 행만 순서대로 채움(11행은 학력 보조행이라 제외)    career_idx = 0
    career_rows = [
        (["[확인필요]", "[확인필요]", "컨설팅사", "대표·선임컨설턴트(경영컨설팅 5년+)"],
         "경력1: 컨설팅사, 연월 [확인필요]"),
        (["[확인필요]", "[확인필요]", "저축은행", "기업대출·투자금융"],
         "경력2: 저축은행, 연월 [확인필요]"),
        (["[확인필요]", "[확인필요]", "씨엔티테크", "스타트업 AC 심사역"],
         "경력3: 씨엔티테크 AC 심사역, 연월 [확인필요]"),
    ]
    for ri, tr in enumerate(rows):
        if ri <= 12:
            continue
        cells = list(tr.iter(_q("tc")))
        texts = [_cell_text(c) for c in cells]
        if texts != ["", "", "", ""] or career_idx >= len(career_rows):
            continue
        vals, note = career_rows[career_idx]
        _set_row(cells, vals)
        notes.append(note)
        career_idx += 1
        if career_idx >= len(career_rows):
            break

    etree.ElementTree(root).write(        str(sec), encoding="utf-8", xml_declaration=True, standalone=True
    )

    out_hwpx = hwpx.with_name(hwpx.stem + "_rows.hwpx")
    with zipfile.ZipFile(out_hwpx, "w", zipfile.ZIP_DEFLATED) as zout:
        mimetype = work / "mimetype"
        if mimetype.exists():
            zout.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for p in sorted(work.rglob("*")):
            if p.is_file() and p.name != "mimetype":
                zout.write(p, p.relative_to(work).as_posix())
    shutil.rmtree(work)
    return out_hwpx, notes


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    src = Path(r"C:\Users\ekth3\Downloads\프로필 양식 샘플_개인것 기본작성하기.hwp")    out = Path(r"D:\auto_write\results\프로필_박다솜_작성본.hwp")
    dl = Path(r"C:\Users\ekth3\Downloads\프로필_박다솜_작성본.hwp")

    identity = {
        "성명": "박다솜",
        "생년월일": "1992.04.06",
        "휴대폰번호": "010-2930-6666",
        "연락처": "010-2930-6666",
        "이메일": "pds2225@naver.com",
        "주소": "어울마당로3길 11, 301호",
        "소속기관": "오토라이트",
        "직책": "대표",
        "부서": "경영",
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="profile_fill_") as td:
        work = Path(td)
        mid = work / "mid.hwpx"
        _convert_via_com(src, mid, _SAVE_FORMATS[".hwpx"])
        filled = work / "filled.hwpx"
        fr = fill_hwpx(mid, filled, identity=identity, replacements={})
        row_hwpx, row_notes = _patch_hwpx(filled)
        tmp_hwp = work / "out.hwp"
        _convert_via_com(row_hwpx, tmp_hwp, _SAVE_FORMATS[".hwp"])
        shutil.copyfile(tmp_hwp, out)
        shutil.copyfile(tmp_hwp, dl)

    print(f"출력: {out}")
    print(f"복사: {dl}")
    print(f"라벨 매칭 채움: {fr.filled_count}칸")
    for k, v in fr.filled.items():
        print(f"  {k} = {v}")
    for n in row_notes:
        print(f"  + {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
