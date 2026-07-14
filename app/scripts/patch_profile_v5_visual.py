"""프로필 v4 → v5: 경영분야 추가 + (옵션) 컨설팅 수행리스트 타임라인 그림.

⚠ 기본 복구는 restore_profile_v5_table.py 사용 — 표 유지, 그림 변환 없음.
"""
from __future__ import annotations

import copy
import re
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from lxml import etree
from matplotlib.patches import FancyBboxPatch  # noqa: E402

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HC = "http://www.hancom.co.kr/hwpml/2011/core"
_OPF = "http://www.idpf.org/2007/opf/"
_HWP_PER_PX = 75

_TYPE_COLORS = {
    "투자유치": "#4C72B0",
    "금융": "#55A868",
    "사업화": "#C44E52",
    "수출": "#8172B2",
    "컨설팅": "#64B5CD",
    "창업": "#E5A855",
    "코칭": "#8C8C8C",
    "멘토링": "#BCBD22",
    "R&D": "#17BECF",
    "현장클리닉": "#E377C2",
    "회계멘토": "#7F7F7F",
    "IR컨설팅": "#2CA02C",
    "IR자문": "#9467BD",
    "컨설턴트": "#8C564B",
    "고객진단(CEM)": "#D62728",
    "총괄": "#1F77B4",
}


def _q(tag: str) -> str:
    return f"{{{_HP}}}{tag}"


def _row_addr(tr) -> int:
    """행(tr)의 논리 행번호(첫 cellAddr rowAddr). 격자 정합용."""
    for tc in tr.findall(_q("tc")):
        a = tc.find(_q("cellAddr"))
        if a is not None:
            return int(a.get("rowAddr", "0"))
    return 0


def _qc(tag: str) -> str:
    return f"{{{_HC}}}{tag}"


def _cell_text(tc) -> str:
    parts = [str(el.text or "") for el in tc.iter(_q("t"))]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


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


def _parse_consulting_rows(tbl) -> list[dict[str, str]]:
    rows = list(tbl.iter(_q("tr")))
    out: list[dict[str, str]] = []
    for tr in rows[1:]:
        cells = [_cell_text(c) for c in tr.iter(_q("tc"))]
        if len(cells) < 4:
            continue
        if not any(cells):
            continue
        out.append(
            {
                "date": cells[0],
                "type": cells[1],
                "org": cells[2],
                "title": cells[3],
            }
        )
    return out


def _sort_key(date: str) -> tuple[int, int]:
    nums = [int(x) for x in re.findall(r"\d{4}", date)]
    year = nums[0] if nums else 0
    month = 0
    m = re.search(r"\.(\d{1,2})", date)
    if m:
        month = int(m.group(1))
    return (-year, -month)


def _timeline_png(path: Path, items: list[dict[str, str]], *, title: str) -> None:
    matplotlib.rcParams["font.family"] = "Malgun Gothic"
    matplotlib.rcParams["axes.unicode_minus"] = False
    n = len(items)
    fig_h = max(8.0, 0.42 * n + 1.8)
    fig, ax = plt.subplots(figsize=(10.5, fig_h))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, n + 1)
    ax.axis("off")
    ax.set_title(title, fontsize=15, fontweight="bold", pad=14)

    x_line = 2.2
    for i, item in enumerate(items):
        y = n - i
        color = _TYPE_COLORS.get(item["type"], "#4C72B0")
        if i < n - 1:
            ax.plot([x_line, x_line], [y - 0.35, y - 0.65], color="#B0B0B0", lw=2, zorder=1)
        ax.scatter([x_line], [y], s=180, color=color, zorder=3, edgecolors="white", linewidths=1.2)
        ax.text(0.05, y, item["date"], va="center", ha="left", fontsize=9.5, fontweight="bold")
        badge = FancyBboxPatch(
            (2.55, y - 0.18),
            1.15,
            0.36,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            linewidth=0,
            facecolor=color,
            alpha=0.18,
            zorder=2,
        )
        ax.add_patch(badge)
        ax.text(3.12, y, item["type"], va="center", ha="center", fontsize=8.8, color=color, fontweight="bold")
        ax.text(3.95, y + 0.08, item["org"], va="center", ha="left", fontsize=9.3, fontweight="bold")
        ax.text(3.95, y - 0.12, item["title"], va="center", ha="left", fontsize=8.8, color="#333333")

    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _png_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as im:
        return im.size


def _make_pic_para(image_id: str, binary_ref: str, width_px: int, height_px: int, *, inst_seed: int) -> etree._Element:
    org_w = width_px * _HWP_PER_PX
    org_h = height_px * _HWP_PER_PX
    disp_w = min(org_w, 46800)
    scale = disp_w / org_w
    disp_h = int(org_h * scale)

    p = etree.Element(_q("p"))
    p.set("id", "2147483648")
    p.set("paraPrIDRef", "45")
    p.set("styleIDRef", "19")
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")

    run = etree.SubElement(p, _q("run"))
    run.set("charPrIDRef", "51")
    pic = etree.SubElement(run, _q("pic"))
    pic.set("id", str(inst_seed))
    pic.set("zOrder", "1")
    pic.set("numberingType", "PICTURE")
    pic.set("textWrap", "TOP_AND_BOTTOM")
    pic.set("textFlow", "BOTH_SIDES")
    pic.set("lock", "0")
    pic.set("dropcapstyle", "None")
    pic.set("href", "")
    pic.set("groupLevel", "0")
    pic.set("instid", str(inst_seed + 1))
    pic.set("reverse", "0")

    offset = etree.SubElement(pic, _q("offset"))
    offset.set("x", "0")
    offset.set("y", "0")
    org = etree.SubElement(pic, _q("orgSz"))
    org.set("width", str(org_w))
    org.set("height", str(org_h))
    cur = etree.SubElement(pic, _q("curSz"))
    cur.set("width", str(disp_w))
    cur.set("height", str(disp_h))

    flip = etree.SubElement(pic, _q("flip"))
    flip.set("horizontal", "0")
    flip.set("vertical", "0")
    rot = etree.SubElement(pic, _q("rotationInfo"))
    rot.set("angle", "0")
    rot.set("centerX", str(disp_w // 2))
    rot.set("centerY", str(disp_h // 2))
    rot.set("rotateimage", "1")

    ri = etree.SubElement(pic, _q("renderingInfo"))
    for tag, vals in (
        ("transMatrix", ("1", "0", "0", "0", "1", "0")),
        ("scaMatrix", (f"{scale:.6f}", "0", "0", "0", f"{scale:.6f}", "0")),
        ("rotMatrix", ("1", "0", "0", "0", "1", "0")),
    ):
        el = etree.SubElement(ri, _qc(tag))
        for i, v in enumerate(vals):
            el.set(f"e{i + 1}", v)

    img = etree.SubElement(pic, _qc("img"))
    img.set("binaryItemIDRef", binary_ref)
    img.set("bright", "0")
    img.set("contrast", "0")
    img.set("effect", "REAL_PIC")
    img.set("alpha", "0")

    rect = etree.SubElement(pic, _q("imgRect"))
    for name, x, y in (("pt0", 0, 0), ("pt1", org_w, 0), ("pt2", org_w, org_h), ("pt3", 0, org_h)):
        pt = etree.SubElement(rect, _qc(name))
        pt.set("x", str(x))
        pt.set("y", str(y))
    clip = etree.SubElement(pic, _q("imgClip"))
    clip.set("left", "0")
    clip.set("right", str(org_w))
    clip.set("top", "0")
    clip.set("bottom", str(org_h))
    margin = etree.SubElement(pic, _q("inMargin"))
    for side in ("left", "right", "top", "bottom"):
        margin.set(side, "0")
    dim = etree.SubElement(pic, _q("imgDim"))
    dim.set("dimwidth", str(org_w))
    dim.set("dimheight", str(org_h))
    etree.SubElement(pic, _q("effects"))
    sz = etree.SubElement(pic, _q("sz"))
    sz.set("width", str(disp_w))
    sz.set("widthRelTo", "ABSOLUTE")
    sz.set("height", str(disp_h))
    sz.set("heightRelTo", "ABSOLUTE")
    sz.set("protect", "0")
    pos = etree.SubElement(pic, _q("pos"))
    pos.set("treatAsChar", "1")
    pos.set("affectLSpacing", "0")
    pos.set("flowWithText", "1")
    pos.set("allowOverlap", "0")
    pos.set("holdAnchorAndSO", "0")
    pos.set("vertRelTo", "PARA")
    pos.set("horzRelTo", "PARA")
    pos.set("vertAlign", "TOP")
    pos.set("horzAlign", "LEFT")
    pos.set("vertOffset", "0")
    pos.set("horzOffset", "0")
    outm = etree.SubElement(pic, _q("outMargin"))
    for side in ("left", "right", "top", "bottom"):
        outm.set(side, "0")
    comment = etree.SubElement(pic, _q("shapeComment"))
    comment.text = f"수행리스트 타임라인 ({binary_ref})"
    etree.SubElement(p, _q("linesegarray"))
    return p


def _text_para(text: str, *, bold: bool = False) -> etree._Element:
    p = etree.Element(_q("p"))
    p.set("id", "2147483648")
    p.set("paraPrIDRef", "45")
    p.set("styleIDRef", "19")
    p.set("pageBreak", "0")
    p.set("columnBreak", "0")
    p.set("merged", "0")
    run = etree.SubElement(p, _q("run"))
    run.set("charPrIDRef", "52" if bold else "51")
    t = etree.SubElement(run, _q("t"))
    t.text = text
    etree.SubElement(p, _q("linesegarray"))
    return p


def _add_manifest_image(hpf_root, image_id: str, href: str) -> None:
    manifest = hpf_root.find(f".//{{{_OPF}}}manifest")
    if manifest is None:
        return
    item = etree.SubElement(manifest, f"{{{_OPF}}}item")
    item.set("id", image_id)
    item.set("href", href)
    item.set("media-type", "image/png")
    item.set("isEmbeded", "1")


def _patch_section(section_path: Path, assets: list[tuple[str, Path]], consulting: list[dict[str, str]]) -> list[str]:
    notes: list[str] = []
    root = etree.parse(str(section_path)).getroot()

    # 1) 경영분야: 경영부문 체크 + 경영분야 행 삽입
    first_tbl = next(root.iter(_q("tbl")))
    rows = list(first_tbl.iter(_q("tr")))
    if len(rows) >= 2:
        cells = list(rows[1].iter(_q("tc")))
        if len(cells) >= 3:
            _set_cell(
                cells[2],
                "■ 마케팅      ■ 재무·자금      ■ 전략·기획      ■ 창업·투자유치",
            )
            notes.append("경영부문 체크: 마케팅·재무·전략·창업/투자유치")

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
            # 행 삽입 시 격자 정합 필수: 삽입 위치 이후 논리행 rowAddr +1 밀고,
            # 새 행 rowAddr 고정, rowCnt +1. 이 처리를 빠뜨리면 새 행이 아래 행과
            # 같은 rowAddr 를 가져 격자가 겹치고 한글이 문서 열기를 거부한다
            # (실측 프로필 표 결함의 근본 원인 — deepcopy 한 행이 원본 rowAddr 를 유지).
            insert_addr = _row_addr(rows[1]) + 1
            for tr in first_tbl.findall(_q("tr")):
                if _row_addr(tr) >= insert_addr:
                    for tc in tr.findall(_q("tc")):
                        a = tc.find(_q("cellAddr"))
                        if a is not None:
                            a.set("rowAddr", str(int(a.get("rowAddr", "0")) + 1))
            for tc in new_row.findall(_q("tc")):
                a = tc.find(_q("cellAddr"))
                if a is not None:
                    a.set("rowAddr", str(insert_addr))
            rows[1].addnext(new_row)
            first_tbl.set(
                "rowCnt", str(int(first_tbl.get("rowCnt") or str(len(rows))) + 1))
            notes.append("경영분야 행 추가 (rowAddr/rowCnt 정합)")

    # 2) 컨설팅 표 → 타임라인 그림 + 깨진 단락 정리
    target_tbl = None
    target_p = None
    for p in root.iter(_q("p")):
        tbl = p.find(".//" + _q("tbl"))
        if tbl is None:
            continue
        header = "".join(_cell_text(c) for c in next(tbl.iter(_q("tr"))).iter(_q("tc")))
        if "일 시" in header and "유형" in header and "사업명" in header and len(list(tbl.iter(_q("tr")))) >= 20:
            target_tbl = tbl
            target_p = p
            break
    if target_p is None or target_tbl is None:
        notes.append("경고: 컨설팅 수행리스트 표를 찾지 못함")
        etree.ElementTree(root).write(
            str(section_path), encoding="utf-8", xml_declaration=True, standalone=True
        )
        return notes

    parent = target_p.getparent()
    insert_at = parent.index(target_p)

    new_nodes: list[etree._Element] = []
    new_nodes.append(_text_para("※ 아래 도식은 컨설팅/멘토링 수행리스트(27건)를 날짜순으로 이어 붙인 타임라인입니다."))
    seed = int(uuid.uuid4().int % 1_000_000_000)
    for i, (image_id, png_path) in enumerate(assets):
        if i > 0:
            new_nodes.append(_text_para("▼ 이어짐", bold=True))
        w, h = _png_size(png_path)
        new_nodes.append(_make_pic_para(image_id, image_id, w, h, inst_seed=seed + i * 17))
    for node in new_nodes:
        parent.insert(insert_at, node)
        insert_at += 1
    parent.remove(target_p)
    notes.append(f"수행리스트 표 제거 → 타임라인 그림 {len(assets)}장 삽입")

    # 컨설팅 표 직후~다음 섹션 전까지만 중복 단락(일시/유형/...) 제거
    remove_ps: list[etree._Element] = []
    in_consult_tail = False
    type_set = set(x["type"] for x in consulting)
    title_set = set(x["title"] for x in consulting)
    org_set = set(x["org"] for x in consulting)
    for p in list(root.iter(_q("p"))):
        if p.find(".//" + _q("tbl")) is not None:
            in_consult_tail = False
            continue
        t_raw = "".join(x.text or "" for x in p.iter(_q("t")))
        t = re.sub(r"\s+", "", t_raw)
        if "[컨설팅/멘토링]" in t_raw:
            in_consult_tail = True
            continue
        if not in_consult_tail:
            continue
        if t.startswith("[") or "타임라인" in t_raw or "이어짐" in t_raw:
            in_consult_tail = False
            continue
        if not t:
            continue
        if t in {"일시", "유형", "수진기업/기관", "사업명"}:
            remove_ps.append(p)
            continue
        if re.fullmatch(r"20\d{2}(\.\d{1,2})?(~\d{1,2})?", t):
            remove_ps.append(p)
            continue
        if t in type_set and len(t) <= 12:
            remove_ps.append(p)
            continue
        if t in title_set or t in org_set:
            remove_ps.append(p)
    for p in remove_ps:
        par = p.getparent()
        if par is not None:
            par.remove(p)
    if remove_ps:
        notes.append(f"깨진 중복 단락 {len(remove_ps)}개 정리")

    etree.ElementTree(root).write(
        str(section_path), encoding="utf-8", xml_declaration=True, standalone=True
    )
    return notes


def patch_profile_v5(src: Path, out: Path) -> list[str]:
    if src.resolve() == out.resolve():
        raise ValueError("출력 경로는 원본과 달라야 합니다")
    work = out.parent / "_patch_profile_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    with zipfile.ZipFile(src, "r") as zin:
        zin.extractall(work)

    sec = next(work.glob("Contents/section*.xml"))
    root = etree.parse(str(sec)).getroot()
    consulting: list[dict[str, str]] = []
    for tbl in root.iter(_q("tbl")):
        header = "".join(_cell_text(c) for c in next(tbl.iter(_q("tr"))).iter(_q("tc")))
        if "일 시" in header and "유형" in header and "사업명" in header and len(list(tbl.iter(_q("tr")))) >= 20:
            consulting = _parse_consulting_rows(tbl)
            break
    if not consulting:
        raise RuntimeError("컨설팅 수행리스트 데이터를 읽지 못했습니다")

    consulting.sort(key=lambda x: _sort_key(x["date"]))
    mid = max(1, len(consulting) // 2)
    chunks = [consulting[:mid], consulting[mid:]] if len(consulting) > 14 else [consulting]

    asset_dir = work / "BinData"
    asset_dir.mkdir(exist_ok=True)
    assets: list[tuple[str, Path]] = []
    for i, chunk in enumerate(chunks, start=1):
        image_id = f"image{i}"
        png = asset_dir / f"{image_id}.png"
        title = f"컨설팅/멘토링 수행리스트 ({i}/{len(chunks)})"
        _timeline_png(png, chunk, title=title)
        assets.append((image_id, png))

    hpf_path = work / "Contents" / "content.hpf"
    hpf_root = etree.parse(str(hpf_path)).getroot()
    for image_id, png in assets:
        _add_manifest_image(hpf_root, image_id, f"BinData/{image_id}.png")
    etree.ElementTree(hpf_root).write(
        str(hpf_path), encoding="utf-8", xml_declaration=True, standalone=True
    )

    notes = _patch_section(sec, assets, consulting)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        mimetype = work / "mimetype"
        if mimetype.exists():
            zout.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for p in sorted(work.rglob("*")):
            if p.is_file() and p.name != "mimetype":
                zout.write(p, p.relative_to(work).as_posix())
    shutil.rmtree(work)
    return notes


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    src = Path(
        r"C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\01. 경영지도사 이력서\프로필 양식_박다솜_v4.hwpx"
    )
    out = src.with_name("프로필 양식_박다솜_v5.hwpx")
    backup = Path(r"D:\auto_write\results\backup_profile_v4") / src.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(src, backup)

    notes = patch_profile_v5(src, out)
    mirror = Path(r"D:\auto_write\results") / out.name
    shutil.copy2(out, mirror)

    print(f"원본(보존): {src}")
    print(f"백업: {backup}")
    print(f"출력: {out}")
    print(f"미러: {mirror}")
    for n in notes:
        print(f"  + {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
