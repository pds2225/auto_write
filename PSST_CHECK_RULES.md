# PSST 검사 규칙 (PSST_CHECK_RULES)

> 대상 코드: `app/auto_write/services/psst_check.py`
> 섹션 헤더 정규식 재사용: `app/auto_write/services/project_service.py` 의 `ProjectService.PSST_*_RE`
> 본 검사는 결정론적이며 AI 를 호출하지 않는다. 아래 표의 상수·함수명은 실제 코드와 정확히 일치시킨다.

PSST = **Problem(문제인식) / Solution(실현가능성) / Scale-up(성장전략) / Team(팀구성)**

검사 진입점:

- `check_psst(doc) -> PSSTReport` : `Document` 객체를 직접 검사한다.
- `check_psst_docx(path) -> PSSTReport` : 경로를 받아 `Document(str(Path(path)))` 로 로드 후 `check_psst` 호출.

---

## 1. 검사 절차 (`check_psst` 흐름)

1. 본문 추출: `_extract_text(doc, limit=30000)` 로 문단(`doc.paragraphs`) + 표 셀(`doc.tables`) 텍스트를 `\n` 으로 합친다. 표 누적 길이가 `limit(30000)` 을 넘으면 표 순회를 중단한다.
2. 섹션 헤더 존재 여부 판정: `ProjectService.PSST_*_RE` 정규식을 추출 텍스트에 `search` 하여 4영역의 `section_present` 플래그를 만든다.
3. 하위항목 탐지: 영역별 4개 하위항목의 키워드를 본문에서 대소문자 무시(`kw.lower() in text.lower()`)로 탐지. 하나라도 매칭되면 그 항목은 충족(`found += 1`), 아니면 `missing_items` 에 항목 라벨 추가.
4. 등급 산정: 영역별로 `_grade(found, total)` 호출.
5. 전체 비율: `overall_ratio = total_found / total_items` (전 영역 합산, 분모 16).
6. 요약: 등급이 `누락` 또는 `미흡` 인 영역 라벨을 모아 "보완 필요" 로 표기. 없으면 "전 영역 적정 이상."

---

## 2. 영역별 하위항목 · 탐지 키워드 (`_PSST_ITEMS`)

각 영역은 하위항목 4개로 구성된다(`items_total = 4`). 키워드는 `_PSST_ITEMS` 의 실제 튜플과 동일하다.

### 2.1 Problem (문제인식) — `area="problem"`, 라벨 `Problem(문제인식)`

| # | 하위항목 라벨 | 탐지 키워드 |
|---|---------------|-------------|
| 1 | 고객/시장 문제 | `고객`, `시장`, `니즈`, `수요`, `페인`, `불편`, `문제` |
| 2 | 기존 대안 한계 | `기존`, `대안`, `한계`, `기존방식`, `현행`, `종래` |
| 3 | 문제 심각성 | `심각`, `위험`, `리스크`, `비용`, `손실`, `확산` |
| 4 | 수치 근거 | `%`, `억`, `만`, `건`, `명`, `배`, `규모`, `통계` |

섹션 헤더 정규식: `PSST_PROBLEM_RE = re.compile(r"1\.\s*문제\s*인식.*Problem", re.IGNORECASE)`

### 2.2 Solution (실현가능성) — `area="solution"`, 라벨 `Solution(실현가능성)`

| # | 하위항목 라벨 | 탐지 키워드 |
|---|---------------|-------------|
| 1 | 해결방안/핵심기능 | `해결`, `솔루션`, `핵심기능`, `기능`, `서비스`, `제품` |
| 2 | 차별성 | `차별`, `경쟁력`, `독창`, `우위`, `특허`, `기술력` |
| 3 | 구현 가능성 | `구현`, `개발`, `실현`, `검증`, `시제품`, `TRL`, `프로토타입` |
| 4 | 고객 적용 시나리오 | `적용`, `활용`, `시나리오`, `사용`, `도입`, `고객사` |

섹션 헤더 정규식: `PSST_SOLUTION_RE = re.compile(r"2\.\s*실현\s*가능성.*Solution", re.IGNORECASE)`

### 2.3 Scale-up (성장전략) — `area="scale"`, 라벨 `Scale-up(성장전략)`

| # | 하위항목 라벨 | 탐지 키워드 |
|---|---------------|-------------|
| 1 | 시장규모 | `시장규모`, `TAM`, `SAM`, `SOM`, `시장`, `성장률` |
| 2 | 수익모델 | `수익`, `BM`, `비즈니스모델`, `과금`, `라이선스`, `구독` |
| 3 | 판로/성장전략 | `판로`, `유통`, `마케팅`, `성장전략`, `확장`, `진출` |
| 4 | KPI/매출계획 | `KPI`, `매출`, `목표`, `계획`, `로드맵`, `마일스톤` |

섹션 헤더 정규식: `PSST_SCALE_RE = re.compile(r"3\.\s*성장전략.*Scale", re.IGNORECASE)`

### 2.4 Team (팀구성) — `area="team"`, 라벨 `Team(팀구성)`

| # | 하위항목 라벨 | 탐지 키워드 |
|---|---------------|-------------|
| 1 | 대표자 역량 | `대표`, `경력`, `역량`, `전공`, `이력`, `창업자` |
| 2 | 팀 구성 | `팀`, `구성원`, `인력`, `조직`, `직원`, `멤버` |
| 3 | 외부 협력 | `협력`, `파트너`, `제휴`, `자문`, `네트워크`, `MOU` |
| 4 | 수행 경험/실행력 | `경험`, `수행`, `실적`, `성과`, `추진`, `실행` |

섹션 헤더 정규식: `PSST_TEAM_RE = re.compile(r"4\.\s*팀\s*구성.*Team", re.IGNORECASE)`

---

## 3. 등급 기준 (`_grade(found, total)`)

영역별 충족 항목 비율 `ratio = found / total` (total=4) 로 4단계 등급을 매긴다.

| 등급 | 조건 (코드 기준) | 충족 항목 수 (4개 중) | 의미 |
|------|------------------|------------------------|------|
| 누락 | `total <= 0` 또는 `found == 0` | 0개 | 해당 영역 내용이 사실상 없음 |
| 미흡 | `ratio < 0.6` (누락 제외) | 1개 (=0.25) | 핵심 요소 절반 미만 |
| 적정 | `0.6 <= ratio < 0.9` | 3개 (=0.75) | 통과 가능 수준 |
| 우수 | `ratio >= 0.9` | 4개 (=1.0) | 전 항목 충족 |

> 주의: 하위항목이 4개이므로 `found=2` 이면 `ratio=0.5 < 0.6` 라서 **미흡**, `found=3` 이면 `ratio=0.75` 라서 **적정** 이다. 0.6 경계상 2개로는 적정이 될 수 없다.

등급 분기 코드:

```python
def _grade(found, total):
    if total <= 0 or found == 0:
        return "누락"
    ratio = found / total
    if ratio >= 0.9:
        return "우수"
    if ratio >= 0.6:
        return "적정"
    return "미흡"
```

---

## 4. 섹션 헤더 정규식 재사용 (`ProjectService.PSST_*_RE`)

`psst_check.py` 는 헤더 정규식을 자체 구현하지 않고 `project_service.ProjectService` 의 상수를 그대로 재사용한다(중복 구현 금지).

| 영역 | 상수명 | 정규식 패턴 | 플래그 |
|------|--------|-------------|--------|
| problem | `PSST_PROBLEM_RE` | `1\.\s*문제\s*인식.*Problem` | `re.IGNORECASE` |
| solution | `PSST_SOLUTION_RE` | `2\.\s*실현\s*가능성.*Solution` | `re.IGNORECASE` |
| scale | `PSST_SCALE_RE` | `3\.\s*성장전략.*Scale` | `re.IGNORECASE` |
| team | `PSST_TEAM_RE` | `4\.\s*팀\s*구성.*Team` | `re.IGNORECASE` |

매칭 결과는 영역별 `section_present` (`PSSTAreaResult.section_present`) 로 저장된다.
헤더 정규식은 **양식 섹션 헤더 존재 여부**만 판정하며, 내용 충실도 등급(`grade`)에는 직접 반영되지 않는다(키워드 탐지로 별도 산정). 따라서 헤더는 있으나 내용이 비면 `section_present=True` 이면서도 등급이 `누락/미흡` 일 수 있다 — 이 불일치 자체가 보완 신호다.

---

## 5. 결과 자료구조 (`PSSTAreaResult`, `PSSTReport`)

### `PSSTAreaResult` (영역 단위)

| 필드 | 타입 | 설명 |
|------|------|------|
| `area` | str | `problem`/`solution`/`scale`/`team` |
| `label` | str | `_AREA_LABELS` 라벨 (예: `Problem(문제인식)`) |
| `section_present` | bool | 헤더 정규식 매칭 여부 |
| `items_total` | int | 하위항목 총수(4) |
| `items_found` | int | 충족 항목 수 |
| `missing_items` | list[str] | 미충족 하위항목 라벨 목록 |
| `grade` | str | `누락`/`미흡`/`적정`/`우수` (기본값 `누락`) |

직렬화: `as_dict()` 로 위 필드를 dict 반환.

### `PSSTReport` (문서 단위)

| 필드 | 타입 | 설명 |
|------|------|------|
| `applicable` | bool | 검사 적용 여부(`check_psst` 는 항상 `True` 반환) |
| `areas` | list[PSSTAreaResult] | 4영역 결과 |
| `overall_ratio` | float | 전체 충족 비율 = `total_found / total_items` (분모 16) |
| `summary` | str | 충족 합계 + 보완 필요 영역 요약 |

직렬화: `as_dict()` 는 `overall_ratio` 를 `round(..., 3)` 로 반올림하고 `areas` 를 각 `as_dict()` 로 펼친다.

`summary` 형식 예: `PSST 전체 충족 11/16 (69%). 보완 필요: Problem(문제인식), Team(팀구성)`

---

## 6. 평가위원 관점 보완 도출

검사 결과를 평가위원 시각으로 환산해 보완 지시를 만든다. `missing_items` 와 `grade` 를 근거로 사용한다.

### 6.1 등급별 조치 기준

| 등급 | 평가위원 인식 | 보완 우선순위 | 조치 |
|------|----------------|----------------|------|
| 누락 | 해당 영역 평가 불가 → 감점/탈락 위험 | 최우선 | 해당 영역 4개 하위항목을 처음부터 작성 |
| 미흡 | 근거 부족으로 신뢰도 낮음 | 높음 | `missing_items` 항목을 채워 최소 적정(3/4) 이상으로 |
| 적정 | 통과 가능하나 변별력 약함 | 중간 | 남은 1개 항목 보강해 우수(4/4) 지향 |
| 우수 | 설득력 충분 | 낮음 | 수치·근거 정밀화로 완성도 유지 |

### 6.2 영역별 평가위원 점검 포인트 (미충족 시 보완 문구 방향)

| 영역 | 평가위원이 확인하는 것 | 미충족 시 보완 방향 |
|------|------------------------|----------------------|
| Problem | 누구의 어떤 문제인가, 왜 지금 심각한가, 근거 수치가 있는가 | 고객/시장 페인을 구체화하고 기존 대안의 한계와 정량 근거(`%`, `억`, `건` 등)를 명시 |
| Solution | 무엇으로 해결하나, 남과 무엇이 다른가, 실제 구현 가능한가 | 핵심기능·차별성(특허/기술력)·구현 단계(TRL/시제품)·적용 시나리오를 분리 서술 |
| Scale-up | 시장이 충분히 큰가, 어떻게 돈을 버나, 성장 경로가 있는가 | 시장규모(TAM/SAM/SOM)·수익모델(BM)·판로·KPI/매출 로드맵을 수치로 제시 |
| Team | 이 팀이 해낼 수 있는가, 역할 분담과 협력은 되는가 | 대표 역량·팀 구성·외부 협력(MOU/자문)·과거 수행 실적을 근거로 제시 |

### 6.3 보완 도출 절차 (권장)

1. `PSSTReport.summary` 로 보완 필요 영역을 먼저 파악한다.
2. 각 영역 `PSSTAreaResult.missing_items` 의 라벨을 그대로 보완 항목으로 쓴다.
3. 해당 라벨의 키워드(2장 표)를 작성 가이드 어휘로 활용해 본문에 실제 내용을 추가한다.
4. 헤더는 있으나(`section_present=True`) 등급이 낮은 영역은 "형식만 있고 내용 부족" 으로 분류해 우선 보완한다.
5. 재검사로 영역 등급이 적정(3/4) 이상으로 오르는지 확인한다.

---

## 7. 적용 범위 메모

- 본 검사는 PSST 양식을 따르는 유형(주로 `business_plan`, `pitch_deck`)에 의미가 크다.
- 오케스트레이터 파이프라인(`document_quality_orchestrator.py`)에서 PSST 검사는 해당 유형에 한해 수행되며, 결과는 품질점수 9항목 중 **PSST·보고서구조(10점)** 산정의 입력(`psst_ratio` = `PSSTReport.overall_ratio`)으로 전달된다.
- 키워드 탐지는 부분 문자열 일치(대소문자 무시)이므로, 관련 없는 문맥에서 키워드가 우연히 포함되면 과대 충족될 수 있다. 등급은 참고 지표이며 최종 판단은 본문 내용 확인과 병행한다.
