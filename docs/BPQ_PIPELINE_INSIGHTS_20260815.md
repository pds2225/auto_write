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
