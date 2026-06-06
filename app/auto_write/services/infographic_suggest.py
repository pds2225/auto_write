"""infographic_suggest.py

문서 내용을 분석해 **인포그래픽·도식·참고이미지 삽입 위치를 제안**하는 리포트를 만든다.
실제 이미지를 삽입하지는 않는다(삽입은 ``docx_ops.insert_image_*`` 가 담당하며,
데이터바우처 규정상 1장 제한 등은 ``qa_service`` 가 경고한다). 본 모듈은
"어디에 / 어떤 형태로 / 어떤 캡션·생성 프롬프트로" 넣으면 좋을지 **제안만** 한다.

결정론적(키워드 → 시각화 유형 매핑)이며 AI 를 호출하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document

# (앵커 키워드들, 추천 시각화 유형, 캡션 템플릿, 생성 프롬프트 템플릿)
_SUGGESTION_RULES: list[tuple[tuple[str, ...], str, str, str]] = [
    (("시장규모", "TAM", "SAM", "SOM", "시장 전망", "성장률"),
     "막대/도넛 차트",
     "[그림] 목표 시장규모 및 성장 전망(TAM·SAM·SOM)",
     "TAM/SAM/SOM 3단계 시장규모를 보여주는 깔끔한 도넛 또는 동심원 인포그래픽, 한글 라벨, 정부지원사업 보고서 톤"),
    (("추진일정", "추진 일정", "로드맵", "마일스톤", "일정계획", "단계별"),
     "타임라인/간트",
     "[그림] 사업 추진 일정 로드맵",
     "분기별 마일스톤을 표시하는 수평 타임라인/간트 차트, 한글, 단정한 비즈니스 스타일"),
    (("팀구성", "팀 구성", "조직도", "조직 구성", "인력구성"),
     "조직도",
     "[그림] 팀 구성·역할 조직도",
     "대표/핵심팀/외부협력으로 구성된 조직도, 역할 라벨 포함, 한글, 심플 플랫 디자인"),
    (("비즈니스모델", "BM", "수익모델", "수익 구조", "밸류체인", "가치사슬"),
     "플로우/밸류체인 도식",
     "[그림] 비즈니스 모델·수익 구조 도식",
     "가치사슬과 수익 흐름을 화살표로 연결한 비즈니스 모델 다이어그램, 한글, 인포그래픽"),
    (("프로세스", "절차", "처리 과정", "동작 원리", "구조도", "아키텍처", "시스템 구성"),
     "플로우차트/구성도",
     "[그림] 핵심 기술·시스템 구성도",
     "시스템/기술 아키텍처 블록 다이어그램, 모듈 간 연결, 한글 라벨, 기술 보고서 스타일"),
    (("경쟁사", "경쟁력", "비교", "차별성", "포지셔닝"),
     "비교표/포지셔닝맵",
     "[그림] 경쟁사 대비 차별성·포지셔닝 맵",
     "2축 포지셔닝 맵 또는 경쟁 비교 인포그래픽, 자사 강조, 한글, 깔끔한 비즈니스 톤"),
    (("매출", "재무", "손익", "매출계획", "재무계획", "추정"),
     "추세 선/막대 그래프",
     "[그림] 연도별 매출·재무 추정",
     "연도별 매출/영업이익 추정을 보여주는 막대+선 복합 그래프, 한글, 보고서 스타일"),
]


@dataclass
class ImageSuggestion:
    anchor_text: str            # 제안 위치(가까운 단락 텍스트)
    visual_type: str            # 추천 시각화 유형
    caption: str                # 캡션(문서 삽입용)
    prompt: str                 # 이미지 생성 프롬프트
    keyword: str                # 트리거된 키워드

    def as_dict(self) -> dict[str, Any]:
        return {
            "anchor_text": self.anchor_text[:80],
            "visual_type": self.visual_type,
            "caption": self.caption,
            "prompt": self.prompt,
            "keyword": self.keyword,
        }


@dataclass
class InfographicReport:
    suggestions: list[ImageSuggestion] = field(default_factory=list)
    existing_images: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "suggestion_count": len(self.suggestions),
            "existing_images": self.existing_images,
            "suggestions": [s.as_dict() for s in self.suggestions],
        }


def _count_existing_images(doc: Document) -> int:
    from docx.oxml.ns import qn
    return len(doc.element.body.findall(".//" + qn("w:drawing")))


def suggest_images(doc: Document, *, max_suggestions: int = 8) -> InfographicReport:
    """문서 단락을 훑어 도식 삽입 제안을 생성한다(중복 유형은 1회만)."""
    report = InfographicReport(existing_images=_count_existing_images(doc))
    used_types: set[str] = set()

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    # 표 헤더 텍스트도 앵커 후보에 포함
    for table in doc.tables:
        if table.rows:
            header = " ".join(c.text.strip() for c in table.rows[0].cells if c.text.strip())
            if header:
                paragraphs.append(header)

    for text in paragraphs:
        if len(report.suggestions) >= max_suggestions:
            break
        for keywords, vtype, caption, prompt in _SUGGESTION_RULES:
            if vtype in used_types:
                continue
            hit = next((kw for kw in keywords if kw in text), None)
            if hit:
                report.suggestions.append(ImageSuggestion(
                    anchor_text=text,
                    visual_type=vtype,
                    caption=caption,
                    prompt=prompt,
                    keyword=hit,
                ))
                used_types.add(vtype)
                break
    return report


def suggest_images_docx(path: str | Path, *, max_suggestions: int = 8) -> InfographicReport:
    return suggest_images(Document(str(Path(path))), max_suggestions=max_suggestions)
