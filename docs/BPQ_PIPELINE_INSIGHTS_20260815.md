# BPQ 파이프라인 인사이트 — 2026-08-15

> 출처: 「배달앱 마케팅 전략 작성 도구」 분석. **프롬프트 문구가 아니라 상태 있는 단계형 작성 파이프라인**을 가져온다.
> 적용 대상: `TASK.md` T-20260814-02. **기존 BPQ-00~13을 갈아엎지 않고 정밀화.**
> 상태: 지식 저장. 구현·TASK 본문 반영은 다음 명령 대기.

가져갈 흐름:

`Facts → 정제된 Context → 단계별 Draft → Self-check → Deterministic QA → Human Approval → Dependency 재검증 → Final`

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
