# 문서 유형 분류 규칙 (DOCUMENT_TYPE_RULES)

> 기준 코드: `app/auto_write/services/document_type_classifier.py`
> 분류 방식: 규칙 기반(키워드 시그니처 + 가중 점수). 모호 시에만 선택적 AI 보조.
> 진입 함수: `classify_text(text, *, filename="")` / `classify_docx(path, *, openai_service=None)` → `DocTypeResult`

이 문서는 위 코드의 상수와 시그니처를 그대로 인용한다. 함수명·상수명·키워드·가중치를 임의로 바꾸지 마라.

---

## 1. 유형 코드 ↔ 라벨 (9종)

상수 `_TYPE_LABELS` 기준.

| 유형 코드 | 라벨 | 비고 |
|-----------|------|------|
| `business_plan` | 사업계획서 | PSST 검사 대상 |
| `rnd_plan` | R&D 연구개발계획서 | |
| `pitch_deck` | 발표평가 자료 | PSST 검사 대상 |
| `consulting_report` | 컨설팅 보고서 | |
| `policy_fund_report` | 정책자금 검토보고서 | |
| `certification_report` | 인증 검토보고서 | |
| `export_report` | 수출컨설팅 보고서 | |
| `field_clinic_report` | 현장클리닉 보고서 | |
| `generic_submission` | 기타 제출문서 | fallback (시그니처 없음) |

> `generic_submission` 은 `_SIGNATURES` 에 키워드가 없다. 최고점이 `_MIN_SCORE` 미만일 때 fallback 으로만 반환된다.

---

## 2. 유형별 키워드 시그니처 (가중치)

상수 `_SIGNATURES` 기준. 매칭은 **부분일치 + 대소문자 무시**(`kw.lower() in haystack.lower()`). `haystack` 은 `"{filename}\n{text}"`.

### business_plan (사업계획서)

| 키워드 | 가중치 |
|--------|--------|
| 사업계획서 | 5 |
| PSST | 5 |
| 문제인식 | 3 |
| 실현가능성 | 3 |
| 성장전략 | 3 |
| 창업아이템 | 3 |
| 팀구성 | 2 |
| Problem | 2 |
| Solution | 2 |
| Scale | 2 |
| Team | 2 |
| 사업화 | 2 |
| BM | 1 |
| 시장진입 | 1 |

### rnd_plan (R&D 연구개발계획서)

| 키워드 | 가중치 |
|--------|--------|
| 연구개발계획서 | 5 |
| 연구개발 | 4 |
| 기술개발목표 | 4 |
| TRL | 4 |
| R&D | 3 |
| 성능지표 | 3 |
| 실험방법 | 3 |
| 선행기술 | 2 |
| 특허분석 | 2 |
| 기술성 | 2 |
| 개발내용 | 2 |

### pitch_deck (발표평가 자료)

| 키워드 | 가중치 |
|--------|--------|
| 발표평가 | 5 |
| 피칭 | 4 |
| 데모데이 | 4 |
| 발표 | 3 |
| IR | 3 |
| Pitch | 3 |
| 투자유치 | 2 |
| Q&A | 2 |
| 슬라이드 | 2 |

### consulting_report (컨설팅 보고서)

| 키워드 | 가중치 |
|--------|--------|
| 컨설팅보고서 | 5 |
| 컨설팅 | 4 |
| 진단결과 | 4 |
| 개선과제 | 4 |
| 기업현황 | 3 |
| 경영진단 | 3 |
| 실행계획 | 2 |
| 기대효과 | 2 |
| As-Is | 2 |
| To-Be | 2 |
| SWOT | 1 |

### policy_fund_report (정책자금 검토보고서)

| 키워드 | 가중치 |
|--------|--------|
| 정책자금 | 5 |
| 상환재원 | 5 |
| 자금용도 | 4 |
| 매출추이 | 3 |
| 신용평가 | 3 |
| 융자 | 3 |
| 담보 | 2 |
| 보증 | 2 |
| 운전자금 | 2 |
| 시설자금 | 2 |
| 리스크 | 1 |

### certification_report (인증 검토보고서)

| 키워드 | 가중치 |
|--------|--------|
| 인증요건 | 5 |
| 인증검토 | 5 |
| 인증 | 4 |
| 충족여부 | 4 |
| 미비서류 | 4 |
| 보완과제 | 3 |
| 이노비즈 | 3 |
| 메인비즈 | 3 |
| 벤처기업 | 2 |
| ISO | 2 |

### export_report (수출컨설팅 보고서)

| 키워드 | 가중치 |
|--------|--------|
| 수출컨설팅 | 5 |
| 수출 | 4 |
| 바이어 | 4 |
| HS코드 | 4 |
| 해외시장 | 3 |
| FTA | 3 |
| 통관 | 3 |
| 수출입 | 3 |
| 관세 | 2 |
| 무역 | 2 |
| 글로벌진출 | 2 |

### field_clinic_report (현장클리닉 보고서)

| 키워드 | 가중치 |
|--------|--------|
| 현장클리닉 | 5 |
| 현장진단 | 4 |
| 클리닉 | 4 |
| 현장지도 | 4 |
| 개선처방 | 4 |
| 현장방문 | 3 |
| 애로사항 | 3 |
| 처방 | 3 |

---

## 3. 점수·임계값·신뢰도(confidence) 산식

### 상수

| 상수 | 값 | 의미 |
|------|----|------|
| `_MIN_SCORE` | 4 | 최고점이 이 값 **미만**이면 `generic_submission` 으로 분류 |
| `_AMBIGUITY_GAP` | 3 | 1·2위 점수차가 이 값 **이하**면 모호 → (옵션) AI 보조 |

### 점수 계산

- 각 유형 코드별로 시그니처 키워드를 순회하며, 부분일치 시 가중치를 누적한다 → `scores[type_code]`.
- 매칭된 키워드는 `matched[type_code]` 에 기록(결과의 `matched_keywords`, 최대 20개).
- `ranked = sorted(scores.items(), key=점수, reverse=True)` 로 정렬.
- `top_code, top_score = ranked[0]`, `second_score = ranked[1][1]`.

### 분기 (`classify_text`)

| 조건 | 반환 |
|------|------|
| `top_score < _MIN_SCORE` (4 미만) | `type_code="generic_submission"`, `confidence=0.3`, `matched_keywords=[]`, `method="rule"` |
| `top_score >= _MIN_SCORE` | `top_code` 반환, confidence 아래 산식, `method="rule"` |

### confidence 산식 (top_score ≥ 4 인 경우)

```
total       = sum(max(0, v) for v in scores.values()) or 1
gap_factor  = min(1.0, (top_score - second_score) / max(1, top_score))
confidence  = min(0.99, 0.4 + 0.4 * (top_score / total) + 0.2 * gap_factor)
```

- 기본값 0.4 + (1위 점수 비중 × 0.4) + (1·2위 격차 비율 × 0.2), 상한 0.99.
- `generic_submission` fallback 의 confidence 는 고정 0.3.

### AI 보조 (`classify_docx`, 선택)

- `openai_service` 가 없거나 `available` 이 False → 규칙 결과 그대로 반환.
- `(top - second) > _AMBIGUITY_GAP` (격차 3 초과) → 충분히 명확 → AI 미사용, 규칙 결과 반환.
- 격차가 `_AMBIGUITY_GAP` 이하(모호)일 때만 `openai_service.complete_json(system, user)` 호출.
  - AI 반환 `type_code` 가 `_TYPE_LABELS` 에 있으면 채택: `method="ai"`, `confidence = max(기존, 0.85)`.
  - 예외 발생 시 무시하고 규칙 결과 유지(try/except).

---

## 4. 유형별 적용 품질 규칙 (구조 적합성 점검 포인트)

분류 결과(`type_code`)에 따라 적용·점검하는 품질 규칙이 달라진다. 아래는 유형별 핵심 점검 항목이다.
(PSST 검사는 코드상 `business_plan` / `pitch_deck` 에만 적용된다. `psst_check.check_psst` 참조.)

| 유형 코드 | 라벨 | 핵심 구조·품질 점검 항목 |
|-----------|------|--------------------------|
| `business_plan` | 사업계획서 | **PSST 4영역**(Problem/Solution/Scale/Team), 평가항목 충족, 정량 KPI(수치 근거) |
| `rnd_plan` | R&D 연구개발계획서 | 기술개발목표, 성능지표(정량), TRL(기술성숙도), 사업화 계획 |
| `consulting_report` | 컨설팅 보고서 | 현황 → 진단 → 개선 → 실행 → 기대효과 흐름 |
| `policy_fund_report` | 정책자금 검토보고서 | 자금용도, 상환재원, 매출추이, 담보·보증, 리스크 |
| `certification_report` | 인증 검토보고서 | 인증요건, 충족여부, 미비서류, 보완과제 |
| `export_report` | 수출컨설팅 보고서 | 해외시장, 바이어, FTA, HS코드 |
| `field_clinic_report` | 현장클리닉 보고서 | 현장진단, 애로(애로사항), 처방, 개선(개선처방) |
| `pitch_deck` | 발표평가 자료 | **PSST 4영역** 점검(사업계획서와 동일), 발표 구조 |
| `generic_submission` | 기타 제출문서 | 유형 특화 구조 점검 없음(일반 후처리만) |

### PSST 4영역 (business_plan / pitch_deck)

`psst_check.check_psst(doc) → PSSTReport`. 4영역 × 각 4개 하위항목, 등급: 누락 / 미흡 / 적정 / 우수.
섹션 헤더 정규식은 `project_service.ProjectService` 의 `PSST_PROBLEM_RE` / `PSST_SOLUTION_RE` / `PSST_SCALE_RE` / `PSST_TEAM_RE` 를 재사용한다.

| 영역 | 코드상 영역 키 | 의미 |
|------|----------------|------|
| Problem | problem | 문제인식 |
| Solution | solution | 실현가능성·해결방안 |
| Scale | scale | 성장전략·시장확장 |
| Team | team | 팀구성 |

---

## 5. 결과 객체 (`DocTypeResult`)

| 필드 | 타입 | 설명 |
|------|------|------|
| `type_code` | str | 분류된 유형 코드 |
| `type_label` | str | `_TYPE_LABELS[type_code]` |
| `confidence` | float | 0.0 ~ 1.0 (`as_dict` 에서 소수 3자리 반올림) |
| `scores` | dict[str,int] | 유형별 누적 점수 |
| `matched_keywords` | list[str] | 1위 유형의 매칭 키워드(직렬화 시 상위 20개) |
| `method` | str | `"rule"` 또는 `"ai"` |

`as_dict()` 직렬화 시: `confidence` 는 `round(…, 3)`, `matched_keywords` 는 `[:20]` 로 잘린다.
