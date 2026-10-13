"""F4 사업계획서 섹션별 지정 이미지 삽입(opt-in).

입력: section_images = [{"anchor": "섹션 라벨", "image": "경로", "caption": "..."}]
(project_meta['section_images'] 또는 참고자료 JSON 의 같은 키).

삽입 자체는 기존 hwpx_pic_insert.insert_cell_reference_images 를 그대로 쓴다.
그래서 승인된 본문 칸에만, 칸 폭·150mm 상한 안에서, 원본 비율로, BinData/manifest
를 함께 갱신해 들어간다. 이 모듈은 '어느 칸에 어떤 파일'만 정한다.
- 앵커는 이번에 실제 값이 쓰인 본문 칸 라벨과 정확 일치(번호 접두 무시)해야 한다.
- 파일 없음·형식 불가·앵커 미특정은 임의 삽입하지 않고 REVIEW 사유로 남긴다.
- 같은 칸에 같은 이미지(내용 해시 기준)는 한 번만 넣는다(멱등).
"""
from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from lxml import etree

from core.docx.services.hwpx_protected_regions import normalized_cell_label

from .body_fill import heading_key
from .status import Status

_NARRATIVE_KINDS = {"GUIDANCE_VALUE", "EMPTY_NARRATIVE"}
_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _note(anchor: str, code: str, review: bool = True) -> str:
    suffix = f" {Status.REVIEW.value}" if review else ""
    return f"[section-image] {anchor} {code}{suffix}"


def _resolve(image: str, base_dirs: Iterable[Path]) -> Path | None:
    raw = str(image or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path if path.is_file() else None
    for base in base_dirs:
        candidate = Path(base) / path
        if candidate.is_file():
            return candidate
    return None


def _image_spec(path: Path, caption: str) -> tuple[dict[str, Any] | None, str]:
    from PIL import Image

    blob = path.read_bytes()
    try:
        with Image.open(BytesIO(blob)) as im:
            fmt, size = (im.format or "").upper(), im.size
    except Exception:
        return None, "IMAGE_UNREADABLE"
    if fmt not in {"PNG", "JPEG"}:
        return None, "IMAGE_UNSUPPORTED"
    if min(size) <= 0:
        return None, "IMAGE_SIZE_INVALID"
    return {"blob": blob, "suffix": ".png" if fmt == "PNG" else ".jpg", "caption": caption}, ""


def existing_cell_image_hashes(hwpx: str | Path, grant) -> set[str]:
    """현재 HWPX 의 해당 칸에 이미 들어 있는 그림들의 내용 해시."""
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure

    try:
        index = index_hwpx_structure(hwpx)
        table = index.tables[grant.table_index]
        with zipfile.ZipFile(hwpx) as archive:
            root = etree.fromstring(archive.read(grant.section_member))
            hpf = etree.fromstring(archive.read("Contents/content.hpf"))
            hrefs = {
                node.get("id"): node.get("href")
                for node in hpf.iter()
                if etree.QName(node).localname == "item"
            }
            tbl = list(root.iter(f"{{{_HP}}}tbl"))[table.table_index_in_section]
            tr = list(tbl.iterchildren(f"{{{_HP}}}tr"))[grant.physical_tr_index]
            tc = list(tr.iterchildren(f"{{{_HP}}}tc"))[grant.physical_tc_index]
            hashes = set()
            for img in tc.iter():
                ref = img.get("binaryItemIDRef") if etree.QName(img).localname == "img" else None
                if ref and hrefs.get(ref) in archive.namelist():
                    hashes.add(hashlib.sha256(archive.read(hrefs[ref])).hexdigest())
            return hashes
    except Exception:
        return set()


def plan_section_images(
    entries: Iterable[dict],
    grants: Iterable,
    values: dict,
    *,
    current_hwpx: str | Path | None = None,
    base_dirs: Iterable[Path] = (),
    queued: dict | None = None,
) -> tuple[dict, list[str]]:
    """section_images 설정 → insert_cell_reference_images 용 {grant: [spec]} + 사유 노트.

    queued: 같은 칸에 이미 예약된 그림(예: 참고 DOCX 인라인 그림). 결과는 여기에 합쳐진다.
    """
    images: dict = {g: list(specs) for g, specs in (queued or {}).items()}
    notes: list[str] = []
    grants = list(grants)
    written = [
        g for g in grants
        if g.kind in _NARRATIVE_KINDS and str(values.get(g, "")).strip()
    ]
    seen: dict = {}
    base_dirs = [Path(b) for b in base_dirs]
    for entry in entries or ():
        if not isinstance(entry, dict):
            continue
        anchor = str(entry.get("anchor") or "").strip()
        key = heading_key(anchor)
        if not key:
            notes.append(_note(anchor, "ANCHOR_EMPTY"))
            continue
        matches = [g for g in written if normalized_cell_label(g.field_label) == key]
        if len(matches) != 1:
            if matches:
                code = "ANCHOR_AMBIGUOUS"
            elif any(normalized_cell_label(g.field_label) == key for g in grants):
                code = "ANCHOR_NOT_WRITTEN"
            else:
                code = "ANCHOR_NOT_FOUND"
            notes.append(_note(anchor, code))
            continue
        grant = matches[0]
        path = _resolve(entry.get("image", ""), base_dirs)
        if path is None:
            notes.append(_note(anchor, "IMAGE_FILE_MISSING"))
            continue
        spec, error = _image_spec(path, str(entry.get("caption") or "").strip())
        if spec is None:
            notes.append(_note(anchor, error))
            continue
        if grant not in seen:
            seen[grant] = {hashlib.sha256(s["blob"]).hexdigest() for s in images.get(grant, [])}
            if current_hwpx is not None:
                seen[grant] |= existing_cell_image_hashes(current_hwpx, grant)
        digest = hashlib.sha256(spec["blob"]).hexdigest()
        if digest in seen[grant]:
            notes.append(_note(anchor, "DUPLICATE_SKIPPED", review=False))
            continue
        seen[grant].add(digest)
        images.setdefault(grant, []).append(spec)
        notes.append(_note(anchor, "PLANNED", review=False))
    return images, notes
