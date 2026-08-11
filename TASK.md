# TASK — AutoWrite 병렬 무인개발

대상: `pds2225/auto_write`
기준 브랜치: `master`

## 목표

오늘 밤 사용자 승인 없이 가능한 작업을 **병렬로 최대한 진행**한다.

이번 TASK는 "작업 1개만 하고 멈추는" 방식이 아니다.
서로 독립적인 작업은 동시에 진행하고, 같은 파일/같은 실행경로를 건드려 충돌 가능성이 있는 작업만 순차 처리한다.

사용자는 다음 날 한 번에 결과를 검수한다.

핵심 목표는 다음이다.

1. AutoWrite 실제 production 경로에 DomainRouter → DomainPipeline → LRuleEnforcer → Hash 검증 → Finalizer를 강제 배선
2. business_plan / consultant_application 양 도메인의 실제 E2E 검증
3. LRule runtime enforcement와 FINAL 우회 차단 강화
4. workspace/results domain routing 실제 사용 확인 및 보완
5. 루트 폴더와 문서/스크립트 구조 정리
6. 중복/placeholder/MIXED 코드 정리
7. 테스트·architecture guard·negative regression 확대
8. 현재 코드에서 독립적으로 발견되는 명확한 P0/P1 결함까지 수정

단, 새로운 제품기능을 임의로 발명하지 않는다.

---

## 0. 시작 전 안전 점검

반드시 먼저 실행한다.

```bash
git fetch --all --prune
git status
git branch --show-current
git rev-parse HEAD
git rev-parse origin/master
git log --oneline -15
git worktree list
git diff
git diff --cached
```

원칙:

- 현재 `master`가 이 TASK 작성 이후 변경됐으면 최신 코드를 기준으로 다시 판단한다.
- 기존 미커밋 사용자 변경을 덮어쓰지 않는다.
- 다른 세션/worktree가 같은 파일을 수정 중이면 동일 파일 병렬수정 금지.
- `git reset --hard`, `git clean -fd`, force push 금지.
- `git add -A` 금지. 이번 작업 파일만 명시적으로 stage.
- 사용자 데이터/실사용 산출물/secret 삭제·변경 금지.
- 운영 배포 및 외부 유료 API 실제 호출 금지.

이미 구현된 작업은 다시 만들지 않는다.
"DONE" 문서보다 실제 runtime caller와 테스트를 우선한다.

---

## 1. 병렬 실행 원칙

작업 시작 후 전체 backlog를 아래 트랙으로 나눈다.

가능하면 각 트랙을 별도 sub-agent / worktree / branch로 수행한다.
도구가 병렬 agent를 지원하지 않으면 한 세션 안에서 독립 파일군별로 번갈아 진행하되, 한 트랙이 막혀도 다른 트랙을 계속한다.

### 병렬 가능 조건

- 수정 파일군이 겹치지 않음
- 동일 public API를 동시에 변경하지 않음
- 동일 migration/entrypoint를 동시에 수정하지 않음
- 서로 선행 결과를 기다릴 필요가 없음

### 직렬 처리 조건

- 같은 파일 수정
- 같은 runtime entrypoint 수정
- schema/API contract 선행 필요
- 한 작업의 결과가 다른 작업의 입력임

병렬 작업을 이유로 동일 기능을 중복 구현하지 않는다.

---

# TRACK A — Production Runtime Wiring (최우선 P0)

실제 production entrypoint를 전수 검색한다.

검색 대상:

- DomainRouter / resolve_domain
- BusinessPlanPipeline
- ConsultantApplicationPipeline
- LRuleEnforcer
- Finalizer / finalize_artifact
- submission_orchestrator
- hwpx_submit
- autopilot_pipeline / bizplan_autopilot
- project_service
- resume_fill
- cross_form 관련 실행경로
- hwp/hwpx fill 및 submit CLI
- `_DRAFT`, `FINAL`, `submittable=True`, `force_draft_name`, rename/copy 경로

목표 실제 흐름:

```text
INPUT
→ DomainRouter
→ DomainPipeline
→ 기존 안정 CORE/shared services
→ format-specific acceptance
→ LRuleEnforcer
→ artifact SHA256
→ registry SHA256
→ Finalizer
→ FINAL 또는 _DRAFT
```

정의 파일/테스트에만 존재하고 production caller가 없으면 미완료다.

### 완료조건

- business_plan 주요 production entrypoint 실제 배선
- consultant_application 주요 production entrypoint 실제 배선
- ambiguous domain은 자동 FINAL 금지
- 기존 CLI/API compatibility 유지

---

# TRACK B — LRule Runtime Enforcement / Finalizer (P0)

현재 canonical LRule 전체를 실제 runtime report에서 정확히 1회 판정한다.

허용 상태:

- PASS
- FAIL
- N/A
- REVIEW_REQUIRED
- UNVERIFIABLE
- USER_OVERRIDE

불변조건:

- PASS → evidence 필수
- N/A → reason 필수
- missing rule > 0 → FINAL 금지
- duplicate rule > 0 → FINAL 금지
- FAIL > 0 → FINAL 금지
- REVIEW_REQUIRED > 0 → FINAL 금지
- UNVERIFIABLE > 0 → FINAL 금지
- USER_OVERRIDE는 실제 사용자 승인 evidence 없이는 생성 금지

### mechanized

`guard_ref` 문자열이나 테스트 존재만으로 PASS 금지.
실제 production callable을 실행하고 evidence를 남긴다.

- 구현된 guard가 있으면 runtime wiring
- 테스트 안에만 있는 deterministic 검사면 reusable guard 추출 검토
- 실제 자동검사 불가면 UNVERIFIABLE/REVIEW_REQUIRED 유지

### Hash

- 검사 시 artifact SHA256 저장
- Finalizer 직전 artifact 재해시
- mismatch → FINAL 금지
- registry SHA256도 Finalizer 직전 현재값과 재비교
- mismatch → FINAL 금지

현재 TODO/pass가 남아 있으면 제거한다.

### Report

실제 실행마다 `lrule_report.json` 저장.
저장 실패도 fail-closed.

---

# TRACK C — FINAL 우회경로 감사 및 차단 (P0)

저장소 전체 검색:

- `force_draft_name`
- `_DRAFT`
- `FINAL`
- `submittable=True`
- `final_path`
- rename/replace
- shutil.copy/copy2/copyfile
- 제출가능/제출용 상태 반환

기존 format-specific acceptance는 유지하되, 최종 제출 가능 판정은 전역 Finalizer로 수렴한다.

특히 우선 확인:

- submission_orchestrator.py
- hwpx_submit.py
- resume/application 결과 생성 경로
- business plan output 경로

### Negative tests

최소:

1. LRule 검사 후 artifact 수정 → FINAL 차단
2. report 이후 registry 변경 → FINAL 차단
3. mechanized guard missing → UNVERIFIABLE → FINAL 차단
4. judgment evidence missing → REVIEW_REQUIRED → FINAL 차단
5. rule missing/duplicate → FINAL 차단
6. report save 실패 → FINAL 차단
7. ambiguous domain → 자동 FINAL 금지
8. legacy direct final path → 차단

---

# TRACK D — Domain / Workspace / Results Wiring (P0/P1)

현재 domain 개념과 document_type을 분리 유지한다.

최소 domain:

- business_plan
- consultant_application
- other

신규 실행은 실제로 다음 경로를 사용해야 한다.

```text
workspace/business_plan/
workspace/consultant_application/
results/business_plan/
results/consultant_application/
```

기존 프로젝트는 legacy fallback으로 읽을 수 있어야 한다.

함수만 있고 caller가 없으면 실제 runtime wiring 한다.

테스트:

- 신규 BP project path
- 신규 CA project path
- legacy BP read
- legacy CA read

---

# TRACK E — Business Plan E2E (P0)

실사용 개인정보 없이 fixture/synthetic data 사용.

production과 동일한 orchestrator를 최대한 사용한다.

검증 흐름:

```text
input
→ DomainRouter
→ business_plan
→ BusinessPlanPipeline
→ generation/quality path
→ LRuleEnforcer
→ report
→ artifact hash
→ registry hash
→ Finalizer
```

검증:

- consultant_application 전용 규칙 N/A + reason
- applicable mechanized silent PASS 0
- blockers 존재 시 _DRAFT
- controlled pass fixture면 FINAL
- report 실제 존재
- report hash와 artifact 일치

mock-only E2E 금지.

---

# TRACK F — Consultant Application E2E (P0)

synthetic applicant/profile fixture 사용.

검증 흐름:

```text
input
→ DomainRouter
→ consultant_application
→ ConsultantApplicationPipeline
→ autofill/resume/cross-form
→ acceptance
→ LRuleEnforcer
→ report/hash
→ Finalizer
```

검증:

- business_plan 전용 규칙 N/A + reason
- 사실 날조 없음
- 미확정 체크박스 임의 선택 없음
- cross-form consistency
- blocker 시 DRAFT
- controlled pass fixture면 FINAL

---

# TRACK G — 루트 폴더 정리 (P1, 다른 트랙과 파일 충돌 없을 때 병렬)

루트의 모든 파일/1단계 디렉터리를 분류한다.

- KEEP_ROOT
- SOURCE
- DOC
- SCRIPT
- TEST
- CONFIG
- DATA
- GENERATED
- ARCHIVE
- DUPLICATE
- UNKNOWN

파일명만 보고 이동하지 않는다.
이동 직전 repo 전체 참조 검색.

우선 LOW RISK만 실제 이동:

- 참조 없는 일반 문서
- 명확한 historical/archive 자료
- 명확한 개발용 스크립트
- 추적 부적절한 generated/temp

문서/스크립트 이동 시 README/CLAUDE/AGENTS/.claude/workflow/test path 모두 갱신.

루트가 계약인 파일은 유지.

루트정리 때문에 business_plan/consultant_application/CORE/LRule를 다시 설계하지 않는다.

---

# TRACK H — MIXED / 중복 / Placeholder 정리 (P1)

전수 검색:

- `구현 예정`
- TODO-only
- pass-only
- 빈 facade
- 1줄 placeholder
- duplicate implementation
- legacy wrapper 내부 복제
- *_old / *_v2 / copy / backup / 날짜 접미사

각 항목:

A. 실제 필요 → canonical implementation에 연결
B. 불필요 → 안전하게 제거
C. compatibility 목적 → 명확한 wrapper/re-export 유지
D. 판단 불가 → UNKNOWN/보류

dual source of truth 금지.

특히 cross_form/autofill/source-pool 관련 MIXED 책임을 재확인하되 억지 이동 금지.

---

# TRACK I — Architecture / Regression Guard 강화 (P1)

최소 불변조건:

1. business_plan → consultant_application 내부 직접 import 금지
2. consultant_application → business_plan 내부 직접 import 금지
3. core/shared → domains 직접 import 금지
4. domains → core/shared 허용
5. wrapper 내부 구현 복제 금지
6. runtime entrypoint의 DomainRouter 우회 방지
7. FINAL 우회 방지
8. placeholder-only domain module 방지
9. legacy workspace compatibility

가능하면 AST 기반 import 검사 사용.

---

# TRACK J — Test / CI / 환경 실패 정리 (P1)

기존 Python 3.11 관련 실패가 남아 있으면 다시 실측.

```bash
py -0p
py --list
python --version
where python
```

정확한 실패 테스트와 원인 분리:

A. 신규 regression → 수정
B. 기존 baseline → 기록
C. 환경 문제 → 증거 기록
D. 잘못된 hardcoded interpreter → repo 지원범위 안에서 portability 수정 검토

skip으로 숨기지 않는다.

가능한 전체 `app/tests/` regression 실행.

---

# TRACK K — LRule Gap 추가 기계화 (P2, P0 완료 후 남는 자원으로 병렬)

HIGH impact + LOW/MEDIUM effort만 선택.

한 규칙은 반드시 아래 4개가 한 세트로 완료될 때만 mechanized 처리:

1. guard
2. regression test
3. coverage update
4. runtime wiring

category만 변경 금지.

P0 미완료인데 gap 기계화에 과도한 시간 사용 금지.

---

## 2. 병렬 작업 충돌 관리

병렬 branch/worktree를 쓸 경우:

- 트랙별 branch 분리
- 같은 파일을 두 트랙에서 동시에 수정 금지
- 공통 파일 수정이 필요한 경우 한 트랙을 owner로 지정
- integration branch에서 하나씩 검증 후 병합
- merge conflict를 `ours/theirs`로 기계적으로 해결 금지
- 양쪽 의도를 실제 코드로 합친 뒤 테스트

추천 ownership 예:

- runtime entrypoint: TRACK A owner
- LRule/Finalizer: TRACK B owner
- bypass tests: TRACK C owner
- config/workspace: TRACK D owner
- BP tests: TRACK E owner
- CA tests: TRACK F owner
- docs/root: TRACK G owner

---

## 3. 사용자에게 중간 질문 금지

다음 질문 금지:

- 계속할까요?
- 이걸 옮길까요?
- PR 만들까요?
- 병합할까요?
- 어느 걸 먼저 할까요?
- 이 구조가 맞나요?

기존 요구사항과 코드 근거로 판단 가능하면 스스로 진행.

한 트랙이 BLOCKED면 그 트랙만 기록하고 다른 독립 트랙을 계속한다.

단 다음은 임의 처리 금지:

- 개인정보
- 실제 서명
- 실제 체크박스 선택
- 유료 API 호출
- secret
- 운영 배포
- destructive migration

---

## 4. 테스트 전략

각 트랙 작은 변경마다 관련 테스트.

최종 최소:

- test_lessons_coverage
- test_lesson_registry_integrity
- test_lrule_domain_gate
- test_lrule_enforcer
- test_finalizer
- test_architecture_boundaries
- submission_orchestrator
- hwpx_submit / hwpx_fill / hwpx_acceptance
- cross_form
- resume/application
- business plan
- workspace routing
- BP E2E
- CA E2E
- negative finalization tests
- 가능한 `app/tests/` 전체

fake pass 금지:

- assert True
- mock이 production 핵심 전체 우회
- exception swallow
- subprocess return code 무시
- skip 남발

---

## 5. Git / PR 운영

병렬 작업은 트랙별 작은 commit 또는 branch로 관리.

의미 단위 commit 예:

- `fix(runtime): wire production entrypoints through domain router`
- `feat(lrules): enforce runtime guards and persist reports`
- `fix(finalizer): verify artifact and registry freshness`
- `test(e2e): cover business-plan runtime path`
- `test(e2e): cover consultant-application runtime path`
- `chore(root): organize repository root`
- `test(architecture): block finalization bypasses`

각 commit 전 관련 테스트.

PR은 독립 작업별로 여러 개 생성 가능하다.
사용자 승인 기다리지 않는다.

자동 병합은 다음 조건을 모두 만족할 때만:

- conflict 없음
- unrelated diff 없음
- 신규 regression 0
- 해당 트랙 필수 테스트 PASS
- destructive change 없음
- 사용자 데이터 영향 없음

조건 미충족 PR은 OPEN으로 남기고 다음 독립 작업 진행.

---

## 6. 내일 검수하기 쉽게 결과 남기기

최종 보고는 한눈에 볼 수 있어야 한다.

```text
[RESULT]
PASS / PARTIAL / BLOCKED

[MASTER]
start HEAD:
end HEAD:

[PARALLEL TRACKS]
A Runtime wiring: PASS/PARTIAL/BLOCKED
B LRule/Finalizer: ...
C Final bypass: ...
D Domain/workspace: ...
E BP E2E: ...
F CA E2E: ...
G Root cleanup: ...
H Mixed/duplicate: ...
I Architecture: ...
J Test/CI: ...
K Gap mechanization: ...

[PRODUCTION WIRING]
실제 연결한 entrypoint 목록

[LRULE]
canonical total:
runtime evaluated:
mechanized actually executed:
gap remaining:
judgment remaining:

[FINAL BYPASS]
found:
fixed:
remaining:

[E2E]
business_plan:
consultant_application:

[ROOT CLEANUP]
moved:
kept:
archived:
unknown:

[TEST]
passed:
failed:
skipped:
environment-only:
new regressions:

[COMMITS]
sha + message

[PRS]
# / title / status / merged 여부

[BLOCKED]
트랙 + 정확한 이유

[REMAINING P0]
없으면 NONE

[REMAINING P1]
목록

[NEXT]
내일 사람이 먼저 확인할 최대 5개
```

---

## 7. 최종 원칙

이번 TASK는 순차적으로 한 항목씩 완료하고 멈추는 작업이 아니다.

**서로 독립적인 것은 가능한 한 병렬로 최대한 많이 구현한다.**

단 같은 파일/같은 contract를 동시에 수정해 충돌을 만들지 않는다.

목표는 내일 사용자가 돌아왔을 때:

- 구현 가능한 것은 최대한 구현되어 있고
- 각 트랙의 테스트 결과가 남아 있고
- 안전한 PR은 병합돼 있으며
- 불확실한 것은 OPEN/BLOCKED로 명확히 분리되어 있고
- 추가 질문 없이 한 번에 검수 가능한 상태

를 만드는 것이다.

"작업 1개만 수행 후 멈춤" 금지.

안전하게 할 수 있는 독립 작업이 남아 있는 동안 계속 진행한다.
