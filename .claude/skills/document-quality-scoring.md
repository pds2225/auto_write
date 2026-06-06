---
name: document-quality-scoring
description: >-
  후처리가 끝난 DOCX 의 100점 만점 품질점수를 9항목 배점으로 결정론적 산정하고 게이트(90 우수/85 통과/70 보완/미만 실패)를
  판정한다. "품질점수 산정", "문서 점수 매겨줘", "DOCX 점수화", "품질 게이트 판정", "85점 넘었는지 확인",
  "문서 등급 평가", "후처리 결과 채점" 요청 시 사용. 점수 재산정·재실행·수정·보완(특정 항목 감점 원인 재확인)·게이트
  재판정·회귀 채점 요청도 이 스킬로 처리. score_document 가 핵심 함수이며 AI 를 호출하지 않는다.
---

## 목적

후처리(run_all)가 끝난 DOCX 에 남아 있는 잔존 결함을 항목별로 세어, 만점에서 감점하는 방식으로 100점 만점 품질점수를 결정론적으로 산정한다. 동일 입력이면 항상 동일 점수를 반환한다(AI 미사용). 산정된 총점으로 통과/실패 게이트를 판정하여 오케스트레이터의 보완 루프 종료 여부를 결정한다.

핵심 함수: `app/auto_write/services/doc_quality_score.py` 의 `score_document(doc, *, doc_type, type_confidence, psst_ratio, image_suggestions, existing_images) -> QualityScore`.

## 적용 대상

- 후처리가 끝난 DOCX (오케스트레이터가 run_all 적용 후 호출). 원본 그대로 점수만 보고 싶을 때도 사용 가능.
- 유형코드(doc_type): business_plan / rnd_plan / pitch_deck / consulting_report / policy_fund_report / certification_report / export_report / field_clinic_report / generic_submission.
- 입력은 python-docx 의 `Document` 객체. 분류 결과(doc_type, type_confidence), PSST 충족비율(psst_ratio), 이미지 제안 수(image_suggestions), 기존 이미지 수(existing_images)를 오케스트레이터가 주입한다.

## 탐지 규칙

각 항목은 코드의 잔존 결함 스캐너로 결함 수를 센다. 실제 동작 그대로 인용한다.

1. 안내문구 제거 (15점): `_scan_guide(doc)` 가 전체 단락·표 셀 텍스트를 검사. `_CRITICAL_GUIDE_RE`(=QAService.CRITICAL_GUIDE_MARKER_RE) 또는 `_PURE_GUIDE_RE` 매칭은 critical, 그 외 `_GENERAL_GUIDE_RE`(=QAService.GUIDE_MARKER_RE) 매칭은 general 로 분류.
2. 글머리표 공백 정리 (10점): `_scan_bullet(doc)` 가 단락 텍스트에서 `_BULLET_PREFIX_RE` 또는 `_MULTI_SPACE_RE` 매칭 단락 수를 셈.
3. 문단·공백 정리 (10점): `_scan_empty_groups(doc)` 가 연속 빈 단락 2개 이상 그룹 수를 셈.
4. 글자크기·스타일 일관성 (15점): `_scan_font_sizes(doc)` 가 run 폰트 크기 종류 수(kinds)와 8pt 미만/18pt 초과 이상치 수(outliers)를 셈.
5. 표 내부 품질 (10점): `_scan_table_ws(doc)` 가 셀 텍스트의 앞뒤 공백(strip 불일치) 또는 `_MULTI_SPACE_RE` 결함 셀 수를 셈.
6. 주요문장 강조 적정성 (10점): `_count_bold_paragraphs(doc)` / `_count_nonempty_paragraphs(doc)` 로 bold 단락 비율 계산.
7. 문서 유형별 구조 적합성 (15점): `_TYPE_STRUCTURE_KEYWORDS[doc_type]` 키워드의 전체 텍스트 내 등장 비율(struct_ratio)과 type_confidence 결합.
8. PSST/보고서 구조 충족도 (10점): psst_ratio 가 주어지면 PSST 충족비율, None 이면 보고서 구조 키워드(현황/분석/개선/결론/계획/기대) 등장 비율.
9. 이미지·도식 제안 적정성 (5점): image_suggestions 또는 existing_images 가 1 이상인지 여부.

## 수정 규칙

이 스킬은 문서를 수정하지 않는다. 채점만 수행한다. 각 항목 점수 산식은 코드와 정확히 일치한다.

1. 안내문구: `s1 = max(0, 15 - critical*5 - general*1)`.
2. 글머리표: `s2 = max(0, 10 - bullet결함*1)`.
3. 문단·공백: `s3 = max(0, 10 - 빈단락그룹*2)`.
4. 글자크기: `penalty = max(0, kinds-4)*2 + outliers*2`, `s4 = max(0, 15 - penalty)` (폰트 종류 4개 이하 양호).
5. 표 내부: `s5 = max(0, 10 - 결함셀*1)`.
6. 강조: bold 단락 0개 → 4점(미강조), 비율 0.35 초과 → 5점(과잉), 그 외 → 10점(적정).
7. 유형구조: `s7 = round(15 * (0.4*min(1,type_confidence) + 0.6*struct_ratio), 1)`. 유형 키워드가 없으면 struct_ratio=0.7 고정.
8. PSST/보고서: psst_ratio 주입 시 `s8 = round(10*psst_ratio, 1)`, 미주입 시 `s8 = round(10*(보고서키워드매칭/6), 1)`.
9. 이미지: 제안/기존 이미지 있으면 5점, 없으면 2점.

총점 = 9항목 합. 등급/게이트:
- 90점 이상 → "우수"
- 85점 이상 → "통과"
- 70점 이상 → "보완 필요"
- 70점 미만 → "실패"
- `passed = (total >= 85)`. 즉 게이트 통과 기준은 85점이다.

반환값 `QualityScore(total, grade, passed, items)`. 각 item 은 `ScoreItem(key, label, score, max_score, defects, detail)`. `.as_dict()` 로 직렬화.

## 예외 규칙

- `score_document` 는 키워드 전용 인자(`*`)다. 반드시 `doc_type=...`, `psst_ratio=...` 형태로 호출한다(위치 인자로 doc 외 전달 금지).
- PSST 미적용 유형(business_plan·pitch_deck 외)은 psst_ratio 를 None 으로 두면 8번 항목이 보고서 구조 키워드로 자동 대체된다. None 전달은 정상 동작이며 오류가 아니다.
- 유형 키워드가 비어 있는 generic_submission 은 struct_ratio 가 0.7 로 고정되어 7번 항목 감점이 제한된다(임의 보정 아님, 설계값).
- 폰트 크기가 명시되지 않은 run(`run.font.size is None`)은 4번 채점에서 무시한다(스타일 상속 케이스).
- 빈 문서/빈 단락만 있는 문서도 예외 없이 채점한다. `_count_nonempty_paragraphs` 가 0이면 분모는 1로 보정되어 ZeroDivision 이 발생하지 않는다.
- 이 스킬 단독으로는 점수만 산출한다. 미달 시 자동 보완 루프는 오케스트레이터가 수행한다(이 스킬은 게이트 판정값만 제공).

## 테스트 방법 (실제 PowerShell 명령)

```powershell
# 1) 하네스 전체 회귀 테스트(점수·게이트 포함)
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q

# 2) 단일 문서 채점 결과를 오케스트레이터로 확인(리포트에 점수·등급·게이트 출력)
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx" --json

# 3) 후처리 없이 진단 덤프로 잔존 결함 눈으로 확인(점수 항목 교차검증)
cd D:\auto_write\app
python _build_chochang.py inspect "결과.docx"
```

채점 함수만 단독 점검할 때(개발용):

```powershell
cd D:\auto_write\app
python -c "from docx import Document; from auto_write.services.doc_quality_score import score_document; d=Document(r'C:\경로\문서.docx'); s=score_document(d, doc_type='business_plan', type_confidence=0.8, psst_ratio=0.75, image_suggestions=2, existing_images=0); print(s.total, s.grade, s.passed); [print(i.label, i.score, i.detail) for i in s.items]"
```

## 실패 시 롤백 기준

- 이 스킬은 문서를 변경하지 않으므로 채점 자체에는 롤백이 필요 없다.
- 채점 결과가 게이트 미달(passed=False)이고 후처리로 문서가 이미 수정된 경우, 원본 복구는 백업 디렉토리에서 수행한다: `python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx`.
- 점수가 비정상(예: 음수, 100 초과, 예외 발생)이면 입력 주입값(doc_type 오타, type_confidence/psst_ratio 범위 0~1 위반)을 먼저 의심한다. 코드 산식상 각 항목은 max(0, ...) 로 음수 방지, 합계는 항목 최대치(15+10+10+15+10+10+15+10+5=100) 이내다.
- 게이트 미달이 반복되면 가장 큰 감점 항목(items 중 max_score-score 가 큰 항목)을 확인하고 해당 세부 스킬(docx-template-cleanup·bullet-spacing-normalization·paragraph-font-sizing 등)로 재후처리한 뒤 재채점한다.

## 품질 점수 반영 (어느 배점 항목에 영향)

이 스킬은 100점 9항목 전체의 산정·합산·게이트 판정을 담당하는 채점 주체다. 직접 영향 항목:

- 안내문구 제거 15 / 글머리표 공백 정리 10 / 문단·공백 정리 10 / 글자크기·스타일 일관성 15 / 표 내부 품질 10 / 주요문장 강조 적정성 10 / 문서 유형별 구조 적합성 15 / PSST·보고서 구조 충족도 10 / 이미지·도식 제안 적정성 5.
- 게이트: total>=90 우수, total>=85 통과(passed), total>=70 보완 필요, 미만 실패. 오케스트레이터의 보완 루프(최대 10회) 종료 판단 근거를 제공한다.

## 연결 코드·CLI (실제 함수/명령)

- 채점 함수: `app/auto_write/services/doc_quality_score.py` → `score_document(doc, *, doc_type='generic_submission', type_confidence=0.0, psst_ratio=None, image_suggestions=0, existing_images=0) -> QualityScore`.
- 데이터클래스: `QualityScore(total, grade, passed, items)`, `ScoreItem(key, label, score, max_score, defects, detail)`. 둘 다 `.as_dict()` 제공.
- 잔존 결함 스캐너(내부): `_scan_guide`, `_scan_bullet`, `_scan_empty_groups`, `_scan_font_sizes`, `_scan_table_ws`, `_count_bold_paragraphs`, `_count_nonempty_paragraphs`.
- 호출 주체: `app/auto_write/services/document_quality_orchestrator.py` 의 `DocumentQualityOrchestrator.run(...)` 파이프라인이 분류·PSST·이미지제안 결과를 주입해 `score_document` 호출 → 게이트 판정 → 미달 시 보완 루프.
- 진입점 CLI: `python document_quality_orchestrator.py <input> [--json]` (점수·등급·게이트가 리포트 md/json 에 기록). 래퍼: `scripts/run_document_quality_harness.py`.
- 교차검증 CLI: `python _build_chochang.py inspect <docx>` (문단/표 덤프로 잔존 결함 육안 확인).
