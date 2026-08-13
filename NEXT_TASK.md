# 실행 금지 — 이 파일은 큐/참고다

```text
실행 기준은 TASK.md 뿐이다.
이 파일만 읽고 구현을 시작하면 STOP.
TASK.md가 이 파일을 읽으라고 명시하지 않으면 열지 마라.

---

# NEXT_TASK — AutoWrite 병렬 개발 큐

대상: `pds2225/auto_write`
기준: 최신 `origin/master`

## 실행 원칙

- 먼저 `git fetch --all --prune` 후 최신 `origin/master`를 기준으로 시작한다.
- 아래 작업 중 **서로 독립적인 것은 가능한 한 전부 병렬 실행**한다.
- 각 작업은 반드시 **최신 origin/master에서 별도 브랜치 + 가능하면 별도 worktree**로 분리한다.
- 각 브랜치에서 구현 → 관련 테스트 → commit → push까지만 수행한다.
- **master 직접 수정/merge/push 금지.**
- PR 생성도 하지 않는다.
- 같은 파일을 건드려 충돌 가능성이 있는 작업들만 순차 처리한다.
- 사용자 승인이나 선택을 기다리지 않는다.
- 막힌 작업은 BLOCKED로 기록하고 다른 독립 작업을 계속한다.
- `git reset --hard`, `git clean -fd`, force push, 사용자 데이터 삭제, secret/API key 변경, 운영 배포 금지.

## 병렬 작업 큐

### A. Production runtime wiring
- 실제 production entrypoint를 전수 조사한다.
- `DomainRouter → DomainPipeline → LRuleEnforcer → Finalizer`가 실제 기존 실행경로에서 호출되도록 연결한다.
- 정의파일/테스트에만 존재하고 실제 caller가 없는 상태를 제거한다.
- 우선 확인: `submission_orchestrator`, `hwpx_submit`, autopilot, bizplan, resume, cross_form, project_service, CLI.

### B. LRule enforcement
- canonical LRule 전체가 runtime report에 정확히 1회 평가되도록 검증/보완한다.
- PASS=evidence 필수, N/A=reason 필수.
- FAIL/REVIEW_REQUIRED/UNVERIFIABLE/missing/duplicate가 있으면 FINAL을 차단한다.
- mechanized rule이 guard_ref 문자열만 있고 실제 runtime guard가 호출되지 않는 경우 우선 연결한다.

### C. Finalizer / hash / bypass
- artifact SHA256 freshness 검증을 완성한다.
- registry SHA256 freshness 검증을 완성한다.
- FINAL/_DRAFT 생성·rename·copy·submittable 경로를 전수 검색한다.
- Finalizer를 우회하는 주요 production path를 차단한다.
- 실패/파일잠금/hash mismatch/report 오류는 fail-closed 처리한다.

### D. Business Plan E2E
- synthetic fixture로 production-like E2E를 만든다.
- domain resolve → business pipeline → LRule → report → hash → Finalizer를 실제로 증명한다.
- positive + negative 케이스를 포함한다.

### E. Consultant Application E2E
- synthetic fixture로 신청서/이력서/cross-form production-like E2E를 만든다.
- domain resolve → consultant pipeline → LRule → report → hash → Finalizer를 증명한다.
- 개인정보·실제 서명·미확정 체크박스 자동추론 금지.

### F. Root cleanup
- 루트 모든 파일/1단계 디렉터리를 KEEP_ROOT / DOC / SCRIPT / DATA / GENERATED / ARCHIVE / DUPLICATE / UNKNOWN 등으로 분류한다.
- 이동 전 저장소 전체 경로 참조를 확인한다.
- 안전성이 증명된 문서·스크립트·archive만 기존 구조에 맞게 정리한다.
- business_plan/consultant_application/LRule 구조 자체를 다시 설계하지 않는다.
- 삭제보다 이동/보존을 우선한다.

### G. Architecture / duplicate / placeholder cleanup
- cross-domain import, core→domains 역의존, dual source of truth를 검사한다.
- 기존 facade/wrapper 중 production caller가 없는 placeholder-only 코드를 식별한다.
- 동일 구현의 중복이 명확한 경우 canonical implementation으로 수렴한다.
- unrelated 대규모 리팩터링은 하지 않는다.

### H. Test / regression / portability
- 관련 변경마다 테스트를 실행한다.
- 최소: architecture, LRule domain/enforcer/finalizer, lessons coverage/integrity, hwpx, submission, resume, cross_form, business-plan 테스트.
- 가능한 경우 `app/tests/` 전체 regression 실행.
- 기존 Python 3.11 hardcoded 실행 실패가 있으면 환경문제와 실제 regression을 분리하고 portability를 검토한다.
- skip/assert True/broad except로 실패를 숨기지 않는다.

### I. LRule gap mechanization — 여유가 있을 때
- P0 작업이 안정된 브랜치에서만 수행한다.
- HIGH impact + LOW/MEDIUM effort gap을 우선한다.
- `guard + test + coverage + runtime wiring` 4개가 모두 있을 때만 mechanized로 전환한다.

## 브랜치 예시

- `task/runtime-wiring`
- `task/lrule-enforcement`
- `task/finalizer-hash`
- `task/e2e-business-plan`
- `task/e2e-consultant`
- `task/root-cleanup`
- `task/architecture-cleanup`
- `task/test-regression`

실제 repo 상태에 맞춰 이름은 조정 가능하다.

## 종료 조건

안전하게 수행 가능한 독립 작업이 남아 있는 동안 멈추지 않는다.

각 브랜치는 깨진 중간상태로 push하지 않는다.

마지막에는 아래만 한 번에 보고한다.

```text
[BRANCHES]
branch / purpose / commit / pushed

[TEST]
branch별 passed / failed / skipped / baseline-only

[BLOCKED]
작업 / 이유

[CONFLICT RISK]
서로 겹치는 브랜치와 파일

[RECOMMENDED MERGE ORDER]
1.
2.
3.

[NOT DONE]
남은 작업
```
