# -*- coding: utf-8 -*-
"""Compare two HWPX packages and fail when XML outside exact targets changes.

The checker reads both files and does not write. A change is allowed only at an
explicit text node, or as the single ``hp:t`` inserted into an empty run when
``text_node_index`` is None. Labels, guidance, other cells, table addresses,
style references, headers, and every other member stay byte-or-structure identical.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

from lxml import etree

_PARSER = etree.XMLParser(remove_blank_text=False, huge_tree=True, resolve_entities=False)


@dataclass(frozen=True)
class XmlScopeTarget:
    """One approved write coordinate. This is not a writer."""

    section_member: str
    paragraph_index: int
    run_index: int
    text_node_index: int | None


@dataclass(frozen=True)
class XmlScopeChange:
    member: str
    xml_path: str
    before: str
    after: str
    disposition: str
    related_target: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class XmlScopeDiffReport:
    ok: bool
    verdict: str
    source_sha256: str
    expected_sha256: str
    sha_ok: bool
    source_unchanged: bool
    changes: list[XmlScopeChange] = field(default_factory=list)
    unmatched_targets: list[str] = field(default_factory=list)

    @property
    def unexpected_count(self) -> int:
        return sum(1 for change in self.changes if change.disposition == "unexpected")

    @property
    def out_of_scope_xml_change(self) -> bool:
        return self.verdict == "OUT_OF_SCOPE_XML_CHANGE"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["unexpected_count"] = self.unexpected_count
        payload["out_of_scope_xml_change"] = self.out_of_scope_xml_change
        payload["changes"] = [change.as_dict() for change in self.changes]
        return payload


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _is_hancom_text(node) -> bool:
    return getattr(node, "tag", None) == f"{{{_HP_NS}}}t"


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def iter_section_paragraphs(root) -> Iterable[Any]:
    """Yield ``hp:p`` in the same order as the structure index.

    The outer paragraph is yielded before paragraphs inside its nested tables.
    """

    def walk(node) -> Iterable[Any]:
        for child in node:
            if _local(child.tag) == "p":
                yield child
                yield from walk(child)
            elif isinstance(child.tag, str):
                yield from walk(child)

    yield from walk(root)


def _run_elements(paragraph) -> list[Any]:
    return [child for child in paragraph if _local(child.tag) == "run"]


def _text_elements(run) -> list[Any]:
    return [child for child in run if _local(child.tag) == "t"]


def raw_text_node(node) -> str:
    parts = [node.text or ""]
    for child in node:
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def paragraph_raw_text(paragraph) -> str:
    chunks: list[str] = []
    for run in _run_elements(paragraph):
        chunks.extend(raw_text_node(node) for node in _text_elements(run))
    return "".join(chunks)


def run_raw_text(run) -> str:
    return "".join(raw_text_node(node) for node in _text_elements(run))


def _target_id(target: XmlScopeTarget) -> str:
    text_index = "none" if target.text_node_index is None else str(target.text_node_index)
    return (
        f"{target.section_member}#p[{target.paragraph_index}]"
        f"/run[{target.run_index}]/t[{text_index}]"
    )


def _clip(value: str, limit: int = 500) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"...<{len(value) - limit} more>"


def _parse(payload: bytes):
    return etree.fromstring(payload, parser=_PARSER)


def _is_xml_member(name: str) -> bool:
    lowered = name.replace("\\", "/").lower()
    return lowered.endswith(".xml") or lowered.endswith(".hpf")


def _index_paragraphs(root) -> list[Any]:
    return list(iter_section_paragraphs(root))


def _mask_targets(before_root, after_root, targets: list[XmlScopeTarget], member: str, changes: list[XmlScopeChange]) -> list:
    """Mask approved text only. Return the empty inserted hp:t elements."""
    allowed_inserts: list = []
    before_paragraphs = _index_paragraphs(before_root)
    after_paragraphs = _index_paragraphs(after_root)
    for target in targets:
        if target.section_member != member:
            continue
        identity = _target_id(target)
        if target.paragraph_index >= len(before_paragraphs) or target.paragraph_index >= len(after_paragraphs):
            continue
        before_runs = _run_elements(before_paragraphs[target.paragraph_index])
        after_runs = _run_elements(after_paragraphs[target.paragraph_index])
        if target.run_index >= len(before_runs) or target.run_index >= len(after_runs):
            continue
        before_run = before_runs[target.run_index]
        after_run = after_runs[target.run_index]
        if target.text_node_index is None:
            _mask_empty_run_insertion(
                before_run, after_run, member, identity, changes,
                target.paragraph_index, target.run_index, targets, allowed_inserts,
            )
            continue
        before_nodes = _text_elements(before_run)
        after_nodes = _text_elements(after_run)
        if target.text_node_index >= len(before_nodes) or target.text_node_index >= len(after_nodes):
            continue
        before_node = before_nodes[target.text_node_index]
        after_node = after_nodes[target.text_node_index]
        if list(before_node) or list(after_node):
            continue
        before_text = before_node.text or ""
        after_text = after_node.text or ""
        if before_text == after_text:
            continue
        changes.append(XmlScopeChange(
            member=member,
            xml_path=f"/p[{target.paragraph_index}]/run[{target.run_index}]/t[{target.text_node_index}]/text()",
            before=_clip(before_text),
            after=_clip(after_text),
            disposition="allowed",
            related_target=identity,
        ))
        after_node.text = before_node.text
    return allowed_inserts


def _mask_empty_run_insertion(
    before_run, after_run, member: str, identity: str, changes: list[XmlScopeChange],
    paragraph_index: int, run_index: int, targets: list[XmlScopeTarget], allowed_inserts: list,
) -> None:
    before_children = list(before_run)
    after_children = list(after_run)
    before_texts = [child for child in before_children if _local(child.tag) == "t"]
    if before_texts or len(after_children) != len(before_children) + 1:
        return
    before_names = tuple(_local(child.tag) or "#node" for child in before_children)
    for index, child in enumerate(after_children):
        if not _is_hancom_text(child):
            continue
        trial = after_children[:index] + after_children[index + 1:]
        trial_names = tuple(_local(item.tag) or "#node" for item in trial)
        if trial_names != before_names:
            continue
        changes.append(XmlScopeChange(
            member=member,
            xml_path=f"/p[{paragraph_index}]/run[{run_index}]/t[new]/text()",
            before="",
            after=_clip(child.text or ""),
            disposition="allowed",
            related_target=identity,
        ))
        child.text = None
        if child.attrib or list(child) or (child.tail or ""):
            if child.tail:
                _unexpected(
                    changes, member,
                    f"/p[{paragraph_index}]/run[{run_index}]/t[new]/tail",
                    "", child.tail, targets, paragraph_index,
                )
            if child.attrib:
                _unexpected(
                    changes, member,
                    f"/p[{paragraph_index}]/run[{run_index}]/t[new]/@attr",
                    "", " ".join(sorted(child.attrib)), targets, paragraph_index,
                )
            return
        allowed_inserts.append(child)
        return


def _related(paragraph_index: int | None, targets: list[XmlScopeTarget], member: str) -> str | None:
    if paragraph_index is None:
        return None
    for target in targets:
        if target.section_member == member and target.paragraph_index == paragraph_index:
            return _target_id(target)
    return None


def _unexpected(
    changes: list[XmlScopeChange], member: str, path: str, before: str, after: str,
    targets: list[XmlScopeTarget], paragraph_index: int | None,
) -> None:
    changes.append(XmlScopeChange(
        member=member,
        xml_path=path,
        before=_clip(before),
        after=_clip(after),
        disposition="unexpected",
        related_target=_related(paragraph_index, targets, member),
    ))


def _approved_insert(node, allowed_inserts: list) -> bool:
    return (
        any(node == item for item in allowed_inserts)
        and _is_hancom_text(node)
        and not (node.text or "")
        and not (node.tail or "")
        and not node.attrib
        and not list(node)
    )


def _diff_nodes(
    before, after, path: str, member: str, targets: list[XmlScopeTarget],
    changes: list[XmlScopeChange], paragraph_ids: dict[int, int], paragraph_index: int | None,
    allowed_inserts: list | None = None,
) -> None:
    allowed = allowed_inserts or []
    if id(before) in paragraph_ids:
        paragraph_index = paragraph_ids[id(before)]
    before_name = _local(before.tag) or "#node"
    after_name = _local(after.tag) or "#node"
    if before.tag != after.tag:
        _unexpected(changes, member, path, before_name, after_name, targets, paragraph_index)
        return
    keys = set(before.attrib) | set(after.attrib)
    for key in sorted(keys, key=str):
        left = before.attrib.get(key)
        right = after.attrib.get(key)
        if left == right:
            continue
        local = str(key).rsplit("}", 1)[-1]
        _unexpected(changes, member, f"{path}/@{local}", left or "", right or "", targets, paragraph_index)
    if (before.text or "") != (after.text or ""):
        _unexpected(changes, member, f"{path}/text()", before.text or "", after.text or "", targets, paragraph_index)
    before_children = list(before)
    after_children = list(after)

    def child_path(node, index: int) -> str:
        return f"{path}/{_local(node.tag) or '#node'}[{index}]"

    def recurse(left, right, index: int) -> None:
        nested = child_path(left, index)
        if (left.tail or "") != (right.tail or ""):
            _unexpected(changes, member, f"{nested}/tail", left.tail or "", right.tail or "", targets, paragraph_index)
        _diff_nodes(left, right, nested, member, targets, changes, paragraph_ids, paragraph_index, allowed)

    if len(before_children) == len(after_children) and all(left.tag == right.tag for left, right in zip(before_children, after_children)):
        for index, (left, right) in enumerate(zip(before_children, after_children)):
            recurse(left, right, index)
        return
    from difflib import SequenceMatcher

    matcher = SequenceMatcher(
        a=[child.tag for child in before_children],
        b=[child.tag for child in after_children],
        autojunk=False,
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset, (left, right) in enumerate(zip(before_children[i1:i2], after_children[j1:j2])):
                recurse(left, right, i1 + offset)
            continue
        if tag in {"delete", "replace"}:
            for offset, left in enumerate(before_children[i1:i2]):
                shown = raw_text_node(left) if _local(left.tag) == "t" else (_local(left.tag) or "#node")
                _unexpected(changes, member, child_path(left, i1 + offset), shown, "", targets, paragraph_index)
        if tag in {"insert", "replace"}:
            for offset, right in enumerate(after_children[j1:j2]):
                if _approved_insert(right, allowed):
                    continue
                shown = raw_text_node(right) if _local(right.tag) == "t" else (_local(right.tag) or "#node")
                _unexpected(changes, member, child_path(right, j1 + offset), "", shown, targets, paragraph_index)


def _member_bytes(path: Path) -> dict[str, bytes]:
    with ZipFile(path) as archive:
        return {info.filename: archive.read(info.filename) for info in archive.infolist()}


def _unmatched(before_members: dict[str, bytes], targets: list[XmlScopeTarget]) -> list[str]:
    missing: list[str] = []
    parsed: dict[str, Any] = {}
    for target in targets:
        payload = before_members.get(target.section_member)
        if payload is None or not _is_xml_member(target.section_member):
            missing.append(_target_id(target))
            continue
        if target.section_member not in parsed:
            try:
                parsed[target.section_member] = _parse(payload)
            except etree.XMLSyntaxError:
                missing.append(_target_id(target))
                continue
        paragraphs = _index_paragraphs(parsed[target.section_member])
        if target.paragraph_index >= len(paragraphs):
            missing.append(_target_id(target))
            continue
        runs = _run_elements(paragraphs[target.paragraph_index])
        if target.run_index >= len(runs):
            missing.append(_target_id(target))
            continue
        if target.text_node_index is None:
            continue
        if target.text_node_index >= len(_text_elements(runs[target.run_index])):
            missing.append(_target_id(target))
    return missing


def compare_hwpx_xml_scope(
    before: str | Path,
    after: str | Path,
    targets: Iterable[XmlScopeTarget],
    *,
    expected_sha256: str,
) -> XmlScopeDiffReport:
    """Return PASS only when the original SHA matches and every XML change is in ``targets``."""
    src = Path(before)
    dst = Path(after)
    before_bytes = src.read_bytes()
    source_sha = hashlib.sha256(before_bytes).hexdigest()
    expected = str(expected_sha256 or "").lower()
    report = XmlScopeDiffReport(
        ok=False,
        verdict="SHA_MISMATCH",
        source_sha256=source_sha,
        expected_sha256=expected,
        sha_ok=source_sha == expected,
        source_unchanged=True,
    )
    if not report.sha_ok:
        report.source_unchanged = src.read_bytes() == before_bytes
        return report
    target_list = list(targets)
    before_members = _member_bytes(src)
    after_members = _member_bytes(dst)
    report.unmatched_targets = _unmatched(before_members, target_list)
    names = sorted(set(before_members) | set(after_members))
    for name in names:
        left = before_members.get(name)
        right = after_members.get(name)
        if left is None or right is None:
            report.changes.append(XmlScopeChange(
                member=name,
                xml_path="<member>",
                before="ABSENT" if left is None else "PRESENT",
                after="ABSENT" if right is None else "PRESENT",
                disposition="unexpected",
                related_target=None,
            ))
            continue
        if left == right:
            continue
        if not _is_xml_member(name):
            if left != right:
                report.changes.append(XmlScopeChange(
                    member=name,
                    xml_path="<bytes>",
                    before=hashlib.sha256(left).hexdigest(),
                    after=hashlib.sha256(right).hexdigest(),
                    disposition="unexpected",
                    related_target=None,
                ))
            continue
        try:
            before_root = _parse(left)
            after_root = _parse(right)
        except etree.XMLSyntaxError as exc:
            report.changes.append(XmlScopeChange(
                member=name,
                xml_path="<parse>",
                before="" if left == right else "XML",
                after=str(exc),
                disposition="unexpected",
                related_target=None,
            ))
            continue
        allowed_inserts = _mask_targets(before_root, after_root, target_list, name, report.changes)
        paragraph_ids = {id(paragraph): index for index, paragraph in enumerate(_index_paragraphs(before_root))}
        _diff_nodes(
            before_root, after_root, f"/{_local(before_root.tag) or 'root'}[0]",
            name, target_list, report.changes, paragraph_ids, None, allowed_inserts,
        )
    report.source_unchanged = src.read_bytes() == before_bytes
    if not report.source_unchanged:
        report.ok = False
        report.verdict = "SOURCE_MUTATED"
        return report
    if report.unexpected_count:
        report.ok = False
        report.verdict = "OUT_OF_SCOPE_XML_CHANGE"
        return report
    report.ok = True
    report.verdict = "PASS"
    return report
