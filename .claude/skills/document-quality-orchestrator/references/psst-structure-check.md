---
name: psst-structure-check
description: >
  사업계획서 PSST 4영역(Problem 문제인식 / Solution 실현가능성 / Scale-up 성장전략 / Team 팀구성)의
  충실도를 결정론적으로 검사하고 누락·미흡 하위항목을 도출한다. 다음 상황에서 적극적으로 사용하라.
  "PSST 검사", "PSST 구조 확인", "문제인식/실현가능성/성장전략/팀구성 점검", "사업계획서 4영역 채워졌는지 봐줘",
  "PSST 누락 항목 알려줘", "PSST 등급 매겨줘" 요청 시. 또한 사업계획서(business_plan)·발표평가(pitch_deck)
  문서 품질 검수 중 PSST 배점이 깎였을 때, 그리고 "다시 검사", "재실행", "수정 후 다시", "보완했는지 확인",
  "PSST 다시 봐줘" 같은 후속작업 요청 시에도 이 스킬을 사용하라. 품질점수 PSST·보고서구조(10점) 항목에 직접 영향.
---

## 목적

사업계획서 유형 문서가 PSST 평가틀(Problem / Solution / Scale-up / Team) 4영역을 얼마나 충실히
채웠는지 결정론적으로 검사한다. 각 영역의 핵심 하위항목 충족 여부를 키워드로 탐지해
[누락 / 미흡 / 적정 / 우수] 4단계 등급을 매기고, 누락 하위항목 목록과 전체 충족 비율(overall_ratio)을
산출한다. AI 를 호출하지 않는다(키 없이 동작).

쉽게 말하면: 사업계획서가 "문제-해결-성장-팀" 네 덩어리를 빠짐없이 썼는지 자동으로 점검하고,
빠진 부분을 콕 집어 알려주는 단계다.

## 적용 대상

- 유형 분류 결과가 `business_plan`(사업계획서) 또는 `pitch_deck`(발표평가)인 DOCX.
  (오케스트레이터는 이 두 유형에서만 PSST 검사를 호출한다. 그 외 유형은 PSST 미적용으로 처리.)
- 직접 호출 시에는 유형과 무관하게 `check_psst(doc)` 가 항상 `applicable=True` 로 4영역을 검사한다.
- 검사 대상 텍스트: 본문 문단 전체 + 표 셀 텍스트(최대 30000자, `_extract_text` 기준).

## 탐지 규칙

코드(`app/auto_write/services/psst_check.py`)의 실제 동작과 정확히 일치한다.

1. **섹션 헤더 존재 여부** — `project_service.ProjectService` 의 PSST 정규식을 재사용한다(중복 구현 금지).
   - `PSST_PROBLEM_RE`  = `1.\s*문제\s*인식.*Problem`
   - `PSST_SOLUTION_RE` = `2.\s*실현\s*가능성.*Solution`
   - `PSST_SCALE_RE`    = `3.\s*성장전략.*Scale`
   - `PSST_TEAM_RE`     = `4.\s*팀\s*구성.*Team`
   - 매치되면 해당 영역 `section_present=True`. (등급 산정에는 직접 쓰이지 않고 섹션 존재 표시용.)

2. **하위항목 충족 탐지** — 영역별 4개 하위항목, 각 항목의 키워드 중 하나라도 본문에
   (대소문자 무시) 등장하면 충족(found+1), 없으면 `missing_items` 에 추가한다.
   - problem: 고객/시장 문제 · 기존 대안 한계 · 문제 심각성 · 수치 근거
   - solution: 해결방안/핵심기능 · 차별성 · 구현 가능성 · 고객 적용 시나리오
   - scale: 시장규모 · 수익모델 · 판로/성장전략 · KPI/매출계획
   - team: 대표자 역량 · 팀 구성 · 외부 협력 · 수행 경험/실행력

3. **영역 등급(`_grade`)** — 충족 수(found)/4 비율 기준.
   - found == 0 → **누락**
   - 비율 ≥ 0.9 (즉 4/4) → **우수**
   - 비율 ≥ 0.6 (즉 3/4) → **적정**
   - 그 외(1~2/4) → **미흡**

4. **전체 비율(`overall_ratio`)** = 전체 충족 항목 수 / 16. summary 에 충족 개수·퍼센트와
   "보완 필요" 영역(등급이 누락·미흡인 영역) 라벨을 함께 기록한다.

## 수정 규칙

- 이 스킬은 **검사·진단만 수행**하며 DOCX 를 수정하지 않는다(읽기 전용).
- 보완은 다음 순서로 권고한다.
  1. `missing_items` 에 나열된 하위항목 키워드(예: 수치 근거, 차별성, 수익모델, 외부 협력)를
     해당 영역 본문에 보강한다.
  2. `section_present=False` 인 영역은 양식 섹션 헤더 자체가 누락된 것이므로,
     `1. 문제 인식 (Problem)` / `2. 실현 가능성 (Solution)` / `3. 성장전략 (Scale-up)` /
     `4. 팀 구성 (Team)` 형식의 헤더를 추가하도록 안내한다.
  3. 보강 후 동일 명령으로 재검사하여 등급이 적정 이상으로 올라갔는지 확인한다.
- 텍스트 보강은 작성자/콘텐츠 단계의 책임이며, 본 스킬은 어떤 항목을 채워야 하는지만 제시한다.

## 예외 규칙

- 유형이 `business_plan`·`pitch_deck` 이 아니면 오케스트레이터는 PSST 검사를 건너뛴다(미적용).
  이 경우 PSST 배점은 보고서 구조 평가로 대체되며 PSST 누락으로 감점하지 않는다.
- 키워드 매칭은 단순 부분일치(`kw.lower() in text.lower()`)이므로, 표·캡션에 우연히 키워드가
  들어가면 충족으로 잡힐 수 있다. 등급이 과대평가로 의심되면 본문 실제 내용을 육안 확인한다.
- 섹션 헤더 정규식은 양식 표준 표기(번호 + 한글명 + 영문 영역명)를 전제한다. 표기가 다르면
  `section_present` 가 False 로 나올 수 있으나, 하위항목 키워드는 별개로 탐지되어 등급은 정상 산정된다.

## 테스트 방법 (실제 PowerShell 명령)

```powershell
cd D:\auto_write\app

# 전체 품질 하네스 실행 시 PSST 검사 자동 포함(business_plan/pitch_deck 유형일 때)
python document_quality_orchestrator.py "C:\경로\사업계획서.docx"

# PSST 단독 검사(파이썬 인라인)
python -c "from auto_write.services.psst_check import check_psst_docx; r=check_psst_docx(r'C:\경로\사업계획서.docx'); print(r.summary); [print(a.label, a.grade, '누락:', a.missing_items) for a in r.areas]"

# 단위 테스트
python -m pytest tests/test_document_quality_harness.py -q
```

## 실패 시 롤백 기준

- 본 스킬은 읽기 전용이라 자체적으로 롤백할 대상이 없다.
- 이후 보완 단계에서 DOCX 를 수정했고 결과가 더 나빠졌다면, 후처리 전 백업본으로 복구한다.
  - 복구: `python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx`
- 원본 DOCX 는 절대 덮어쓰지 않는다(출력=입력 경로면 ValueError). 수정 전 백업이 없으면 진행하지 않는다.

## 품질 점수 반영

- 품질점수 100점 중 **PSST·보고서구조(10점)** 항목에 직접 영향.
- `score_document(...)` 는 `psst_ratio`(= `PSSTReport.overall_ratio`)를 입력받아 이 항목 점수를 산정한다.
  영역별 등급이 적정·우수로 올라가 overall_ratio 가 높아질수록 배점을 채운다.
- 이 항목 점수가 낮으면 게이트(90 우수 / 85 통과 / 70 보완 / 미만 실패) 통과에 불리하므로,
  `missing_items` 보강 → 재검사 루프로 비율을 끌어올린다.

## 연결 코드·CLI (실제 함수/명령)

- 핵심 함수: `app/auto_write/services/psst_check.py`
  - `check_psst(doc) -> PSSTReport`
  - `check_psst_docx(path) -> PSSTReport`
  - 결과 구조: `PSSTReport(applicable, areas[PSSTAreaResult], overall_ratio, summary)`,
    `PSSTAreaResult(area, label, section_present, items_total, items_found, missing_items, grade)`
- 재사용 정규식: `project_service.ProjectService.PSST_PROBLEM_RE / PSST_SOLUTION_RE / PSST_SCALE_RE / PSST_TEAM_RE`
- 점수 연동: `doc_quality_score.score_document(..., psst_ratio=..., ...)` → PSST·보고서구조(10점)
- 오케스트레이션: `document_quality_orchestrator.DocumentQualityOrchestrator.run(...)`
  (유형이 business_plan/pitch_deck 일 때만 PSST 검사 호출)
- 진입 CLI: `app/document_quality_orchestrator.py`, `scripts/run_document_quality_harness.py`
