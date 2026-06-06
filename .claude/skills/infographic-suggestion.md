---
name: infographic-suggestion
description: >-
  완성 DOCX에 도식·인포그래픽·참고이미지를 어디에/어떤 유형으로/어떤 캡션·생성프롬프트로 넣을지 제안한다.
  사업계획서·R&D계획서·정책자금·인증·수출·현장클리닉 보고서가 글만 빽빽하고 그림이 없을 때,
  "이미지 제안 해줘 / 도식 추천 / 인포그래픽 넣을 위치 / 그림 어디에 / 시각화 제안" 요청 시 적극 사용한다.
  점수 리포트의 '이미지 제안(5점)' 항목이 0점이거나, 후처리 후 "다시/재실행/수정/보완"으로
  도식 제안을 갱신해 달라는 후속 요청에도 사용한다. 실제 이미지는 삽입하지 않고 제안만 한다.
---

## 목적

완성 DOCX 문서를 훑어 **도식/인포그래픽/참고이미지 삽입 위치·유형·캡션·생성프롬프트를 제안**한다.
실제 이미지 삽입은 하지 않는다(삽입은 `docx_ops`, 규정 경고는 `qa_service` 담당). 이 스킬은
"어디에 / 어떤 형태로 / 어떤 캡션·프롬프트로" 넣으면 좋을지 **제안만** 생성한다.
글자만 가득하고 시각자료가 없는 정부지원사업 문서의 가독성·심사 인상을 높이는 것이 목표다.

쉽게 말하면: 문서를 읽고 "여기엔 막대그래프, 여기엔 조직도를 넣으세요"라고 위치와 그림 설명을
대신 적어주는 도구다. 그림을 직접 그려 넣지는 않는다.

## 적용 대상

- 대상 문서 유형: business_plan(사업계획서), rnd_plan(R&D계획서), pitch_deck(발표평가),
  consulting_report(컨설팅), policy_fund_report(정책자금), certification_report(인증),
  export_report(수출컨설팅), field_clinic_report(현장클리닉), generic_submission(기타).
- 모든 유형에 적용 가능하다(유형 제한 없음). 시장규모·일정·팀구성·BM·기술구조·경쟁·재무 등
  시각화하기 좋은 내용이 있는 문서일수록 제안 수가 많아진다.
- 입력: 완성 DOCX 파일 1개. 출력: 텍스트/JSON 형태의 제안 리포트(원본 변경 없음).

## 탐지 규칙

`suggest_images(doc, *, max_suggestions=8)` 의 실제 동작과 정확히 일치한다.

- 본문 단락 중 **공백 제거 후 비어있지 않은 단락 텍스트**를 앵커 후보로 수집한다.
- 추가로 각 표의 **첫 행(헤더) 셀 텍스트**를 공백으로 이어 붙여 앵커 후보에 포함한다.
- 각 앵커 텍스트에 대해 아래 7개 규칙(`_SUGGESTION_RULES`)의 키워드를 검사한다.
  키워드가 텍스트에 **부분 문자열로 포함(`kw in text`)** 되면 매칭으로 본다.
  1. 시장규모/TAM/SAM/SOM/시장 전망/성장률 → **막대/도넛 차트**
  2. 추진일정/추진 일정/로드맵/마일스톤/일정계획/단계별 → **타임라인/간트**
  3. 팀구성/팀 구성/조직도/조직 구성/인력구성 → **조직도**
  4. 비즈니스모델/BM/수익모델/수익 구조/밸류체인/가치사슬 → **플로우/밸류체인 도식**
  5. 프로세스/절차/처리 과정/동작 원리/구조도/아키텍처/시스템 구성 → **플로우차트/구성도**
  6. 경쟁사/경쟁력/비교/차별성/포지셔닝 → **비교표/포지셔닝맵**
  7. 매출/재무/손익/매출계획/재무계획/추정 → **추세 선/막대 그래프**
- 문서에 이미 삽입된 이미지 수는 `w:drawing` 요소를 세어 `existing_images` 로 보고한다.

## 수정 규칙

- 본 스킬은 **문서를 수정하지 않는다.** 제안 리포트만 만든다(읽기 전용).
- 매칭된 각 항목은 `ImageSuggestion(anchor_text, visual_type, caption, prompt, keyword)` 로 생성한다.
  - `anchor_text`: 제안 위치로 쓸 가까운 단락/헤더 텍스트.
  - `visual_type`: 추천 시각화 유형(위 7종 중 하나).
  - `caption`: 문서 삽입용 캡션(예: `[그림] 목표 시장규모 및 성장 전망(TAM·SAM·SOM)`).
  - `prompt`: 이미지 생성 프롬프트(한글 라벨, 보고서 톤 등 포함).
  - `keyword`: 실제로 매칭된 키워드.
- 제안 결과를 사용자에게 전달할 때는 **위치(앵커) → 유형 → 캡션 → 생성프롬프트** 순으로 정리한다.
- 실제 그림 삽입이 필요하면 `docx_ops` 의 이미지 삽입 헬퍼로 별도 작업해야 함을 안내한다.

## 예외 규칙

- **중복 유형은 1회만 제안한다.** 같은 `visual_type` 이 이미 제안되었으면 건너뛴다
  (`used_types` 집합으로 관리). 즉 7종 유형이 각각 최대 1개씩만 나온다.
- **최대 제안 수 제한**: `max_suggestions`(기본 8) 에 도달하면 더 이상 제안하지 않는다.
  유형이 7종이므로 기본값에서는 사실상 유형당 1개, 최대 7개가 상한이다.
- 매칭되는 키워드가 전혀 없는 문서는 **제안 0개**가 정상이다(오류 아님). 이때 이미지 제안 점수는 0점.
- 빈 단락/공백만 있는 단락은 앵커에서 제외한다.
- 표가 없거나 헤더가 비어 있으면 표 헤더 앵커는 추가되지 않는다.
- AI/외부 API 를 호출하지 않는다(완전 결정론적). 같은 문서는 항상 같은 제안을 준다.

## 테스트 방법 (실제 PowerShell 명령)

품질 하네스 전체 실행 시 이미지 제안이 점수에 자동 반영된다.

```
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx" --json
```

리포트(md+json)에서 `image_suggestions` / 이미지 제안 점수를 확인한다.

제안 로직만 단독 확인(파이썬 인라인):

```
cd D:\auto_write\app
python -c "from docx import Document; from auto_write.services.infographic_suggest import suggest_images_docx; r = suggest_images_docx(r'C:\경로\문서.docx'); print(r.as_dict())"
```

문서 구조(단락/표) 덤프로 앵커 후보 확인:

```
cd D:\auto_write\app
python _build_chochang.py inspect "C:\경로\문서.docx"
```

하네스 테스트 스위트 실행:

```
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q
```

## 실패 시 롤백 기준

- 이 스킬은 **읽기 전용**이라 문서 자체를 손상시키지 않으므로 롤백 대상이 아니다.
- 단, 하네스 전체(`document_quality_orchestrator.py`) 실행 중 다른 후처리로 출력 DOCX가
  잘못 생성된 경우에는 오케스트레이터 백업으로 복원한다:

```
cd D:\auto_write\app
python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx
```

- 백업 경로: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` (후처리 전 자동 백업).
- 원본 DOCX 덮어쓰기 금지(출력=입력 경로면 ValueError). 백업 없이 원본 수정 금지.

## 품질 점수 반영

- 영향 배점: **이미지 제안(5점)** 항목 1곳.
- 점수 산출: `doc_quality_score.score_document(...)` 가 `image_suggestions`(제안 목록)과
  `existing_images`(기존 삽입 이미지 수)를 입력받아 5점 배점에 반영한다.
- 제안이 1건 이상 생성되거나 기존 이미지가 존재하면 가점되고, 제안 0건·이미지 0개이면 0점에 수렴한다.
- 게이트 기준(참고): 총점 90↑ 우수 / 85↑ 통과 / 70↑ 보완필요 / 70미만 실패, `passed = 총점>=85`.
  이미지 제안은 5점 비중이라 단독으로 게이트를 좌우하진 않지만, 경계 점수에서 통과/보완을 가른다.

## 연결 코드·CLI (실제 함수/명령)

- 핵심 함수: `auto_write.services.infographic_suggest.suggest_images(doc, *, max_suggestions=8) -> InfographicReport`
- 파일 입력 헬퍼: `suggest_images_docx(path, *, max_suggestions=8) -> InfographicReport`
- 데이터 구조: `ImageSuggestion(anchor_text, visual_type, caption, prompt, keyword)`,
  `InfographicReport(suggestions, existing_images)` (각각 `as_dict()` 제공).
- 점수 연동: `auto_write.services.doc_quality_score.score_document(doc, doc_type, type_confidence, psst_ratio, image_suggestions, existing_images) -> QualityScore`
- 오케스트레이터: `auto_write.services.document_quality_orchestrator.DocumentQualityOrchestrator.run(...)`
  파이프라인 중 이미지 제안 단계에서 본 함수를 호출하고 점수에 반영한다.
- CLI 진입점: `app/document_quality_orchestrator.py` (`--json`, `--no-report`, `--rollback` 등),
  래퍼: `scripts/run_document_quality_harness.py`, 구조 덤프: `app/_build_chochang.py inspect <docx>`.
