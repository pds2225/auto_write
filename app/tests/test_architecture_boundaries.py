# test_architecture_boundaries.py — Architecture boundary enforcement
"""아키텍처 경계 검증 테스트.

도메인 간 금지된 import를 자동으로 검출한다.
"""
from __future__ import annotations
import os
import re
import pytest

APP_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def _iter_py_files(root: str):
    for dirpath, _dirs, files in os.walk(root):
        _dirs[:] = [d for d in _dirs if d not in ("__pycache__", ".pytest_cache")]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def _domain_of(relpath: str) -> str | None:
    """파일 상대경로로 도메인 판정."""
    parts = relpath.replace("\\", "/").split("/")
    if "bizplan" in parts:
        return "business_plan"
    if "resume" in parts:
        return "consultant_application"
    if "domains" in parts and "business_plan" in parts:
        return "business_plan"
    if "domains" in parts and "consultant_application" in parts:
        return "consultant_application"
    if "auto_write" in parts and "domains" not in parts and "services" not in parts:
        return None  # auto_write root (models, config, etc.)
    if "core" in parts:
        return "core"
    return None


def _get_imports(filepath: str) -> list[str]:
    """파일에서 import 문을 추출한다."""
    imports = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(("from ", "import ")):
                    imports.append(line)
    except Exception:
        pass
    return imports


def _is_cross_domain(import_line: str, source_domain: str) -> tuple[bool, str]:
    """import가 cross-domain 위반인지 검사한다."""
    # business_plan -> consultant_application 금지
    if source_domain == "business_plan":
        if "resume" in import_line and "auto_write.services" not in import_line:
            return True, "business_plan -> resume"
        if "consultant_application" in import_line:
            return True, "business_plan -> consultant_application"

    # consultant_application -> business_plan 금지
    if source_domain == "consultant_application":
        if "bizplan" in import_line and "auto_write.services" not in import_line:
            return True, "consultant_application -> bizplan"
        if "business_plan" in import_line and "domains.business_plan" in import_line:
            return True, "consultant_application -> business_plan"

    return False, ""


class TestArchitectureBoundaries:
    """아키텍처 경계 검증."""

    def test_no_cross_domain_imports(self):
        """도메인 간 금지된 import가 없어야 한다."""
        violations = []
        for fpath in _iter_py_files(APP_DIR):
            rel = os.path.relpath(fpath, APP_DIR)
            domain = _domain_of(rel)
            if domain is None:
                continue
            for imp in _get_imports(fpath):
                is_violation, reason = _is_cross_domain(imp, domain)
                if is_violation:
                    violations.append(f"{rel}: {imp} [{reason}]")
        assert violations == [], f"Cross-domain import violations:\n" + "\n".join(violations)

    def test_domain_packages_exist(self):
        """도메인 패키지가 존재해야 한다."""
        assert os.path.isdir(os.path.join(APP_DIR, "bizplan"))
        assert os.path.isdir(os.path.join(APP_DIR, "resume"))
        assert os.path.isdir(os.path.join(APP_DIR, "bizplan", "services"))
        assert os.path.isdir(os.path.join(APP_DIR, "resume", "services"))

    def test_domain_pipeline_facades_exist(self):
        """도메인 파이프라인 facade가 존재해야 한다."""
        bp = os.path.join(APP_DIR, "auto_write", "domains", "business_plan", "pipeline.py")
        ca = os.path.join(APP_DIR, "auto_write", "domains", "consultant_application", "pipeline.py")
        dc = os.path.join(APP_DIR, "auto_write", "domains", "domain_classifier.py")
        assert os.path.isfile(bp), f"Missing: {bp}"
        assert os.path.isfile(ca), f"Missing: {ca}"
        assert os.path.isfile(dc), f"Missing: {dc}"
