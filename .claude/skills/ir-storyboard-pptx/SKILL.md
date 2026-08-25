---
name: ir-storyboard-pptx
description: >-
  일러스트 스토리보드(여러 칸 IR/피치덱 시안)를 실제 PPT로 만들 때의 라우팅 스킬.
  python-pptx/PIL 카드덱으로 다시 그리지 말고, 시각 네이티브 도구(Skywork)에
  원본 이미지 + 장별 카피 프롬프트를 넘긴다. "넌안되겠다 + 다른 도구에 동일작업"은
  도구 이관이지 불합격 판정이 아니다. 트리거: 스토리보드 PPT, 슬라이드 한장씩,
  피치덱 변환, Skywork, KICKXUP IR, K-네비 슬라이드, 발표자료 그림시안.
---

# ir-storyboard-pptx — 일러스트 스토리보드 → PPT 라우팅

## The Insight

일러스트가 있는 스토리보드를 PPT로 바꾸는 일은 **카피 재배치가 아니라 그림 복제**다.
Cursor에서 python-pptx/PIL로 파란 카드·아이콘 서클을 그리면 시안과 다른 덱이 나온다.
같은 작업을 시각 네이티브 도구(Skywork Slides)로 넘기고, 원본 이미지를 반드시 첨부한다.

"넌안되겠다, ○○한테 동일작업 시켜"는 **품질 낙제가 아니라 도구 이관**이다.
사용자가 실패/거절/불합격을 말하지 않았으면 RESUME·원장에 불합격을 쓰지 않는다.

## Why This Matters

- 잘못된 도구로 9장을 다시 그리면 시간도 쓰고, 시안 대비 완성도가 떨어진다.
- 세션 마무리 때 이관을 불합격으로 적으면 다음 세션이 사실을 왜곡한다.

## Recognition Pattern

다음이면 이 스킬이다.

- 입력이 **여러 칸 스토리보드 이미지**(한 장에 01~09 시안)
- 요청이 "슬라이드 한 장씩 만들어서 전체 PPT로"
- 또는 "Skywork에 동일작업 시킬 프롬프트"

다음이면 이 스킬이 **아니다**.

- 빈 양식 채움 → `cross-form-submission` / `hwpx_submit`
- 완성 DOCX 다듬기 → `document-quality-orchestrator`
- 처음부터 사업계획서 본문 작성 → `bizplan-orchestrator`

## The Approach

1. **도구를 고른다.** 시안에 폰 목업·지도 점선·랜드마크 그림이 있으면 Skywork.
   Cursor python-pptx는 텍스트 카드 IR에만 쓴다.
2. **정본은 첨부 이미지다.** 텍스트만 넣으면 제네릭 템플릿이 나온다.
3. **프롬프트는 장별 카피 + 비주얼 필수요소 + 숫자 고정.** 날조 금지.
   K-네비 KICKXUP 정본: `docs/KNEVI_KICKXUP_SKYWORK_PROMPT.md`
4. **산출 PPT는 git에 넣지 않는다.** (`results/`, `*.pptx`)
5. **세션 기록:** 이관이면 "Skywork로 동일작업 이관". 불합격이라고 쓰지 말 것.

## Skywork 최소 절차

1. 모드: Slides / PPT / Presentation (Docs 아님)
2. 첨부: 원본 스토리보드 이미지
3. 붙여넣기: 장별 카피가 있는 프롬프트
4. 한 번에 안 맞으면 후속 한 줄만:
   `첨부 스토리보드와 1:1로 레이아웃을 맞춰라. 카드 나열 템플릿 쓰지 말고, 핵심 그림(예: 폰 목업, 비교 문장)을 살려라.`

## Success criteria

- PPTX 16:9, 슬라이드 수가 시안 칸 수와 같음(칸 9개면 9장. 목차/감사 추가 금지)
- 시안의 핵심 그림·비교 문장·KPI 숫자가 그대로임
- 원장/RESUME에 사용자 말과 다른 판정(불합격 등)이 없음

## Pitfalls

- 이미지 없이 프롬프트만 보내기
- 9칸 썸네일을 한 슬라이드에 넣기
- KPI·고유명사 창작
- 이관 요청을 FAIL로 기록하기
