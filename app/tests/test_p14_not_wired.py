# -*- coding: utf-8 -*-
"""P1.4 stays unwired until an independent QA pass.

The product path remains ProjectService._generate_hwpx_direct → submit_hwpx →
fill_hwpx. Analyzer authorization must not be called from that path yet.
"""

from __future__ import annotations

import inspect

from auto_write.services.hwpx_submit import submit_hwpx
from auto_write.services.project_service import ProjectService


def test_submit_hwpx_still_fills_through_legacy_fill_only() -> None:
    source = inspect.getsource(submit_hwpx)
    assert "fill_hwpx(" in source
    assert "authorize_t02_writes" not in source
    assert "commit_t02_label_writes" not in source
    assert "commit_exact_text_writes" not in source


def test_project_publish_does_not_call_analyzer_authorization() -> None:
    source = inspect.getsource(ProjectService._generate_hwpx_direct)
    assert "submit_hwpx(" in source
    assert "authorize_t02_writes" not in source
    assert "commit_t02_label_writes" not in source
