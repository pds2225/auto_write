"""기존 이미지 라이브러리 인덱싱 (원본 이동/삭제 금지)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from auto_write.image_automation.models import VisualAsset
from auto_write.image_automation.paths import sha256_file

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


@dataclass(frozen=True)
class LibraryIndexResult:
    assets: list[VisualAsset]
    root: Path
    count: int


def _image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return int(im.width), int(im.height)
    except Exception:
        return 0, 0


def index_image_library(
    library_root: Path,
    *,
    copy_into: Path | None = None,
) -> LibraryIndexResult:
    """라이브러리 이미지를 스캔한다. 원본은 이동하지 않는다.

    copy_into 가 있으면 run 폴더로 복사하고 path_rel 은 복사본 기준.
    없으면 path_rel 에 익명화된 asset-<sha8>.<ext> 만 기록하고
    실제 절대경로는 반환하지 않는다(sidecar 는 호출측 책임).
    """
    library_root = Path(library_root)
    if not library_root.is_dir():
        raise FileNotFoundError(f"이미지 라이브러리 없음: {library_root}")

    if copy_into is not None:
        copy_into = Path(copy_into)
        copy_into.mkdir(parents=True, exist_ok=True)

    assets: list[VisualAsset] = []
    for path in sorted(library_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        digest = sha256_file(path)
        rel_name = f"asset-{digest[:8]}{path.suffix.lower()}"
        parent_hint = path.parent.name
        if copy_into is not None:
            dest = copy_into / rel_name
            if not dest.exists():
                dest.write_bytes(path.read_bytes())
            stored_rel = rel_name
            width, height = _image_size(dest)
        else:
            stored_rel = rel_name
            width, height = _image_size(path)

        assets.append(
            VisualAsset(
                asset_id=f"lib-{digest[:12]}",
                source_kind="library",
                path_rel=stored_rel,
                sha256=digest,
                width=width,
                height=height,
                parent_hint=parent_hint,
                source_label=path.name[:80],
                text_hint=f"{parent_hint} {path.stem}",
            )
        )

    return LibraryIndexResult(assets=assets, root=library_root, count=len(assets))


def write_library_index(assets: list[VisualAsset], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [a.model_dump() for a in assets]
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
