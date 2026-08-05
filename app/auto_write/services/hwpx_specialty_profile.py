"""hwpx_specialty_profile — 양식별 모집분야 checkBtn 좌표 맵 (L034).

모집분야는 **사용자 confirm 후에만** 체크한다. 추정 자동체크 금지.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SpecialtyOption:
    """모집분야 선택지 하나 — 표시 라벨·줄임말(aliases)과 checkBtn 표 좌표(col,row)."""

    label: str
    aliases: tuple[str, ...]
    col: int
    row: int


# 기업민원처리센터 전문상담위원 참여 신청서 (서식1 표)
# row3 = 라벨, row4 = checkBtn (실측)
MINWON_SPECIALTY_OPTIONS: tuple[SpecialtyOption, ...] = (
    SpecialtyOption(
        label="경영기반 전문상담",
        aliases=("경영기반", "기반"),
        col=1,
        row=4,
    ),
    SpecialtyOption(
        label="경영활동 전문상담",
        aliases=("경영활동", "활동"),
        col=2,
        row=4,
    ),
    SpecialtyOption(
        label="특화분야 전문상담",
        aliases=("특화분야", "특화"),
        col=3,
        row=4,
    ),
)

PROFILES: dict[str, tuple[SpecialtyOption, ...]] = {
    "minwon_counselor": MINWON_SPECIALTY_OPTIONS,
    "default": MINWON_SPECIALTY_OPTIONS,
}


class SpecialtyConfirmError(ValueError):
    """confirm 값이 프로필에 없거나 모호할 때."""


def resolve_specialty_checks(
    confirms: Iterable[str],
    *,
    profile: str = "minwon_counselor",
) -> list[tuple[int, int, str]]:
    """confirm 라벨 → [(col, row, label), ...]. 빈 confirm → [].

    매칭 규칙(추정 자동체크 금지 — 모듈 최상단 원칙):
    1. **정확 일치**(label 또는 alias 와 완전히 같음) → 그 옵션으로 확정.
    2. 정확 일치가 없으면 부분 일치(포함 관계)를 모으고, 후보가 **정확히 1개**일
       때만 확정한다.
    3. 후보가 0개(불명)거나 2개 이상(모호)이면 ``SpecialtyConfirmError``.
       예: ``"전문상담"`` 은 세 옵션 라벨 모두에 들어 있어 모호 → 에러.
       예전에는 이런 토큰이 조용히 첫 옵션(경영기반)으로 체크돼, 제출 서식에
       사용자가 고르지 않은 분야가 찍힐 수 있었다.
    """
    opts = PROFILES.get(profile) or PROFILES["default"]
    out: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for raw in confirms:
        token = (raw or "").strip()
        if not token:
            continue
        matched: SpecialtyOption | None = None
        loose: list[SpecialtyOption] = []
        for opt in opts:
            keys = (opt.label, *opt.aliases)
            if token == opt.label or token in opt.aliases:
                matched = opt  # 정확 일치 — 즉시 확정(짧은 alias 겹침보다 우선)
                break
            if any(token in k or k in token for k in keys):
                loose.append(opt)
        if matched is None:
            uniq = {opt.label: opt for opt in loose}
            if len(uniq) > 1:
                raise SpecialtyConfirmError(
                    f"모집분야 confirm 모호: {token!r} 가 여러 분야에 해당합니다"
                    f"({sorted(uniq)}). 정확한 분야명을 지정하세요."
                )
            if uniq:
                matched = next(iter(uniq.values()))
        if matched is None:
            raise SpecialtyConfirmError(
                f"모집분야 confirm 불명: {token!r}. "
                f"허용: {[o.label for o in opts]}"
            )
        if matched.label in seen:
            continue
        seen.add(matched.label)
        out.append((matched.col, matched.row, matched.label))
    return out
