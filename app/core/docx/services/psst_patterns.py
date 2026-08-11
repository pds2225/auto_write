# psst_patterns.py — Shared PSST regex patterns
"""PSST 4영역 섹션 헤더 정규식 패턴.

project_service.py와 psst_check.py가 공유하는 패턴의 단일 출처.
"""
from __future__ import annotations
import re

__all__ = [
    "PSST_PROBLEM_RE",
    "PSST_SOLUTION_RE",
    "PSST_SCALE_RE",
    "PSST_TEAM_RE",
]

PSST_PROBLEM_RE = re.compile(r"1\.\s*문제\s*인식.*Problem", re.IGNORECASE)
PSST_SOLUTION_RE = re.compile(r"2\.\s*실현\s*가능성.*Solution", re.IGNORECASE)
PSST_SCALE_RE = re.compile(r"3\.\s*성장전략.*Scale", re.IGNORECASE)
PSST_TEAM_RE = re.compile(r"4\.\s*팀\s*구성.*Team", re.IGNORECASE)
