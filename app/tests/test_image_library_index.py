"""이미지 라이브러리 인덱싱 — 원본 불변."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from auto_write.image_automation.image_library_index import index_image_library
from auto_write.image_automation.paths import sha256_file


def _png(path: Path, color=(10, 20, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (640, 480), color).save(path)
    return path


def test_index_does_not_move_originals(tmp_path: Path):
    lib = tmp_path / "lib"
    src = _png(lib / "1.문제인식" / "market.png")
    before = sha256_file(src)
    out = tmp_path / "copies"
    result = index_image_library(lib, copy_into=out)
    assert result.count == 1
    assert src.is_file()
    assert sha256_file(src) == before
    assert (out / result.assets[0].path_rel).is_file()
    assert result.assets[0].parent_hint == "1.문제인식"
