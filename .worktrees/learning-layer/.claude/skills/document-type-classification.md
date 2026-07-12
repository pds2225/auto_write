---
name: document-type-classification
description: >-
  완성·작성중인 정부지원사업 DOCX의 문서 유형을 9종(사업계획서·R&D계획서·발표평가·컨설팅·정책자금·인증·수출·현장클리닉·기타) 규칙기반으로
  분류한다. 다음 상황에서 적극 사용하라 — "이 문서 무슨 유형이야", "문서 종류 분류", "유형 판별/판정", "사업계획서 맞아?",
  "보고서 종류 확인", "유형 구조 적합성 점검", 그리고 품질 오케스트레이터가 유형별 PSST·구조 게이팅을 정하기 전 단계. 분류 결과가
  애매하거나 틀렸을 때의 재분류·다시 분류·재실행·수정·보완 요청, 특정 문서만 부분 재판정 요청도 이 스킬로 처리한다.
---

# document-type-classification

## 목적
완성되었거나 작성 중인 DOCX의 본문·표·파일명 텍스트를 읽어 한국 정부지원사업 문서 유형 9종 중 하나로 분류한다.
이 유형 결과는 품질 게이트의 "유형 구조 적합(15점)" 항목 판정 기준이 되고, business_plan/pitch_deck일 때만 PSST 검사를 켜는 분기 조건이 된다.
규칙 기반(키워드 가중점수)으로 AI 키 없이 동작하며, 1·2위 점수가 모호할 때만 선택적으로 AI 보조 판정을 시도한다.

## 적용 대상
- 입력: `.docx` 파일 경로(`classify_docx`) 또는 이미 추출한 텍스트 문자열(`classify_text`).
- 분류 결과 유형코드(라벨):
  - `business_plan`(사업계획서) / `rnd_plan`(R&D 연구개발계획서) / `pitch_deck`(발표평가 자료)
  - `consulting_report`(컨설팅 보고서) / `policy_fund_report`(정책자금 검토보고서) / `certification_report`(인증 검토보고서)
  - `export_report`(수출컨설팅 보고서) / `field_clinic_report`(현장클리닉 보고서) / `generic_submission`(기타 제출문서, fallback)

## 탐지 규칙
실제 코드(`app/auto_write/services/document_type_classifier.py`) 동작과 정확히 일치한다.
- 텍스트 추출: `_extract_text(doc, limit=12000)` — 본문 문단을 먼저, 그다음 표 셀 텍스트를 누적, 총 12000자에서 절단.
- haystack = `"{filename}\n{text}"`. 키워드 부분일치, 대소문자 무시(`kw.lower() in haystack.lower()`).
- 유형별 키워드 가중치(`_SIGNATURES`) 합산으로 유형별 점수 계산. 대표 가중치 예:
  - business_plan: 사업계획서·PSST(각 5), 문제인식·실현가능성·성장전략·창업아이템(각 3)
  - rnd_plan: 연구개발계획서(5), 연구개발·기술개발목표·TRL(각 4)
  - pitch_deck: 발표평가(5), 피칭·데모데이(각 4)
  - consulting_report: 컨설팅보고서(5), 진단결과·개선과제·컨설팅(각 4)
  - policy_fund_report: 정책자금·상환재원(각 5), 자금용도·융자(각 4/3)
  - certification_report: 인증요건·인증검토(각 5), 인증·충족여부·미비서류(각 4)
  - export_report: 수출컨설팅(5), 수출·바이어·HS코드(각 4)
  - field_clinic_report: 현장클리닉(5), 현장진단·클리닉·현장지도·개선처방(각 4)
- 순위 산정: 점수 내림차순 정렬, 1위(top_score)·2위(second_score) 추출.
- confidence = `min(0.99, 0.4 + 0.4*(top_score/총점) + 0.2*gap_factor)`,
  여기서 gap_factor = `min(1.0, (top_score - second_score)/max(1, top_score))`.
- 반환은 `DocTypeResult(type_code, type_label, confidence, scores, matched_keywords, method)`. `as_dict()`로 직렬화 가능.

## 수정 규칙
- 이 스킬은 DOCX 본문을 수정하지 않는다(판정 전용). 파일 후처리·강조·정리는 다른 스킬 담당.
- 분류 결과(`type_code`)는 오케스트레이터가 소비:
  - `business_plan` 또는 `pitch_deck`일 때만 PSST 검사를 실행한다.
  - 그 외 유형은 PSST 미적용, 유형별 보고서 구조 적합성으로만 평가한다.
- 텍스트만 있고 파일이 없을 때는 `classify_text(text, filename=...)`를 직접 호출한다.

## 예외 규칙
- `top_score < _MIN_SCORE(=4)` 이면 무조건 `generic_submission`, confidence=0.3, matched_keywords=[] 로 반환(키워드 근거 부족).
- AI 보조는 다음을 모두 만족할 때만 시도: `openai_service`가 전달되고 `available`이 True이며 `(top - second) <= _AMBIGUITY_GAP(=3)`(모호).
  - 1·2위 격차가 3을 초과하면 충분히 명확 → AI 호출하지 않고 규칙 결과 유지.
  - AI 호출이 예외를 던지면 무시하고 규칙 결과 유지(절대 실패로 중단하지 않음).
  - AI가 유효한 코드를 반환하면 `method="ai"`, `confidence=max(기존, 0.85)`로 갱신.
- AI 키가 없거나 미설정이면 전 과정 규칙 기반으로만 동작(기본값).

## 테스트 방법 (실제 PowerShell 명령)
```powershell
cd D:\auto_write\app

# 1) 파이썬 컴파일 점검
python -m py_compile auto_write\services\document_type_classifier.py

# 2) 단일 DOCX 유형 분류 (규칙 기반, AI 미사용)
python -c "from auto_write.services.document_type_classifier import classify_docx; r=classify_docx(r'C:\경로\문서.docx'); print(r.as_dict())"

# 3) 텍스트 문자열로 즉시 판정
python -c "from auto_write.services.document_type_classifier import classify_text; print(classify_text('사업계획서 문제인식 실현가능성 PSST', filename='plan.docx').as_dict())"

# 4) 오케스트레이터 전체 파이프라인(분류 단계 포함) 실행
python document_quality_orchestrator.py "C:\경로\문서.docx" --json

# 5) 회귀 테스트
python -m pytest tests\test_document_quality_harness.py -q
```

## 실패 시 롤백 기준
- 이 스킬 자체는 파일을 변경하지 않으므로 분류 단계에 롤백 대상이 없다.
- 분류가 틀려 후처리 결과가 잘못된 경우, 오케스트레이터가 후처리 전 백업한 원본으로 복구한다:
  `python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx`
- 재분류 요청 시: 같은 입력으로 `classify_docx`/`classify_text`를 다시 호출하고, 결과가 여전히 모호(격차 ≤ 3)하면 `openai_service` 전달 여부를 확인한다.

## 품질 점수 반영
- 영향 항목: "유형 구조 적합(15점)". 분류된 `type_code`/`type_confidence`가 `score_document(...)`의 유형 구조 적합 배점 산정 입력이 된다.
- 간접 영향: `business_plan`/`pitch_deck`로 분류되면 PSST 검사가 켜져 "PSST·보고서 구조(10점)" 평가 경로가 활성화된다.

## 연결 코드·CLI (실제 함수/명령)
- 코드: `app/auto_write/services/document_type_classifier.py`
  - `classify_text(text: str, *, filename: str = "") -> DocTypeResult`
  - `classify_docx(path, *, openai_service=None) -> DocTypeResult`
  - `DocTypeResult(type_code, type_label, confidence, scores, matched_keywords, method)` / `.as_dict()`
  - 상수: `_MIN_SCORE=4`, `_AMBIGUITY_GAP=3`, `_TYPE_LABELS`, `_SIGNATURES`, `_extract_text(...)`
- 소비처: `app/auto_write/services/document_quality_orchestrator.py`(유형 분류 → PSST 분기 → 점수),
  `app/auto_write/services/doc_quality_score.py`(`score_document(..., doc_type, type_confidence, ...)`).
- 진입 CLI: `app/document_quality_orchestrator.py`, 래퍼 `scripts/run_document_quality_harness.py`.
