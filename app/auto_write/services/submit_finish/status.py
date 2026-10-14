"""제출 마감 기능 공통 계약: 검증 상태 어휘와 AI 판단 권한 제한(TASK 12장).

엔진과 AI 는 최종 제출 여부를 판단하지 않는다. 모든 보고 문구는
허용 표현만 쓰고, 금지 표현이 섞이면 assert_no_forbidden 이 잡아낸다.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NA = "N/A"
    UNVERIFIED = "UNVERIFIED"


# 12장 금지 표현. "제출 가능"류는 부정형("제출 불가능")도 함께 막는다.
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "제출 가능",
    "제출가능",
    "제출 불가능",
    "제출불가능",
    "제출 불가",
    "제출불가",
    "제출 승인",
    "제출승인",
    "제출 적합",
    "제출적합",
    "제출 자격 충족",
    "제출자격 충족",
)

# 12장 허용 표현(보고서 문구 작성 시 이 중에서 고른다).
ALLOWED_PHRASES: tuple[str, ...] = (
    "자동 검사 PASS",
    "구조 검사 FAIL",
    "시각적 오류 의심",
    "사용자 확인 필요",
    "기술적 검증 미실행",
    "자동 검사에서 추가 이상 미발견",
)

_FORBIDDEN_RE = re.compile("|".join(re.escape(p) for p in FORBIDDEN_PHRASES))


def find_forbidden(text: str) -> list[str]:
    """text 안의 금지 표현을 모두 돌려준다(없으면 빈 리스트)."""
    return sorted(set(_FORBIDDEN_RE.findall(text or "")))


def assert_no_forbidden(text: str) -> None:
    hits = find_forbidden(text)
    if hits:
        raise ValueError(f"금지 표현 포함: {hits}")


@dataclass
class Finding:
    """검수 항목 1건. source 는 'structural' | 'visual-ai' | 'manual-agent' | 'engine'."""

    code: str
    status: Status
    message: str
    source: str = "structural"
    page: int | None = None
    evidence: str = ""  # 근거(경로·좌표·값 출처 등). 개인정보 원문은 넣지 않는다.
    image: str = ""  # 오류 의심 영역 크롭 이미지 경로
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        assert_no_forbidden(self.message)
        assert_no_forbidden(self.evidence)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


def sanitize_forbidden(text: str) -> str:
    """기존 검증기가 만든 문구에 섞인 금지 표현을 중립 표현으로 바꾼다.

    기존 엔진(hwpx_acceptance 등)의 verdict 문자열은 이 패키지 밖이라 수정하지 않고,
    보고서에 담기 직전에 여기서 걸러낸다.
    """
    return _FORBIDDEN_RE.sub("자동 검사 결과(사용자 확인 필요)", text or "")
