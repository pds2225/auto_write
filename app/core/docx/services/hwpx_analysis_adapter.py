"""Read-only HWPX adapter for DOCX-oriented analysis engines.

This module extracts paragraph-like text and image counts directly from the HWPX
ZIP/XML package. It never converts HWPX to DOCX and never mutates the source
file, so DOCX analyzers can reuse their decision logic without a round-trip.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from lxml import etree

_SECTION_RE = re.compile(r"^Contents/section(\d+)\.xml$")


@dataclass(frozen=True)
class HwpxAnalysis:
    paragraphs: tuple[str, ...]
    existing_images: int
    section_count: int

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


def _local_name(tag: object) -> str:
    text = str(tag or "")
    if "}" in text:
        return text.rsplit("}", 1)[-1]
    return text


def _paragraph_text(paragraph) -> str:
    """Return text owned by one hp:p, excluding nested hp:p descendants.

    HWPX tables can live inside an outer paragraph. Without this guard, table
    cell paragraphs are counted once through the outer paragraph and again as
    their own paragraphs.
    """
    parts: list[str] = []

    def walk(node) -> None:
        for child in node:
            name = _local_name(child.tag)
            if name == "p":
                continue
            if name == "t":
                parts.append("".join(child.itertext()))
                continue
            walk(child)

    walk(paragraph)
    return "".join(parts).strip()


def read_hwpx_analysis(path: str | Path) -> HwpxAnalysis:
    """Extract lightweight analysis data directly from an HWPX package."""
    src = Path(path)
    if src.suffix.lower() != ".hwpx":
        raise ValueError(f"HWPX 파일이 아님: {src}")
    if not src.exists():
        raise FileNotFoundError(src)

    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)

    try:
        with ZipFile(src) as archive:
            section_entries: list[tuple[int, str]] = []
            for name in archive.namelist():
                match = _SECTION_RE.match(name)
                if match:
                    section_entries.append((int(match.group(1)), name))
            section_entries.sort()

            if not section_entries:
                raise ValueError("HWPX section XML이 없습니다.")

            paragraphs: list[str] = []
            existing_images = 0
            for _index, name in section_entries:
                root = etree.fromstring(archive.read(name), parser=parser)
                for element in root.iter():
                    local = _local_name(element.tag)
                    if local == "pic":
                        existing_images += 1
                    elif local == "p":
                        text = _paragraph_text(element)
                        if text:
                            paragraphs.append(text)

            return HwpxAnalysis(
                paragraphs=tuple(paragraphs),
                existing_images=existing_images,
                section_count=len(section_entries),
            )
    except BadZipFile as exc:
        raise ValueError(f"유효한 HWPX ZIP이 아님: {src}") from exc
