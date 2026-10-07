"""검증 출처목록: sources.json / sources.md / sources.csv."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, urlunparse

from auto_write.image_automation.models import CitationStatus, SourceCitation
from auto_write.models import EvidenceSource

# 한글 접미(년)와 붙어 있어도 연도 추출. checked_at 재사용 금지와 별개.
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or ""
    # drop fragment; keep query
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def extract_year(*texts: str) -> str:
    for text in texts:
        if not text:
            continue
        m = _YEAR_RE.search(text)
        if m:
            return m.group(0)
    return ""


def evidence_to_citation(
    src: EvidenceSource,
    *,
    used_on: str = "",
    allowed_urls: set[str] | None = None,
) -> SourceCitation:
    title = (src.title or "").strip()
    org = (src.organization or "").strip()
    url = (src.url or "").strip()
    year = extract_year(src.summary or "", src.title or "", getattr(src, "topic", "") or "")
    # checked_at 은 자료 연도로 쓰지 않는다.
    status = _status(title=title, organization=org, year=year, url=url, allowed_urls=allowed_urls)
    return SourceCitation(
        title=title,
        organization=org,
        year=year,
        url=url,
        used_on=used_on,
        status=status,
    )


def citation_from_parts(
    *,
    title: str,
    organization: str,
    year: str,
    url: str,
    used_on: str = "",
    allowed_urls: set[str] | None = None,
    invented: bool = False,
) -> SourceCitation:
    if invented:
        return SourceCitation(
            title=title,
            organization=organization,
            year=year,
            url=url,
            used_on=used_on,
            status=CitationStatus.MISMATCH,
        )
    status = _status(
        title=title,
        organization=organization,
        year=year,
        url=url,
        allowed_urls=allowed_urls,
    )
    return SourceCitation(
        title=title.strip(),
        organization=organization.strip(),
        year=year.strip(),
        url=url.strip(),
        used_on=used_on,
        status=status,
    )


def _status(
    *,
    title: str,
    organization: str,
    year: str,
    url: str,
    allowed_urls: set[str] | None,
) -> CitationStatus:
    if not title.strip():
        return CitationStatus.MISSING_TITLE
    if not organization.strip():
        return CitationStatus.MISSING_ORGANIZATION
    if not year.strip():
        return CitationStatus.MISSING_YEAR
    if not url.strip():
        return CitationStatus.MISSING_URL
    if allowed_urls is not None:
        norm = normalize_url(url)
        allowed_norm = {normalize_url(u) for u in allowed_urls if u}
        if norm not in allowed_norm:
            return CitationStatus.MISMATCH
    return CitationStatus.VERIFIED


def extract_pdf_hyperlinks(pdf_path: Path) -> list[str]:
    import fitz

    urls: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            for link in page.get_links():
                uri = link.get("uri") or ""
                if uri.startswith(("http://", "https://")):
                    urls.append(uri)
    finally:
        doc.close()
    return urls


def build_citations(
    evidence: Iterable[EvidenceSource],
    *,
    pdf_urls: Iterable[str] | None = None,
    notebooklm_urls: Iterable[str] | None = None,
) -> list[SourceCitation]:
    """EvidenceSource + PDF hyperlink 근거만 사용. NotebookLM 신규 URL은 mismatch."""
    pdf_set = {normalize_url(u) for u in (pdf_urls or []) if u}
    evidence_urls = {normalize_url(e.url) for e in evidence if e.url}
    allowed = pdf_set | evidence_urls

    citations = [
        evidence_to_citation(e, allowed_urls=allowed) for e in evidence
    ]

    nlm = {normalize_url(u) for u in (notebooklm_urls or []) if u}
    for url in sorted(nlm - allowed):
        citations.append(
            citation_from_parts(
                title="",
                organization="",
                year="",
                url=url,
                invented=True,
            )
        )
    return citations


def is_submission_ready(citations: list[SourceCitation]) -> bool:
    """모든 인용 후보가 verified 이고 1건 이상일 때만 제출 가능."""
    if not citations:
        return False
    return all(c.status == CitationStatus.VERIFIED for c in citations)


def requires_draft(citations: list[SourceCitation]) -> bool:
    return not is_submission_ready(citations)


def write_citation_reports(
    citations: list[SourceCitation],
    out_dir: Path,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "sources.json"
    md_path = out_dir / "sources.md"
    csv_path = out_dir / "sources.csv"

    rows = [c.model_dump() for c in citations]
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    headers = ["자료명", "기관명", "연도", "URL", "사용 슬라이드/페이지", "검증상태"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for c in citations:
            w.writerow([c.title, c.organization, c.year, c.url, c.used_on, c.status.value])

    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for c in citations:
        lines.append(
            "| "
            + " | ".join(
                [
                    c.title,
                    c.organization,
                    c.year,
                    c.url,
                    c.used_on,
                    c.status.value,
                ]
            )
            + " |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "md": md_path, "csv": csv_path}
