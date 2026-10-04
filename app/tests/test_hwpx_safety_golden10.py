# -*- coding: utf-8 -*-
"""Golden regression for the existing ten validation forms."""

from __future__ import annotations

from core.docx.services.hwpx_safety_golden import evaluate_golden10, format_golden_report


def test_golden10_matches_verified_xml_facts() -> None:
    report = evaluate_golden10()
    text = format_golden_report(report)
    print(text)
    assert report["file_count"] == 10
    assert report["ok"], text
    assert report["unsafe_auto_count"] == 0
    assert all(item["status"] == "PASS" for item in report["files"])
