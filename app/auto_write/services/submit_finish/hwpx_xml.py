# -*- coding: utf-8 -*-
"""F1·F2 공용 HWPX 입출력 헬퍼 — 읽기·섹션 파싱·안전 저장만 담당한다.

규칙(기존 엔진과 동일): 원본은 읽기만 하고, 출력이 원본과 같으면 거부한다.
mimetype 은 맨 앞·무압축, 나머지 항목은 원래 순서·압축 설정을 그대로 쓴다.
XML 선언의 standalone 값은 원본 것을 보존한다(hwpx_fill._detect_standalone 재사용).
"""
from __future__ import annotations

import os
import re
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

from core.docx.services.hwpx_fill import _detect_standalone, _local, _same_file

HPF_NAME = "Contents/content.hpf"
_SECTION_RE = re.compile(r"Contents/section\d+\.xml$")
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


def read_hwpx(path) -> tuple[list[zipfile.ZipInfo], dict[str, bytes]]:
    """zip 항목 정보와 원본 바이트를 그대로 읽는다(원본 미수정)."""
    with zipfile.ZipFile(Path(path)) as archive:
        infos = archive.infolist()
        data = {info.filename: archive.read(info.filename) for info in infos}
    return infos, data


def section_names(data: dict[str, bytes]) -> list[str]:
    """section0.xml, section1.xml ... 를 번호 순으로."""
    names = [name for name in data if _SECTION_RE.match(name)]
    return sorted(names, key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))


def parse_xml(blob: bytes):
    return etree.fromstring(blob, _PARSER)


def serialize_xml(root, original: bytes) -> bytes:
    """원본 선언의 standalone 을 지켜 직렬화한다."""
    standalone = _detect_standalone(original)
    if standalone is None:
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=standalone)


def find_manifest(hpf_root):
    return next((node for node in hpf_root.iter() if _local(node.tag) == "manifest"), None)


def assert_not_same(src, dst) -> None:
    src, dst = Path(src), Path(dst)
    if _same_file(src, dst) or src.resolve() == dst.resolve():
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")


def write_hwpx(infos, data: dict[str, bytes], dst, added: dict[str, bytes] | None = None) -> Path:
    """임시 파일에 쓴 뒤 교체(중간 실패 시 반쪽 파일이 남지 않게)."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".hwpx", dir=str(dst.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w") as archive:
            if "mimetype" in data:
                head = zipfile.ZipInfo("mimetype")
                head.compress_type = zipfile.ZIP_STORED
                archive.writestr(head, data["mimetype"])
            for info in infos:
                if info.filename != "mimetype":
                    archive.writestr(info, data[info.filename])
            for name, blob in (added or {}).items():
                archive.writestr(name, blob, compress_type=zipfile.ZIP_DEFLATED)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return dst


def paragraph_text(p) -> str:
    """문단의 직계 텍스트 흐름(중첩 표 제외) — hwpx_fill._inline_texts 기준과 동일."""
    from core.docx.services.hwpx_fill import _inline_texts

    return "".join(t.text or "" for t in _inline_texts(p))


def cell_text(tc) -> str:
    """셀 안 모든 hp:t 글자(중첩 표 포함 — 문맥 판단용)."""
    return "".join(el.text or "" for el in tc.iter() if _local(getattr(el, "tag", "")) == "t")


def cell_addr(tc) -> tuple[int, int]:
    """(row, col). cellAddr 가 없으면 (-1, -1)."""
    for child in tc:
        if _local(getattr(child, "tag", "")) == "cellAddr":
            try:
                return int(child.get("rowAddr", -1)), int(child.get("colAddr", -1))
            except ValueError:
                return -1, -1
    return -1, -1
