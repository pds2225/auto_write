# BPQ 파이프라인 인사이트 — 2026-08-15

> 출처: (1) 배달앱 마케팅 전략 작성 도구 (2) 상권분석.html. **기능 복제가 아니라 단계별 상태 머신.**
> 적용 대상: `TASK.md` T-20260814-02 구현요건 구체화. **신규 Epic 금지. BPQ-00~13 정밀화.**
> 상태: 지식 저장. 구현·TASK 본문 반영은 다음 명령 대기.

가져갈 흐름:

`LLM → 구조화된 중간 산출물 → 검증 → 다음 중간 산출물 → 렌더링 → LRule/Finalizer`

한 문장: 각 단계가 검증 가능한 구조화 데이터를 만들고, 그 결과만 다음 단계가 소비한다. `LLM → 최종 DOCX` 금지.

가져가면 안 됨: HTML에 박힌 API 키, 저장 JSON에 비밀값 포함. 비밀은 `.env`만.

---

## P0 (다음 명세 반영 우선)

1. **SectionContextPack** — `CompanyMaster + ProgramSpec + QualityProfile + DocumentPlan`을 매 섹션 LLM에 통째로 넣지 않는다. `SectionContextBuilder`가 섹션별 팩만 공급 (평가항목, 분량, confirmed facts, 시장/Pain, 숫자, 금지 facts, conflicts, required citations, quality patterns).
2. **FactState** — 공란도 데이터. 문자열 빈칸(`""`)으로 합치지 않는다.
   `CONFIRMED / INFERRED / UNKNOWN / CONFLICT / NOT_APPLICABLE / PLAN` (+ 0=사실, 없음=확인된 부재, 미입력, 확인필요). Actual/Plan 혼합은 구조적으로 차단.
3. **Source precedence (코드화)** — 예: 기업 공식자료 > 대표 직접입력 > 증빙문서 > 기존 사업계획서 > 외부자료 > AI 추론. 충돌 시 LLM이 고르지 않고 Conflict Queue.
4. **이중 검증** — Writer Self-check → 기존 LRule / PSST / 수치 / 출처 결정론 QA.
5. **STALE dependency** — Fact 변경 → dependency graph → 영향 섹션 STALE → 재생성/승인 전 FINAL 금지. 구결과를 최신처럼 쓰지 않음.

## P1

6. **Hard vs Soft 분리** — LRule=절대규칙/검사. QualityProfile=작성전략/문체(사용자 수정 가능). PromptTemplate=실행 템플릿이며 LRule 정본이 되면 안 됨. 순서: LRule → QualityProfile → PromptTemplate.
7. **구조화 출력 계약** — 자유문장 바로 DOCX 금지. `SectionDraft schema → validator → renderer`. 불일치 시 repair 후 재검증.
8. **Human Approval 상태** — 섹션 `GENERATED → REVIEWED → APPROVED → LOCKED`. 사람 수정도 provenance. 수치/팩트 QA 재실행.
9. **Replay** — input hash + source/profile/model 버전 + 중간산출 + QA + artifact hash.

## P2

10. **Golden을 단계별 fixture로** — MarketGate expected: CompanyMaster / ProgramSpec / DocumentPlan / section context / Draft / QA. 최종 DOCX만 비교 금지.

## 기존 BPQ에 넣을 위치 (신시스템 금지)

| Workstream | 추가 |
|---|---|
| BPQ-02 | FactState, source precedence, Actual/Plan/Unknown/Conflict |
| BPQ-03 | SectionContextPack, dependency graph, STALE 전파 |
| BPQ-07 | section input contract, required/forbidden facts, evidence, QualityProfile, prompt template version |
| BPQ-08 | 단계별 expected (문서만 비교 금지) |
| BPQ-12 | Writer self-check → schema → factual/numeric → LRule → layout → Finalizer |
| BPQ-13 | upstream fact 수정 → STALE → 재생성 → 수치 consistency |

서술 생성에도 cross-form과 같은 날조0: 오매칭은 빈칸보다 나쁨, high confidence만 자동.

## 금지 (이 자료에서)

- 첨부 HTML의 Anthropic/OpenAI 키를 코드/JSON에 복사
- 프로젝트 저장물에 API 키 포함
- 프롬프트 편집 UI를 LRule 정본으로 승격
- AIMY 사실 전이, 출처 없는 숫자, Actual/Plan 혼합, LLM의 충돌 임의 선택

---

## 상권분석.html에서 추가 (2026-08-15 2차)

### Stage 누적 (S0–S8)

S0 프로젝트 → S1 공고/양식(`ProgramSpec`/`FormSpec`) → S2 사실추출(`CompanyMaster`/`FactGraph`) → S3 사실감사(Conflict/Missing/Actual·Plan) → S4 작성전략(평가항목↔Claim↔Evidence↔분량) → S5 `DocumentPlan` → S6 섹션 Structured Draft → S7 원본 양식 렌더 → S8 LRule+Hash+Finalizer.

각 AI 호출은 자유 장문이 아니라 **JSON Schema에 맞춘 StageResult**. 다음 단계는 그 객체만 소비.

### priorContext는 객체를 참조

텍스트 dump가 아니라 claim 객체를 여러 단계에서 재사용. Gap: `file_name + page` + 실존 검증이 TASK에 있으나 모델/런타임 provenance가 약함.

```json
{
  "claim_id": "CLM-0231",
  "field": "2027년 예상매출",
  "value": 500000000,
  "unit": "KRW",
  "fact_type": "PLAN",
  "as_of": "2027",
  "source_file": "사업추진계획.pdf",
  "source_page": 12,
  "confidence": 1.0,
  "verification": "VERIFIED"
}
```

### Data Audit은 작성 전 독립 단계

경계(사업/법인/제품) · 업종 · 기간 · 단위 · 출처(파일+페이지) · MISSING · CONFLICT · Claim 사용가능여부. 같은 연도 매출 2.8억 vs 3.1억은 LLM이 고르지 않고 둘 다 CONFLICT, 5억은 PLAN, 본문 사용 금지.

### 숫자는 deterministic engine

코드가 계산(TAM/SAM/SOM, CAGR, YoY, 수량×단가, 인건비/사업비 합, 정부+자부담, 연차 자금 총계, KPI, 퍼널, BEP, 기간). LLM은 계산하지 않고 해석·심사위원 문장만.

### Review Queue는 필드 단위

`needs_confirm: ["2025년 매출 확인"]` 대신 `field_id`, `status=MISSING`, `required_by`, `severity=BLOCKING`, `action`. 확인필요는 정상 상태. 점수/문장으로 메우지 않음.

### Prompt ≠ 프로젝트 데이터

CompanyMaster ≠ ProgramSpec ≠ QualityProfile ≠ PromptTemplate ≠ DocumentPlan. Prompt는 `profile_id` + `version` + `prompt_hash`로 재현.

### AW-004 모니터 상태 (참고 UX)

`WAITING / READY / RUNNING / PASS / REVIEW_REQUIRED / BLOCKED / FAILED / DRAFT / FINAL`.  
금지: 값 하나 있으면 완료. `content exists ≠ valid`, `generated ≠ verified`, `verified ≠ finalizable`. runtime 결과만 완료.

### 가져오면 안 됨 (상권분석 HTML)

- 브라우저 API 키 / LocalStorage 정본
- `{...}` regex JSON 복구 → Structured Output / schema / Pydantic
- “점수가 낮으니 다시 써” 루프. `bizplan_autopilot`은 부족한 Fact/Claim/Evidence의 **해당 Stage만 재실행**

### T-20260814-02에 넣을 구현요건 키워드

`Stage Pipeline` · `StageResult` · `Data Audit` · `Deterministic Calculation` · `Claim Provenance` · `Stage Retry`

AW-005 흐름(새문서→양식→기존자료→작성→출처→LRule→FINAL/DRAFT)과 맞음. DomainRouter / LRule / Finalizer는 KEEP.

### 우선순위 (2차)

P0: StageResult 공통 모델, FactGraph, Claim provenance(파일+페이지), Audit, 결정론 숫자, DocumentPlan→section generator  
P1: workflow monitor, Stage 재실행, QualityProfile/Prompt 버전, Review Queue  
P2: checkpoint export/import, Golden fixture, stage debug view

---

## 구현 스냅샷 (2026-08-15, `origin/main` `9cffb24`)

> 조사 본문은 `9cffb24`(#137) 시점 그대로다. 그 이후 `origin/main`은 `7a2dc5a`(#140 git-sync push 검증). #140은 `git_sync_service.py`만 추가했고 아래 DOCX/LRule 표는 그대로다.

작업 시작 전 고정 절차(이번 명령으로 고정): `git fetch` 기본 브랜치 → `TASK.md` 읽기 → 현재 구현 조사 → 그다음 작업. 제품 코드·T-20260814-02 본문 반영은 **다음 명령 대기**.

### Git / TASK LIST

- Remote: `https://github.com/pds2225/auto_write` · BASE 실제값: **`main`** (`TASK.md` §1은 `main`, §3 판정 문단에 구버전 `master` 잔존. 원격 `master` 없음)
- HEAD: `9cffb24` `prep: cherry-pick overnight A–H lanes onto current main (#137)`
- ahead/behind vs `origin/main`: 이 스냅샷 작성 시점 로컬 `main` = 원격과 동기
- LIST (스냅샷 당시): `[ ]` AW-001~008 · `[~]` T-20260814-01 · `[ ]` T-20260814-02 (명세만) · `[x]` T-20260814-03 (체리픽 준비; #137은 그 이후 머지됨)
- 이후 LIST: `[x]` T-20260815-01 (잔여 체리픽+#140). 본 문서는 지식 저장. T-20260814-02 본문 미변경

### 정본 경로 드리프트 (BPQ-00이 다시 고정해야 함)

T-20260814-02 KEEP는 `app/auto_write/services/*`를 정본으로 적는다. **2026-08-15 HEAD에서는 DOCX 엔진 상당수가 `core.docx.services`에 실구현**이고 `auto_write.services`는 3줄 re-export다. import는 계속 `from auto_write.services…`가 동작한다. **병렬 `*V2` 금지. 세 벌을 동시에 수정 금지.**

| 역할 | 실구현 | `auto_write.services` | `bizplan.services` |
|---|---|---|---|
| DomainRouter | `app/auto_write/domains/domain_router.py` | — | — |
| LRuleEnforcer | `app/auto_write/services/lrule_enforcer.py` | 실파일 | — |
| Finalizer | `app/auto_write/services/finalizer.py` | 실파일 | — |
| company_extract | `app/auto_write/services/company_extract.py` (299줄) | 실파일 | 없음 |
| announcement_analyzer | `app/auto_write/services/announcement_analyzer.py` | 실파일 | 얇은 re-export |
| form_analyzer | `app/auto_write/services/form_analyzer.py` | 실파일 | 얇은 re-export |
| plan_builder | `app/auto_write/services/plan_builder.py` (64줄) | 실파일 | 얇은 re-export |
| project_service / provenance | `app/auto_write/services/project_service.py` | 실파일 | — |
| document_ingest | `app/auto_write/document_ingest.py` (664줄) | 실파일 | `core/docx/document_ingest.py` **바이트 동일 복제** |
| autopilot_pipeline | `app/core/docx/services/autopilot_pipeline.py` (571줄, LRule 4.6 포함) | 3줄 re-export | 얇은 re-export |
| bizplan_ai_writer | `app/core/docx/services/bizplan_ai_writer.py` | 3줄 re-export | 얇은 re-export |
| bizplan_autopilot | `app/core/docx/services/bizplan_autopilot.py` | 3줄 re-export | 얇은 re-export |
| quality_rules (서식 프리셋) | `app/core/docx/services/quality_rules.py` | 3줄 re-export | **전문 복제** (core와 동일 본문) |
| cross_form_autofill | `app/core/docx/services/cross_form_autofill.py` (2463줄) | 3줄 re-export | **전문 복제** (import만 `auto_write.services.*`) |
| usage_acceptance | `app/core/docx/services/usage_acceptance.py` | 3줄 re-export | — |
| evaluation_service | `app/core/docx/services/evaluation_service.py` | 3줄 re-export | 얇은 re-export |
| render_service | `app/core/docx/services/render_service.py` | 3줄 re-export | **전문 복제** (import만 다름) |
| docx_ops / submittable_filler | `app/core/docx/services/` | 3줄 re-export | — |
| psst_check / psst_fill | `app/core/docx/services/` | 3줄 re-export | psst_fill는 **전문 복제**(import만 다름) |

실행 import 권장: `from auto_write.services.<name>` (호환). 파일 수정 시 **실구현 1곳만**. AW-007이 복제본 정리 owner.

### KEEP 모듈 — 구현됨 vs 갭 (인사이트 대비)

| 인사이트 / BPQ 개념 | 현재 | 갭 |
|---|---|---|
| DomainRouter | 구현. `resolve`/`resolve_from_docx`. explicit > document_type > classifier | KEEP |
| LRuleEnforcer | 구현. 151 canonical (`lessons_coverage.json` mechanized 44 / gap 21 / judgment 86). `guards` dict 없으면 mechanized → **UNVERIFIABLE** | 가드 callable을 autopilot이 넘기지 않음 → 거의 항상 FINAL 불가 |
| Finalizer | 구현. FAIL/REVIEW/UNVERIFIABLE → `_DRAFT`. artifact SHA256 | KEEP. 내용 QA 아님 |
| Autopilot 4.6 | **#137 이후 배선됨**. `classify_domain` → `enforce_lrules` → `finalize_artifact`. 예외는 `finalizer_blocked_reason=lrule_finalizer_error:…` (침묵 성공 금지). usage_acceptance와 **이중 게이트** | AW-001 경로 KEEP. 거의 `_DRAFT`는 의도(fail-closed) |
| CompanyMaster | 식별 12필드만 (기업명·대표자·사업자번호·설립일·업종·주소·연락처·이메일·홈페이지·직원수·자본금·팩스). `confidence` high/medium/conflict. `confirmed=false`. provenance=`file`+`raw_label`. 숫자값 보존 | **FactGraph 없음**: fact_id, unit, as_of, actual/plan/estimate, page, FactState. 아이템·KPI·IP·매출 없음 |
| Conflict | 파일 간 식별값 `_norm_value` 불일치 → Conflict Queue. LLM 비해소 | KPI/날짜/Actual·Plan 충돌 없음. source precedence 코드 없음 |
| ProgramSpec | `AnnouncementReport`: criteria, deadline, documents, funding 휴리스틱/AI | 단일 ProgramSpec JSON 없음. 글자/페이지 한도·삭제금지·섹션 중요도 미구조화 |
| FormSpec | `FormReport`: 섹션/표/이미지슬롯/필수칸/PSST 유무, `classify_field_kind` fact vs narrative | FormSpec(자수·삭제금지·섹션 가중) 없음 |
| QualityProfile (작성) | **미구현**. `quality_rules.PRESETS`는 색/pt/공란 **서식** | AIMY 문체 프로필 JSON 없음. PromptTemplate 버전/해시 없음 |
| DocumentPlan / Content planner | `plan_builder.build_fill_plan` = identity/overview + 외부 fill_plan.json 좌표 | 평가전략·Claim·Evidence·분량 계획 없음 |
| Writer | `bizplan_ai_writer`: PSST 약점 영역에 LLM이 **문단 리스트를 바로 DOCX에 삽입**. `[확인필요]`/`[산출근거]` 문자열. `needs_confirm: list[str]` | StageResult schema 없음. SectionContextPack 없음. field_id Review Queue 없음 |
| bizplan_autopilot | `max_loops=3`, `target_ratio=0.85`. **점수 낮으면 writer+autopilot 전체 재실행** | 인사이트: **실패 Stage만 retry**. 점수→전문 재작성 금지 |
| cross-form 전사 | 구현(날조0, high만 자동, 원본 미수정) | **서술 재작성 경로 없음** (별 파일로 둘 것) |
| Claim provenance | `answers_provenance.json` source enum: user/docx_seed/psst/ai/fallback/needs_confirm | file+page+as_of+actual/plan 없음. typed claim 객체 없음 |
| QA 서식/제출 | usage_acceptance + doc_quality_score + self_diagnose | 내용 KPI 일관성 약함 |
| `check_unverified_claims` | 옵트인 warn, 게이트 비영향 | 결정론 숫자 엔진 없음 (TAM/SAM/SOM, 합계, BEP) |
| `check_recruit_date_conflict` | usage_acceptance에 존재 | AIMY형 표지↔본문 KPI 동일소스 미구현 |
| StageResult / STALE / SectionContextPack | **코드 0**. `TASK.md` 스펙 표에만 존재 | 신규는 기존 모듈 확장. `FactGraphService` 등 병렬 클래스명 금지 |
| E2E | `app/tests/test_e2e_domain_pipeline.py` **15 tests** (BP+CA, SHA256, empty, force_draft, cross-domain N/A) | Golden stage fixture 없음 |
| AIMY 벤치마크 파일 | 이 클라우드 워크스페이스에 `results/aimy_form_rules/` **없음**. MarketGate 레포 예시 `tools/injector/examples/content_marketgate.json` **있음**. 원본 HWP는 OneDrive(로컬). txt 역추정 요청본은 명세 시점부터 **없음** | BPQ-01은 skip-if-missing. 가짜 corpus 금지 |
| `templates/` | 저장소에 디렉터리 없음 | 명세와 동일 |

### 현재 실제 작성 경로 (목표 S0–S8과 불일치)

```text
초안 DOCX
 → bizplan_ai_writer (PSST 약점 영역 문단 직접 삽입)
 → autopilot_pipeline (백업·서식·PSST 가이드·점수·usage_acceptance)
 → LRule+Finalizer (#137) → 대개 _DRAFT
루프: 공고 채점 비율 < 0.85 이면 위 전체 재실행 (max 3)
```

목표: `S0…S8 StageResult` → 원본 양식 렌더 → LRule+Hash+Finalizer. **지금 코드는 LLM→DOCX 루프.**

### Autopilot LRule 실측 의미

`run_autopilot`은 `enforce_lrules(..., guards=없음)`을 호출한다. mechanized인데 guard callable이 없으면 UNVERIFIABLE → `can_finalize=False` → Finalizer `_DRAFT`. 서식 수용검사가 통과해도 파일명은 `_DRAFT`. 이는 AW-001 fail-closed이며, BPQ 내용 파이프라인이 끝난 것이 아니다.

### 다음 명령이 오기 전까지 하지 않음

- T-20260814-02 DETAILS 키워드 삽입 (Stage Pipeline / StageResult / Data Audit / Deterministic Calculation / Claim Provenance / Stage Retry)
- BPQ-00 제품 코드 / 새 Epic / `*V2` 클래스
- leftover `task/*` 재머지, 비밀 커밋
- AIMY 숫자 전이

다음 명령 해석 힌트:

- 「TASK에 반영해」→ 기존 BPQ-02/03/07/08/12/13에만 키워드 추가. AW-001~008 원문 유지
- 「구현 시작해」→ `origin/main` 재fetch 후 BPQ-00 감사만. 정본=실구현 1곳. `py -3.11 -m pytest`
