from __future__ import annotations

from pathlib import Path

import pytest

import security_baseline


def test_protected_paths_are_blocked_but_examples_are_allowed() -> None:
    blocked = {
        ".env": "PROTECTED_ENV_FILE",
        "config/.env.production": "PROTECTED_ENV_FILE",
        "workspace/projects/p1/input.json": "PROTECTED_PROJECT_DATA",
        "results/output.docx": "PROTECTED_PROJECT_DATA",
        "backup/source.docx": "PROTECTED_PROJECT_DATA",
        ".browser-profile/Cookies": "PROTECTED_BROWSER_STATE",
        "tmp/storage_state.json": "PROTECTED_BROWSER_STATE",
    }
    for path, rule_id in blocked.items():
        assert security_baseline.find_protected_path_rule(path) == rule_id

    assert security_baseline.find_protected_path_rule(".env.example") is None
    assert security_baseline.find_protected_path_rule("app/.env.example") is None
    assert security_baseline.find_protected_path_rule("docs/workspace-policy.md") is None


def test_secret_scan_reports_rule_and_path_without_secret_value() -> None:
    secret_value = "sk" + "-" + ("A" * 32)
    findings = security_baseline.scan_text("config.py", f'OPENAI_API_KEY="{secret_value}"')

    assert [(item.rule_id, item.path) for item in findings] == [("SECRET_OPENAI_KEY", "config.py")]
    assert secret_value not in repr(findings)


def test_secret_patterns_cover_google_and_github_tokens() -> None:
    google_key = "AI" + "za" + ("B" * 35)
    github_token = "gh" + "p_" + ("C" * 36)
    findings = security_baseline.scan_text("tokens.txt", f"{google_key}\n{github_token}")

    assert {item.rule_id for item in findings} == {"SECRET_GOOGLE_KEY", "SECRET_GITHUB_TOKEN"}


def test_source_tree_has_no_unsafe_tempfile_mktemp() -> None:
    app_root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in (app_root / "auto_write").rglob("*.py"):
        if "tempfile" + ".mktemp" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(path.relative_to(app_root).as_posix())
    assert offenders == []


def test_upload_extraction_rejects_path_like_filename() -> None:
    from auto_write.main import _extract_text_from_upload

    with pytest.raises(ValueError, match="경로 구분자"):
        _extract_text_from_upload("../announcement.docx", b"not-a-docx")


def test_upload_extraction_removes_temporary_file(monkeypatch: pytest.MonkeyPatch) -> None:
    from auto_write import main

    captured_paths: list[Path] = []

    def fake_extract(path: Path) -> str:
        captured_paths.append(path)
        assert path.exists()
        return "공고문"

    monkeypatch.setattr(main.project_service, "extract_reference_text", fake_extract)
    assert main._extract_text_from_upload("announcement.docx", b"temporary") == "공고문"
    assert len(captured_paths) == 1
    assert not captured_paths[0].exists()
    assert not captured_paths[0].parent.exists()


def test_actual_repository_passes_tracked_file_security_scan() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert security_baseline.scan_tracked_files(repo_root) == []
