# 문서 품질점수 산정 규칙 (DOCUMENT_QUALITY_SCORE_RULES)

> 기준 코드: `app/auto_write/services/doc_quality_score.py`
> 진입 함수: `score_document(doc, *, doc_type, type_confidence, psst_ratio, image_suggestions, existing_images) -> QualityScore`
> 산정 방식: 후처리가 끝난 DOCX에 **남아있는 결함(잔존 결함)** 을 세어 항목별 만점에서 감점한다. AI를 호출하지 않으며 동일 입력에는 항상 동일 점수를 반환한다(결정론).
> 결과 객체: `QualityScore(total, grade, passed, items: list[ScoreItem])`, 각 항목은 `ScoreItem(key, label, score, max_score, defects, detail)`.

---

## 1. 배점표 (총 100점, 9항목)

| 번호 | `key` | `label` | 만점 | 감점 단위 | 잔존 결함 스캐너 |
|------|-------|---------|------|-----------|-------------------|
| 1 | `guide_removal` | 안내문구 제거 | 15 | critical -5 / general -1 | `_scan_guide(doc)` |
| 2 | `bullet_spacing` | 글머리표 공백 정리 | 10 | 결함 단락당 -1 | `_scan_bullet(doc)` |
| 3 | `paragraph_cleanup` | 문단·공백 정리 | 10 | 연속 빈단락 그룹당 -2 | `_scan_empty_groups(doc)` |
| 4 | `font_consistency` | 글자크기·스타일 일관성 | 15 | (초과 폰트종류 + 이상치)당 -2 | `_scan_font_sizes(doc)` |
| 5 | `table_quality` | 표 내부 품질 | 10 | 결함 셀당 -1 | `_scan_table_ws(doc)` |
| 6 | `emphasis` | 주요문장 강조 적정성 | 10 | 구간 점수(0/없음·과잉 감점) | `_count_bold_paragraphs` / `_count_nonempty_paragraphs` |
| 7 | `type_structure` | 문서 유형별 구조 적합성 | 15 | 가중식(신뢰도+구조키워드) | `_TYPE_STRUCTURE_KEYWORDS` |
| 8 | `psst_structure` | PSST/보고서 구조 충족도 | 10 | 충족 비율 비례 | `psst_ratio` 또는 보고서 키워드 |
| 9 | `image_suggestion` | 이미지·도식 제안 적정성 | 5 | 제안·이미지 유무 | `image_suggestions` / `existing_images` |

> 총점 `total = sum(i.score for i in items)`. 항목 점수는 모두 `max(0.0, ...)` 로 하한 0점 보장(음수 없음).

---

## 2. 항목별 감점 산식

### 항목 1. 안내문구 제거 (15점) — `guide_removal`

- 스캐너: `_scan_guide(doc) -> (critical, general)`. 전체 단락 텍스트 + 모든 표 셀 텍스트를 검사한다.
  - `critical` += 1 : `_CRITICAL_GUIDE_RE`(=`QAService.CRITICAL_GUIDE_MARKER_RE`) 또는 `_PURE_GUIDE_RE` 매칭 시.
  - `general` += 1 : 위에 안 걸리고 `_GENERAL_GUIDE_RE`(=`QAService.GUIDE_MARKER_RE`) 매칭 시.
- 산식: `s1 = max(0.0, 15.0 - crit * 5.0 - gen * 1.0)`
- `defects = crit + gen`, `detail = "critical=<crit>, general=<gen>"`

| 잔존 결함 | 감점 |
|-----------|------|
| critical 1건 | -5 |
| general 1건 | -1 |

### 항목 2. 글머리표 공백 정리 (10점) — `bullet_spacing`

- 스캐너: `_scan_bullet(doc) -> int`. 각 단락 텍스트가 `_BULLET_PREFIX_RE`(잔존 글머리표 접두) 또는 `_MULTI_SPACE_RE`(다중 공백) 에 매칭되면 +1.
- 산식: `s2 = max(0.0, 10.0 - b * 1.0)`
- `defects = b`, `detail = "잔존 글머리표/다중공백 단락=<b>"`

### 항목 3. 문단·공백 정리 (10점) — `paragraph_cleanup`

- 스캐너: `_scan_empty_groups(doc) -> int`. **2개 이상 연속**된 빈 단락을 1개 그룹으로 카운트(`run >= 2`).
- 산식: `s3 = max(0.0, 10.0 - eg * 2.0)`
- `defects = eg`, `detail = "연속 빈단락 그룹=<eg>"`

### 항목 4. 글자크기·스타일 일관성 (15점) — `font_consistency`

- 스캐너: `_scan_font_sizes(doc) -> (kinds, outliers)`.
  - `kinds` = 본문 run에서 실제 지정된 폰트 크기(pt) **종류 수**(`size is None` 은 제외).
  - `outliers` = 8pt 미만 또는 18pt 초과 run 수(`pt < 8 or pt > 18`).
- 감점: `penalty4 = max(0, kinds - 4) * 2.0 + outliers * 2.0` → 폰트 종류가 **4종 이하면 종류 감점 없음**, 5종부터 초과분에 종류당 -2, 이상치 1건당 -2.
- 산식: `s4 = max(0.0, 15.0 - penalty4)`
- `defects = max(0, kinds - 4) + outliers`, `detail = "폰트 종류=<kinds>, 이상치=<outliers>"`

### 항목 5. 표 내부 품질 (10점) — `table_quality`

- 스캐너: `_scan_table_ws(doc) -> int`. 모든 표 셀 텍스트에서 `t != t.strip()`(앞뒤 공백) 또는 `_MULTI_SPACE_RE`(셀 내 다중 공백) 매칭 시 +1.
- 산식: `s5 = max(0.0, 10.0 - tw * 1.0)`
- `defects = tw`, `detail = "공백 결함 셀=<tw>"`

### 항목 6. 주요문장 강조 적정성 (10점) — `emphasis`

- 측정: `bold_p = _count_bold_paragraphs(doc)`(굵게 run을 가진 단락 수), `total_p = max(1, _count_nonempty_paragraphs(doc))`, `ratio = bold_p / total_p`.
- 구간 점수(감점 산식 아님, 구간 고정값):

| 조건 | 점수 `s6` | `defects` | `detail` |
|------|-----------|-----------|----------|
| `bold_p == 0` (강조 없음) | 4.0 | 1 | 강조 없음(핵심문장 미강조) |
| `ratio > 0.35` (과잉 강조) | 5.0 | 1 | 과잉 강조(비율 <ratio>) |
| 그 외 (적정) | 10.0 | 0 | 강조 `<bold_p>`개(비율 <ratio>) 적정 |

> `defects` 는 `0 if s6 == 10 else 1`.

### 항목 7. 문서 유형별 구조 적합성 (15점) — `type_structure`

- 유형별 필수 구조 키워드: `_TYPE_STRUCTURE_KEYWORDS[doc_type]`.

| `doc_type` | 구조 키워드 |
|------------|-------------|
| `business_plan` | 문제, 해결, 시장, 성장, 팀, 사업화 |
| `rnd_plan` | 목표, 기술, 성능, 방법, 일정, 사업화 |
| `pitch_deck` | 문제, 솔루션, 시장, 팀, 투자 |
| `consulting_report` | 현황, 진단, 개선, 실행, 기대효과 |
| `policy_fund_report` | 자금, 용도, 상환, 매출, 리스크 |
| `certification_report` | 요건, 충족, 보완, 서류 |
| `export_report` | 수출, 시장, 바이어, 전략 |
| `field_clinic_report` | 현황, 진단, 애로, 처방, 개선 |
| `generic_submission` | (없음) |

- `present` = 전체 텍스트(단락+셀)에 포함된 구조 키워드 수.
- `struct_ratio = present / len(kws)` (키워드가 없으면 `0.7` 고정).
- 산식: `s7 = round(15.0 * (0.4 * min(1.0, type_confidence) + 0.6 * struct_ratio), 1)`
  - 즉 신뢰도 가중 40% + 구조키워드 충족 가중 60%. `type_confidence` 는 1.0 상한.
- `defects = len(kws) - present`, `detail = "유형=<doc_type>, 구조키워드 <present>/<len>, conf=<type_confidence>"`

### 항목 8. PSST/보고서 구조 충족도 (10점) — `psst_structure`

- `psst_ratio` 가 주어진 경우(PSST 적용 유형: business_plan / pitch_deck):
  - 산식: `s8 = round(10.0 * psst_ratio, 1)`, `detail = "PSST 충족 <psst_ratio>"`
- `psst_ratio is None` 인 경우(그 외 유형) → 보고서 구조 키워드로 대체:
  - 키워드: `("현황", "분석", "개선", "결론", "계획", "기대")`
  - `rp` = 포함된 키워드 수, 산식: `s8 = round(10.0 * (rp / 6), 1)`, `detail = "보고서 구조 키워드 <rp>/6"`
- 두 경우 모두 `defects = 0`.

### 항목 9. 이미지·도식 제안 적정성 (5점) — `image_suggestion`

| 조건 | 점수 `s9` | `defects` | `detail` |
|------|-----------|-----------|----------|
| `image_suggestions > 0` 또는 `existing_images > 0` | 5.0 | 0 | 제안 `<n>`건, 기존 이미지 `<m>`장 |
| 둘 다 0 | 2.0 | 1 | 도식 제안 없음(시각화 여지 점검 필요) |

> `defects` 는 `0 if s9 == 5 else 1`.

---

## 3. 품질 게이트 (등급·통과)

총점 `total` 으로 등급 `grade` 와 통과 여부 `passed` 를 결정한다.

```python
grade = ("우수" if total >= 90 else "통과" if total >= 85
         else "보완 필요" if total >= 70 else "실패")
passed = total >= 85
```

| 총점 구간 | `grade` | `passed` | 의미 |
|-----------|---------|----------|------|
| 90 이상 | 우수 | True | 제출 가능 우수 수준 |
| 85 이상 ~ 90 미만 | 통과 | True | 게이트 통과 |
| 70 이상 ~ 85 미만 | 보완 필요 | False | 보완 루프 대상 |
| 70 미만 | 실패 | False | 보완 루프 대상 |

> **통과 기준은 85점**(`passed = total >= 85`). 90점은 "우수" 라벨일 뿐 통과 임계가 아니다.

---

## 4. 미달 시 보완 루프 (오케스트레이터 게이팅)

- 게이트 미달(`passed == False`, 즉 total < 85)이면 `DocumentQualityOrchestrator.run(...)` 이 후처리(`run_all`)와 재채점(`score_document`)을 반복하는 **보완 루프**를 수행한다.
- **최대 10회** 반복한다.
- **수렴 조기종료:** 추가 후처리로 점수 개선이 멈추면(수렴) 10회 도달 전이라도 루프를 조기종료한다.
- 조기종료·미달 종료 시에는 잔여 결함 항목(예: 수동 확인이 필요한 강조·구조·이미지 항목)을 리포트(`md` + `json`)에 명시한다.

---

## 5. 결과 직렬화

- `QualityScore.as_dict()` → `{"total": <1자리 반올림>, "grade", "passed", "items": [...]}`.
- `ScoreItem.as_dict()` → `{"key", "label", "score"(1자리 반올림), "max_score", "defects", "detail"}`.
