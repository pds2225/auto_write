"""NotebookLM semantic step → 한국어/영어 accessibility selector registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Locale = Literal["ko", "en"]


@dataclass(frozen=True)
class SelectorCandidate:
    role: str
    name: str
    locale: Locale


# semantic step → (ko candidates, en candidates)
SELECTOR_REGISTRY: dict[str, dict[Locale, list[tuple[str, str]]]] = {
    "create_notebook": {
        "ko": [("button", "새 노트 만들기"), ("button", "새 노트북")],
        "en": [("button", "Create new notebook"), ("button", "New notebook")],
    },
    "add_source": {
        "ko": [("button", "소스 추가"), ("button", "출처 추가")],
        "en": [("button", "Add source"), ("button", "Upload source")],
    },
    "upload_file": {
        "ko": [("button", "파일 업로드"), ("button", "컴퓨터에서 업로드")],
        "en": [("button", "Upload file"), ("button", "Upload from computer")],
    },
    "studio_slides": {
        # 짧은 라벨 "슬라이드"/"Slides"는 상위 메뉴와 동시 매칭될 수 있어 제외.
        "ko": [("button", "슬라이드 자료")],
        "en": [("button", "Slide deck")],
    },
    "presenter_slides": {
        "ko": [("radio", "발표자 슬라이드")],
        "en": [("radio", "Presenter slides")],
    },
    "length_short": {
        "ko": [("radio", "짧게")],
        "en": [("radio", "Short")],
    },
    "generate": {
        "ko": [("button", "생성"), ("button", "만들기")],
        "en": [("button", "Generate"), ("button", "Create")],
    },
    "download": {
        "ko": [("button", "다운로드"), ("button", "내보내기")],
        "en": [("button", "Download"), ("button", "Export")],
    },
}


class SelectorAmbiguityError(RuntimeError):
    """후보가 둘 이상 매칭되거나 locale 미등록이면 클릭 금지."""

    def __init__(self, step: str, code: str = "ui_contract_changed"):
        self.step = step
        self.code = code
        super().__init__(f"selector ambiguity for step={step} code={code}")


def candidates_for(step: str, locale: Locale) -> list[SelectorCandidate]:
    if step not in SELECTOR_REGISTRY:
        raise SelectorAmbiguityError(step, "ui_contract_changed")
    entry = SELECTOR_REGISTRY[step]
    if locale not in entry:
        raise SelectorAmbiguityError(step, "ui_contract_changed")
    return [SelectorCandidate(role=r, name=n, locale=locale) for r, n in entry[locale]]


def resolve_unique_selector(
    step: str,
    locale: Locale,
    match_fn,
) -> SelectorCandidate:
    """
    match_fn(candidate) -> bool.
    매칭 0건 또는 2건 이상이면 SelectorAmbiguityError (클릭 0건).
    """
    cands = candidates_for(step, locale)
    matched = [c for c in cands if match_fn(c)]
    if len(matched) != 1:
        raise SelectorAmbiguityError(step, "ui_contract_changed")
    return matched[0]
