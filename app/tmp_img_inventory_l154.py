# -*- coding: utf-8 -*-
"""L154 Phase A: inventory + classify source/target images (UTF-8 report)."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from lxml import etree

SRC = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\02. 밸류업파트너스"
    r"\2026 토슈즈공통\20260807 24_제품 양산 패키지 수혜기업 모집(~8_7)"
    r"\붙임 2. 제품 양산 패키지 신청서 종합 최종본.hwpx"
)
TGT = Path(
    r"C:\Users\ekth3\OneDrive\바탕 화면\지원사업_공고첨부_문서전용_20260625"
    r"\25_2026 예술분야 예비창업 프로그램 참여자 모집"
    r"\2026 예술분야 예비창업 신청서_함서영_v3.1.hwpx"
)
OUT_DIR = Path(r"D:\auto_write\tmp_hwp_images\l154_inventory")
REPORT = OUT_DIR / "inventory_report.txt"


def sniff(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if data[:4] == b"GIF8":
        return "gif"
    return "unknown"


def px_size(data: bytes, kind: str):
    try:
        if kind == "png":
            return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        if kind == "jpg":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker, seglen = data[i + 1], int.from_bytes(data[i + 2 : i + 4], "big")
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    return (
                        int.from_bytes(data[i + 7 : i + 9], "big"),
                        int.from_bytes(data[i + 5 : i + 7], "big"),
                    )
                i += 2 + seglen
        if kind == "bmp" and len(data) >= 26:
            return int.from_bytes(data[18:22], "little"), abs(
                int.from_bytes(data[22:26], "little")
            )
    except Exception:
        return None
    return None


def local(tag) -> str:
    if isinstance(tag, str) and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag or ""


def nearby_text(pic, max_chars: int = 240) -> str:
    node = pic
    p = None
    while node is not None:
        if local(node.tag) == "p":
            p = node
            break
        node = node.getparent()
    chunks = []
    if p is not None:
        parent = p.getparent()
        if parent is not None:
            kids = list(parent)
            try:
                idx = kids.index(p)
            except ValueError:
                idx = -1
            window = kids[max(0, idx - 3) : idx + 4] if idx >= 0 else [p]
            for k in window:
                for el in k.iter():
                    if local(el.tag) == "t" and el.text:
                        chunks.append(el.text.strip())
    return " ".join(c for c in chunks if c)[:max_chars]


def invent(path: Path, label: str, lines: list[str], extract: bool = False) -> dict:
    lines.append(f"\n======== {label} ========")
    lines.append(f"path: {path}")
    lines.append(f"exists: {path.exists()} size={path.stat().st_size if path.exists() else 0}")
    result = {"bins": [], "pics": [], "section_text_preview": ""}
    if not path.exists():
        return result

    extract_dir = OUT_DIR / label.lower()
    if extract:
        extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "r") as z:
        names = z.namelist()
        bins = sorted(n for n in names if n.replace("\\", "/").startswith("BinData/"))
        lines.append(f"zip_entries={len(names)} BinData={len(bins)}")
        hashes = {}
        for n in bins:
            info = z.getinfo(n)
            data = z.read(n)
            kind = sniff(data)
            px = px_size(data, kind)
            h = hashlib.md5(data).hexdigest()[:12]
            hashes.setdefault(h, []).append(Path(n).name)
            row = {
                "name": Path(n).name,
                "bytes": info.file_size,
                "ext": Path(n).suffix.lower(),
                "kind": kind,
                "px": px,
                "md5": h,
            }
            result["bins"].append(row)
            px_s = f"{px[0]}x{px[1]}" if px else "?"
            lines.append(
                f"  {row['name']:20s} bytes={info.file_size:9d} "
                f"ext={row['ext']:6s} magic={kind:7s} px={px_s:12s} md5={h}"
            )
            if extract and info.file_size > 0:
                (extract_dir / Path(n).name).write_bytes(data)

        dups = {k: v for k, v in hashes.items() if len(v) > 1}
        if dups:
            lines.append("DUPLICATE blobs:")
            for k, v in dups.items():
                lines.append(f"  {k}: {v}")

        secs = sorted(n for n in names if "section" in n.lower() and n.endswith(".xml"))
        lines.append(f"sections: {secs}")

        for s in secs:
            root = etree.fromstring(z.read(s))
            pics = [el for el in root.iter() if local(el.tag) == "pic"]
            lines.append(f"\n--- {s}: pic_count={len(pics)} ---")
            for i, pic in enumerate(pics):
                img_id = ""
                comment = ""
                for el in pic.iter():
                    ln = local(el.tag)
                    if ln == "img":
                        img_id = el.get("binaryItemIDRef") or ""
                    if ln == "shapeComment" and el.text:
                        comment = (el.text or "").replace("\n", " | ")[:120]
                near = nearby_text(pic)
                result["pics"].append(
                    {"idx": i, "idRef": img_id, "comment": comment, "near": near}
                )
                lines.append(f"  pic[{i}] idRef={img_id}")
                lines.append(f"         comment={comment}")
                lines.append(f"         near={near}")

            texts = []
            for t in root.iter():
                if local(t.tag) == "t" and t.text:
                    texts.append(t.text.strip())
            joined = " ".join(texts)
            result["section_text_preview"] = joined[:3000]
            lines.append("\n--- image-related paragraphs ---")
            for para in root.iter():
                if local(para.tag) != "p":
                    continue
                ptext = "".join(
                    (el.text or "") for el in para.iter() if local(el.tag) == "t"
                ).strip()
                if not ptext:
                    continue
                if any(
                    k in ptext
                    for k in (
                        "사진",
                        "이미지",
                        "그림",
                        "첨부",
                        "시제품",
                        "제품사진",
                        "참고자료",
                        "시각자료",
                        "인포그래픽",
                        "로드맵",
                        "도면",
                        "삽입",
                        "양산",
                        "패키지",
                        "토슈즈",
                        "제품",
                        "시장",
                        "비즈니스",
                        "사업계획",
                        "아이템",
                        "기술",
                        "차별",
                    )
                ):
                    # skip overly long body paras unless short caption-like
                    if len(ptext) < 180:
                        lines.append(f"  hint: {ptext}")

            # outline of major headings (short lines with numbers)
            lines.append("\n--- short heading-like paras ---")
            for para in root.iter():
                if local(para.tag) != "p":
                    continue
                ptext = "".join(
                    (el.text or "") for el in para.iter() if local(el.tag) == "t"
                ).strip()
                if 2 <= len(ptext) <= 60 and any(
                    ch.isdigit() for ch in ptext[:3]
                ) or (
                    ptext.startswith(("가.", "나.", "다.", "라.", "마.", "바.", "사.", "아."))
                    and len(ptext) <= 60
                ):
                    lines.append(f"  head: {ptext}")

    return result


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["L154 image inventory report"]
    invent(SRC, "SOURCE", lines, extract=True)
    invent(TGT, "TARGET", lines, extract=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT} ({len(lines)} lines)")
    print(f"Extracted to {OUT_DIR}")


if __name__ == "__main__":
    main()
