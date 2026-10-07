"""origin 기반 canonical repo 이름."""

from __future__ import annotations

import pytest

from auto_write.image_automation.repo_name import RepoNameError, parse_repo_name_from_origin_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/pds2225/auto_write.git", "auto_write"),
        ("https://github.com/pds2225/auto_write", "auto_write"),
        ("git@github.com:pds2225/auto_write.git", "auto_write"),
        ("ssh://git@github.com/pds2225/auto_write.git", "auto_write"),
    ],
)
def test_parse_repo_name(url: str, expected: str):
    assert parse_repo_name_from_origin_url(url) == expected


def test_parse_repo_name_empty_fails():
    with pytest.raises(RepoNameError):
        parse_repo_name_from_origin_url("")


def test_worktree_folder_name_ignored():
    # URL basename wins even if cwd folder is auto_write-wt-m1-notebooklm
    assert parse_repo_name_from_origin_url("https://github.com/pds2225/auto_write.git") == "auto_write"
