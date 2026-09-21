# AUTO_WRITE 실사용 제품 흐름 — AW-005

> 기준일: 2026-09-21  
> 작업 브랜치: `feat/aw005-product-flow-actual-use-20260921`  
> 목적: 이미 있는 엔진을 버리지 않고, 비개발자가 실제로 쓸 수 있는 **하나의 문서작성 제품 흐름**으로 정리한다.  
> 실행 정본: `docs/AUTO_WRITE_웹앱_최종_요구사항_20260816.md`  
> 구조 정본: `docs/WEBAPP_MODULE_TO_FORM_TOC.md`

## 1. 제품을 한 문장으로

**공고 + 빈 양식을 먼저 넣고, 기존 사업계획서가 있으면 재사용하며, 작성 가능한 파트부터 근거와 함께 작성하고, 부족한 정보만 나중에 추가로 받는 사업계획서 작성 도구.**

새 작성과 기존 계획서 활용은 별도 제품이 아니다.  
기존 계획서가 없으면 같은 화면에서 그 칸만 비운다.

---

## 2. 사용자가 실제로 보는 흐름

### 화면 1 — 문서 시작

처음에는 세 칸만 보인다.

| 역할 | 필수 | 사용자 행동 |
|---|---:|---|
| 공고 | 필수 | 공고문 파일 업로드 |
| 양식 | 필수 | 빈 신청서/사업계획서 양식 업로드 |
| 기존 사업계획서 | 선택 | 과거 작성본이 있으면 업로드 |

- 한 파일이 공고+양식이면 두 역할로 표시 가능.
- 기존 계획서가 없어도 진행 가능.
- 회사소개, 사업자등록증, 재무, 이력서는 첫 화면에 펼치지 않는다.
- 파일 역할은 시스템이 제안할 수 있으나 **사용자 확정 전 작성 금지**.

**CTA: `[자료 분석 시작]`**

### 화면 2 — 이번 양식에서 작성할 파트

양식의 **대목차**를 기준으로 보여 준다.

예:

```text
1. 사업 개요
2. 문제 해결의 타당성
3. 사업화 가능성
4. 지속가능성·사회적 기여
5. 팀/기업가정신
```

각 파트 상태는 복잡한 점수 대신 아래 3개만 사용한다.

- **바로 작성 가능** — 현재 자료로 작성 가능
- **일부 작성 가능** — 현재 자료로 먼저 쓰고 부족한 항목만 추가 요청
- **정보 필요** — 필수 사실이 없어 해당 부분은 보류

현재 구현 자산:
- `section_matcher.py`가 WRITABLE / PARTIAL_WRITABLE / BLOCKED_REQUIRED_INFO / NO_USABLE_MATERIAL 판정을 이미 제공.
- `step2_output_contract.py`가 Fact / Narrative Evidence / Conflict + source/locator 계약을 제공.

**핵심 원칙: 모든 정보를 받을 때까지 전체 작성 보류 금지.**

### 화면 3 — 선택한 파트의 재료

왼쪽: 이번 대목차  
오른쪽: 사용할 수 있는 기존 재료 카드

카드 최소 표시:

```text
[1] 문제정의
창업도약_2025.docx · p.4
"외국인 방문객은 ..."
[원문에서 보기]
```

선택 단위:
- 모듈
- 문단
- 문장
- 표
- 표 행/셀

선택하면 자동으로 `[1] [2] [3]` 번호를 부여한다.

추가 입력:
- 직접 붙여넣기 → 출처 = `사용자 직접 입력`
- 자료 더 넣기 → 부족한 경우에만 노출

### 화면 4 — 자연어 지시 + 작성계획

사용자 예:

```text
1번은 그대로 쓰고,
2번 표는 유지,
3번 내용은 이번 공고의 지역사회 문제 해결 기준에 맞춰 보완.
```

AI는 즉시 초안을 쓰지 않고 **Composition Plan**을 먼저 보여 준다.

Composition Plan 최소 필드:

```text
target_section
selected_material_ids
user_instruction
ai_interpreted_actions
fill_rank: transcript | similar | generated
source_locators
applicable_l_rules
```

버튼:
- `[이대로 작성]`
- `[지시 수정]`

**승인 전 초안 생성 금지.**

### 화면 5 — 해당 파트 결과

한 번에 문서 전체를 쓰지 않는다.  
현재 선택한 대목차 1개만 작성한다.

작성 우선순위:

1. **전사** — 소스의 사실을 그대로
2. **유사** — 의미가 맞는 기존 내용을 공고/양식에 맞게 재배치
3. **생성** — 자료에 없으면 새로 작성하되 반드시 `생성` 표시

결과 표시는 최소 다음을 구분한다.

- 원문 사실
- 기존 자료 재구성
- 생성
- 사용자 직접 입력

출처:
- 사용자 표시: **파일명 + 페이지**
- 내부: 정확한 locator
- 근거가 없으면 `자료 내 확인 불가`

### 화면 6 — 다음 파트 / 부족자료 요청

파트 작성 직후 다음 행동만 제시한다.

예:

```text
현재 자료로 3개 파트 작성 가능

추가하면 좋아지는 정보
- 2025년 실제 매출 → 매출계획 보완
- 대표자 주요 경력 → 팀 역량 보완

[다음 파트 작성] [자료 추가]
```

모든 자료를 먼저 요구하지 않는다.

### 화면 7 — 최종 조립

모든 대목차 검토가 끝난 뒤에만 최종 양식에 조립한다.

흐름:

```text
파트별 승인 결과
→ 원본 양식 구조에 조립
→ LRule 검사
→ Finalizer
→ FINAL 또는 _DRAFT
→ 최종 HWPX 생성
```

최종 사용자 파일:
- 원본 양식과 같은 폴더
- `지원사업명_문서종류_MMDDHH vN.hwpx`
- 원본 덮어쓰기 금지
- 같은 이름이면 v2, v3 자동 증가
- 검수 실패 시 `_DRAFT`

---

## 3. 신규작성과 기존자료 활용은 이렇게 하나로 합친다

### 기존 계획서 있음

```text
공고 + 양식 + 기존 계획서
→ 기존 계획서에서 Fact/Evidence 추출
→ 양식 대목차와 매칭
→ 작성 가능한 파트 즉시 제시
→ 사용자 선택/지시/계획 승인
→ 파트 작성
```

### 기존 계획서 없음

```text
공고 + 양식
→ 양식 대목차/공고 요구사항 분석
→ 현재 입력만으로 가능한 파트 확인
→ 재료 없으면 생성 가능 표시
→ 사용자 선택/지시/계획 승인
→ 파트 작성
```

화면과 엔진은 동일하고, **기존 계획서 소스 유무만 다르다.**

---

## 4. 제품 파이프라인 — 기존 엔진 재사용 기준

| 제품 단계 | 재사용할 현재 자산 | 상태 |
|---|---|---|
| 파일 읽기 | `document_ingest`, `doc_text_extract` | 있음 |
| 공고 분석 | `announcement_analyzer` | 있음 |
| 양식 분석 | `form_analyzer`, TemplateProfile | 있음 |
| Fact/Evidence 계약 | `step2_output_contract.py` | 있음 |
| 섹션 매칭 | `section_matcher.py` | 있음 |
| 기존 자료 전사 | `cross_form_autofill`, `cross_form_fill` | 있음 |
| 본문 생성 | `bizplan_ai_writer`, `bizplan_autopilot` | 있음 |
| HWPX 직접 채움 | `hwpx_fill`, `hwp_fill_direct.py` | 있음 |
| 채움+검수 | `hwpx_submit.py` | 있음 |
| LRule | `LRuleEnforcer` | 있음 |
| 최종 판정 | `Finalizer` | 있음 |
| 최종 파일명/경로 | source-adjacent output helper (#184) | 있음 |
| 정확 locator 추출 | 형식별 일부/계약 존재 | **미완** |
| 모듈 카드 UI | 없음 | **미완** |
| [1][2][3] 선택재료 UI | 없음 | **미완** |
| Composition Plan 승인 게이트 | 사양만 존재 | **미완** |
| 파트 단위 생성/재생성 | 엔진은 있으나 제품 흐름 연결 없음 | **미완** |
| 파트별 최종 HWPX 조립 | 개별 엔진 존재, 단일 제품 흐름 미연결 | **미완** |

---

## 5. 현재 웹앱과 목표 흐름의 차이

현재 `app/auto_write/main.py`:

```text
템플릿 업로드
→ 템플릿 상세
→ 프로젝트 생성
→ 프로젝트 폼
→ generate()
→ 전체 output.docx
```

현재 문제:
- 첫 화면이 공고+양식+선택 기존계획서 구조가 아님
- 파일 역할 확정 단계 없음
- 모듈/원문 선택 없음
- [1][2][3] 재료 선택 없음
- Composition Plan 승인 없이 generate 가능
- 파트 단위가 아니라 전체 생성 중심
- 기본 산출 흐름이 아직 DOCX 중심 코드와 섞여 있음

따라서 **현재 FastAPI 화면을 그대로 제품으로 확장하지 않고, 기존 서비스는 재사용하되 P0 문서작업 흐름을 단일 진입으로 재배선**한다.

---

## 6. 실제 개발 순서

### P0-1. Intake
- 공고 / 양식 / 기존계획서 3역할 업로드
- 공고+양식 동일파일 허용
- 역할 사용자 확정
- 공고+양식 없으면 진행 차단

### P0-2. Analyze
- 공고 요구사항
- 양식 대목차
- 기존 자료 Fact/Evidence
- source_file + source_location/locator
- conflict 보존

### P0-3. Match
- 대목차별 WRITABLE / PARTIAL / BLOCKED
- 재사용 가능한 모듈 카드
- 부족자료는 blocking/non-blocking 분리

### P0-4. Compose
- 사용자가 재료 선택
- [1][2][3] 번호
- 자연어 지시
- Composition Plan 생성
- 사용자 승인 저장

### P0-5. Write one section
- 승인된 파트만 작성
- transcript → similar → generated
- generated 명시
- source_file + page 표시

### P0-6. Assemble
- 승인된 파트들을 원본 양식에 조립
- LRuleEnforcer
- Finalizer
- `FINAL/_DRAFT`
- source-adjacent HWPX

---

## 7. 제품 상태값

가짜 progress 금지. 실제 runtime 상태만 표시한다.

```text
WAITING_INPUT
ANALYZING
PLAN_READY
AWAITING_PLAN_APPROVAL
WRITING_SECTION
SECTION_READY
ASSEMBLING
FINALIZING
FAILED
```

UI에는 필요 이상으로 다 보이지 않아도 되지만, 내부 실행 상태와 화면 상태가 일치해야 한다.

---

## 8. 데이터 최소 계약

### Case

```json
{
  "case_id": "...",
  "announcement_files": [],
  "form_files": [],
  "prior_plan_files": [],
  "role_confirmed": true
}
```

### Material

```json
{
  "material_id": "...",
  "type": "fact|evidence|table|paragraph|user_input",
  "text": "...",
  "source_file": "...",
  "source_page": 4,
  "locator": {}
}
```

### SectionWork

```json
{
  "section_id": "...",
  "status": "WRITABLE|PARTIAL_WRITABLE|BLOCKED_REQUIRED_INFO|NO_USABLE_MATERIAL",
  "selected_material_ids": [],
  "user_instruction": "",
  "composition_plan": {},
  "plan_approved": false,
  "draft": {},
  "reviewed": false
}
```

---

## 9. 실사용 완료 기준

AW-005를 DONE으로 바꾸려면 최소 아래가 실제로 연결돼야 한다.

1. 공고+양식 업로드 없이는 시작 불가.
2. 기존 계획서 0개/1개/여러 개가 같은 화면에서 처리됨.
3. 기존 계획서가 있으면 재사용 가능한 파트가 먼저 보임.
4. 기존 계획서가 없어도 같은 흐름으로 진행됨.
5. 사용자에게 모듈 원문 + 파일명 + 페이지가 보임.
6. 선택 재료에 [1][2][3] 번호가 붙음.
7. 자연어 지시 후 Composition Plan이 먼저 생성됨.
8. 사용자 승인 전 파트 초안이 생성되지 않음.
9. 승인한 파트만 작성됨.
10. 생성한 문장은 `생성` 표시.
11. 사실에는 실제 source/locator가 연결됨.
12. 전체 문서는 마지막에만 조립됨.
13. LRuleEnforcer + Finalizer를 통과.
14. 최종 HWPX가 원본 양식 폴더에 생성됨.
15. 원본 파일은 수정되지 않음.

---

## 10. 지금 당장 하지 않을 것

- 품질점수 대시보드
- 제출가능/불가능 자동판정 UI
- CRM/영업/결제
- 시스템 아키텍처 시각화 P2
- L Rule 웹 수정 P1
- 웹 전용 DOCX writer 신규 개발
- 기존 엔진 복제
- 문서 전체 일괄 AI 작성
- 출처 없는 사실 생성
- 페이지 번호만 보여 주고 원문을 못 찾는 UX

---

## 11. 이번 브랜치의 역할

이 브랜치는 **제품 흐름을 실사용 기준으로 하나로 정리하는 AW-005 작업 브랜치**다.

이번 체크포인트에서 확정한 것:
- 제품 진입점 1개
- 첫 화면 3역할
- 기존 계획서 유무 = 같은 흐름
- 대목차 단위 작성
- 작성 가능한 파트 우선
- 부족자료 후요청
- [1][2][3] 재료 + 자연어
- Composition Plan 승인 게이트
- 전사 → 유사 → 생성
- 최종 HWPX 원본 폴더 저장
- 기존 엔진 재사용

아직 DONE이 아닌 것:
- 위 흐름을 FastAPI 실제 화면/API/runtime에 연결
- 형식별 locator 완성
- 파트별 생성/조립 E2E
- P0 전체 사용자 E2E
