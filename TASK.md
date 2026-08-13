# TASK.md — 이 레포 실행 단일 기준

```text
REPO: pds2225/auto_write
BASE: master
```

## 0. Git 동기화·STOP 게이트
1. `git fetch --all --prune`.
2. `git remote get-url origin`, `git branch --show-current`, `git status --short` 확인.
3. `git rev-list --left-right --count HEAD...origin/master`로 ahead/behind/diverged 확인.
4. 현재 `master`가 clean이고 `ahead=0, behind>0`일 때만 `git merge --ff-only origin/master`로 최신화.
5. dirty/ahead/diverged/다른 브랜치 로컬 전용 변경은 반드시 보존. 삭제·덮어쓰기·자동 reset 금지.
6. `git reset --hard`, force push, `git clean -fd`, 임의 stash/drop 금지.
7. 로컬 변경이 있으면 최신 `origin/master` 기준 별도 branch/worktree에서 작업. 안전 분리 불가 시 `BLOCKED`.
8. 이 `TASK.md`만 실행. 다른 레포 TASK/NEXT_TASK/옛 채팅 과업 금지.
9. secret 값 수정/커밋 금지. 기존 안전한 secret sync 정책이 있으면 그 정책만 사용.
10. 구현 → 테스트 → commit → push → PR까지 가능. 이 TASK는 master 자동병합을 허용하지 않는다.


## 0.1 머지 규칙
- 머지는 **이 TASK가 허용한 경우만** 한다. 명시가 없으면 기본 브랜치 병합 금지.
- 조건: **충돌 없음** + **GitHub Checks 초록**.
- 실패면 merge 명령 실행 금지.
- 예외: **문서만(TASK.md 등) 변경**이고, CI 빨강이 **이번 diff와 무관한 기존 기본브랜치 실패**(예: mail `source_stats`)이면 문서 PR은 머지 가능. 근거를 최종 보고에 적을 것.


## TRACK 골격
TRACK A: AutoWrite 실사용 MVP 정리 (본문 TRACK A–E 유지)
TRACK B: (없음)
TRACK C: (없음)
통합검증: (없음)

# CURRENT TASK — AutoWrite 실사용 MVP 정리

## 목표
AutoWrite를 비개발자가 실제 사용할 수 있는 하나의 작업 흐름으로 정리한다.

최우선 결과:
1. 원격 GitHub 레포와 작업상태를 안전하게 **쌍방향 sync**할 수 있음.
2. 전체 L 규칙을 한 화면에서 조회·관리·수정 가능.
3. 비개발자가 이해할 수 있는 아키텍처·업무흐름 모니터링 화면 제공.
4. 실제 문서 생성 경로가 DomainRouter → DomainPipeline → LRuleEnforcer → Hash 검증 → Finalizer로 수렴.
5. business_plan / consultant_application 실제 E2E 검증.

불필요한 제품 기능은 만들지 않는다.

## 현재상태
기존 코드에는 DomainRouter, 도메인 Pipeline, LRule, Finalizer, workspace/results 구조가 존재하지만 일부는 production caller 배선/FINAL 우회 차단/실제 E2E 검증이 미완료일 수 있다.

최근 사용자 제품 요구:
- 원격 repo와 쌍방향 sync가 가장 중요.
- L로 시작하는 규칙 전체 관리 + 수정 가능 화면 필요.
- 비개발자용 아키텍처와 업무플로우 모니터링 필요.
- 대시보드/프로젝트관리 자체는 불필요.
- 품질점수/제출가능성 점수 기능 불필요.
- 출처 표시는 `파일명 + 페이지` 기준.
- 새 사업계획서 작성과 기존 자료→새 양식 작성은 별도 복잡한 제품으로 쪼개지 말고 하나의 문서작성 흐름에서 source 존재 여부로 처리하는 방향 우선.

## 구현범위
### TRACK A — Production runtime correctness (P0)
실제 production entrypoint를 확인해 아래 흐름으로 수렴:
```text
INPUT
→ DomainRouter
→ DomainPipeline
→ 기존 CORE/shared services
→ format acceptance
→ LRuleEnforcer
→ artifact SHA256
→ registry SHA256
→ Finalizer
→ FINAL 또는 _DRAFT
```

필수:
- business_plan 주요 entrypoint 실제 배선.
- consultant_application 주요 entrypoint 실제 배선.
- ambiguous domain 자동 FINAL 금지.
- LRule report 누락/duplicate/FAIL/REVIEW_REQUIRED/UNVERIFIABLE이면 FINAL 금지.
- artifact/registry hash가 검사 이후 변경되면 FINAL 금지.
- legacy direct FINAL 우회경로 차단.

### TRACK B — 안전한 원격↔로컬 Sync MVP (P0)
사용자가 비개발자로도 현재 상태를 알 수 있게 한다.

최소 기능:
- 현재 repo, base branch, local branch 표시.
- local dirty 여부.
- origin 대비 ahead / behind / diverged 표시.
- 원격 변경 가져오기: **clean + behind only**일 때 fast-forward만 허용.
- 로컬 작업 보내기: 현재 작업 branch push 또는 PR 생성 흐름.
- force push/reset-hard 자동 실행 금지.
- dirty/ahead/diverged 상태에서는 원본 보존 + 안전한 새 branch/worktree 안내 또는 자동 생성 가능한 범위에서 안전 분리.
- sync 전/후 SHA와 결과 로그 표시.

`master를 원격에 강제로 맞추기` 버튼이나 동작은 만들지 않는다.

### TRACK C — L 규칙 전수관리·수정 화면 (P0)
- canonical LRule 전체를 누락 없이 목록화.
- rule id/name/domain/category/status/설명/evidence/guard 여부 표시.
- 검색/필터.
- 수정 가능한 정책 필드는 기존 canonical source of truth를 통해 저장.
- 중복 source of truth 금지.
- 규칙 삭제/비활성화 등 FINAL 안전성에 영향을 주는 변경은 경고/검증/감사로그.
- 런타임 report에서 각 규칙이 PASS/FAIL/N/A/REVIEW_REQUIRED/UNVERIFIABLE/USER_OVERRIDE 중 하나로 정확히 1회 판정되는지 표시.
- UI 수정이 runtime enforcement를 우회하지 못하게 한다.

### TRACK D — 비개발자용 아키텍처·업무플로우 모니터링 (P1)
별도 복잡한 개발자 대시보드가 아니라 한 화면에서 다음만 보여준다:
```text
입력자료
→ 도메인 판정
→ 문서 생성/채움
→ LRule 검사
→ Hash 검증
→ Finalizer
→ FINAL / DRAFT
```

각 단계:
- 현재 상태: 대기/진행/완료/실패/검토필요
- 마지막 실행시각
- 핵심 오류 한 줄
- 결과 산출물 경로
- 관련 규칙/검증 링크

개발자용 내부 class graph를 그대로 노출하지 않는다.

### TRACK E — 문서 작성 흐름 단순화 (P1)
사용자 관점의 문서작성 진입점을 불필요하게 2개 제품으로 분리하지 않는다.

권장 UX:
```text
새 문서 작성
→ 양식 선택
→ 기존 자료 추가(선택)
→ 자동 작성/채움
→ 출처 확인
→ LRule 검증
→ FINAL/DRAFT
```

기존 자료가 있으면 재사용하고 없으면 사용자 입력을 사용.

출처 표기 기준:
```text
파일명 + 페이지 번호
```
근거 없는 출처/내용 생성 금지.

## 금지사항
- 품질점수 UI 신규 개발.
- 제출가능성/선정가능성 점수 신규 개발.
- 불필요한 프로젝트 관리 대시보드.
- generic KPI dashboard.
- 사용자가 요청하지 않은 CRM/결제/팀협업 확장.
- LRule 우회 FINAL.
- business_plan ↔ consultant_application 내부 직접 의존 확대.
- 중복 LRule registry/source of truth 생성.
- 실제 사용자 개인정보를 테스트 fixture로 사용.
- destructive Git sync.

## 입력검증
- 업로드/입력 파일 존재·형식·크기 기존 정책 검증.
- domain 판단 실패/모호함을 명시적으로 처리.
- source citation은 실제 파일/페이지 존재 여부 검증.
- Git sync는 repo/origin/base/branch/ahead/behind/dirty를 먼저 검증.
- LRule edit는 schema/allowed value/required evidence 검증.

## 빈상태
- 입력자료 없음: 빈 화면이 아니라 필요한 다음 입력 안내.
- 기존 자료 없음: 새 작성 흐름으로 정상 진행.
- 출처 없음: 출처를 날조하지 않고 `출처 확인 필요`.
- LRule 없음/누락: FINAL 차단.
- sync 변경 없음: `최신 상태` 명시.

## 로딩상태
- 문서 생성/변환/LRule 검사/Git fetch·sync 각각 진행 상태 표시.
- 중복 실행 방지.
- 장시간 작업은 현재 단계가 보이게 한다.

## 오류상태
- 문서 파싱/변환 실패.
- LRule report 저장 실패.
- hash mismatch.
- Git fetch/push 실패.
- diverged/merge conflict.
- 저장 권한/파일 잠금 오류.
각 오류는 사용자에게 원인 한 줄 + 다음 행동을 제공하고 성공으로 위장하지 않는다.

## 테스트
최소:
### Runtime
- business_plan E2E
- consultant_application E2E
- ambiguous domain negative
- artifact hash 변경 후 FINAL 차단
- registry hash 변경 후 FINAL 차단
- missing/duplicate LRule FINAL 차단
- direct FINAL bypass 차단

### Git Sync
- clean/current
- clean/behind → ff-only 성공
- ahead → 보존
- dirty → 보존
- diverged → reset 없이 차단/분리
- push branch
- fetch 실패

### LRule UI/API
- 전체 rule count/누락/중복
- edit validation
- invalid edit
- persistence
- runtime report와 rule id 연결

### Workflow UI
- empty/loading/error/success/review-required
- mobile/Windows browser 기본 smoke

가능하면 전체 기존 regression 실행.

## 회귀검증
- 기존 CLI/API 호환.
- 기존 business_plan 결과 생성.
- 기존 consultant_application 결과 생성.
- workspace/results legacy read.
- 기존 HWP/HWPX/DOCX 경로.
- 기존 LRule/Finalizer negative tests.
- 기존 사용자 산출물/데이터 비변경.

## 문서동기화
실제 구현과 맞게 필요한 범위에서만:
- README
- AGENTS/CLAUDE 등 실행 규칙 문서
- architecture 문서
- LRule registry/coverage 문서
- TASK/TASKS
를 동기화.

문서가 코드보다 앞서 DONE을 선언하면 안 된다.

## Git 규칙
- 최신 `origin/master`를 기준으로 작업 branch/worktree 생성.
- 독립 TRACK은 파일 owner를 분리해 병렬 가능.
- 동일 entrypoint/registry를 동시에 수정 금지.
- 각 TRACK: 구현 → targeted test → regression → commit → push.
- PR 생성 가능.
- master 자동병합 금지.

## DONE/BLOCKED
DONE 조건:
- production runtime이 DomainRouter→Pipeline→LRule→Hash→Finalizer로 실제 연결.
- BP/CA E2E 통과.
- 안전 Git sync 상태/ff-only/push 흐름 검증.
- LRule 전수관리·수정 화면 동작 및 runtime enforcement 유지.
- 비개발자 workflow monitor 동작.
- 빈/로딩/오류 상태 검증.
- 불필요한 score/dashboard 기능 미추가.

BLOCKED:
- AGENTS.md 보호규칙과 필수 구현 충돌.
- repo diverged/dirty 상태를 안전하게 분리할 수 없음.
- 필수 Python/Windows/HWP 환경이 없어 실제 E2E 검증 불가.
- canonical LRule source가 둘 이상이라 사용자 결정 없이는 통합 불가.

## 최종보고
```text
REPO: pds2225/auto_write
BASE_SYNC: CLEAN_CURRENT | FAST_FORWARDED | LOCAL_CHANGES_PRESERVED | DIVERGED | BLOCKED
TRACK_A_RUNTIME: DONE | BLOCKED
TRACK_B_SYNC: DONE | BLOCKED
TRACK_C_LRULE_UI: DONE | BLOCKED
TRACK_D_WORKFLOW: DONE | BLOCKED
TRACK_E_AUTHORING: DONE | BLOCKED
BRANCHES:
COMMITS:
PUSH:
PRS:
TEST:
REGRESSION:
STATUS: DONE | BLOCKED | FAIL
```

## 실행지시
원격 상태를 안전하게 확인·동기화한 뒤 이 `TASK.md`만 처음부터 끝까지 읽고 실행한다. 독립 TRACK은 병렬로 진행하되 동일 파일/entrypoint는 한 owner만 수정한다. 사용자에게 중간 결정을 요구하지 말고 안전하게 결정 가능한 범위는 진행하며, 위험하거나 정책 결정이 필요한 항목만 `BLOCKED`로 남긴다.

---

# 필수 섹션 템플릿 (하단 고정)

실과업이 있을 때 아래 칸이 비어 있으면 구현 금지(STOP).
아래는 기존 본문에서 옮긴 칸이다. 본문 STOP 게이트가 우선한다.

## 목표
AutoWrite를 비개발자가 실제 사용할 수 있는 하나의 작업 흐름으로 정리한다.

최우선 결과:
1. 원격 GitHub 레포와 작업상태를 안전하게 **쌍방향 sync**할 수 있음.
2. 전체 L 규칙을 한 화면에서 조회·관리·수정 가능.
3. 비개발자가 이해할 수 있는 아키텍처·업무흐름 모니터링 화면 제공.
4. 실제 문서 생성 경로가 DomainRouter → DomainPipeline → LRuleEnforcer → Hash 검증 → Finalizer로 수렴.
5. business_plan / consultant_application 실제 E2E 검증.

불필요한 제품 기능은 만들지 않는다.

## 현재 상태
기존 코드에는 DomainRouter, 도메인 Pipeline, LRule, Finalizer, workspace/results 구조가 존재하지만 일부는 production caller 배선/FINAL 우회 차단/실제 E2E 검증이 미완료일 수 있다.

최근 사용자 제품 요구:
- 원격 repo와 쌍방향 sync가 가장 중요.
- L로 시작하는 규칙 전체 관리 + 수정 가능 화면 필요.
- 비개발자용 아키텍처와 업무플로우 모니터링 필요.
- 대시보드/프로젝트관리 자체는 불필요.
- 품질점수/제출가능성 점수 기능 불필요.
- 출처 표시는 `파일명 + 페이지` 기준.
- 새 사업계획서 작성과 기존 자료→새 양식 작성은 별도 복잡한 제품으로 쪼개지 말고 하나의 문서작성 흐름에서 source 존재 여부로 처리하는 방향 우선.

## 구현범위
### TRACK A — Production runtime correctness (P0)
실제 production entrypoint를 확인해 아래 흐름으로 수렴:
```text
INPUT
→ DomainRouter
→ DomainPipeline
→ 기존 CORE/shared services
→ format acceptance
→ LRuleEnforcer
→ artifact SHA256
→ registry SHA256
→ Finalizer
→ FINAL 또는 _DRAFT
```

필수:
- business_plan 주요 entrypoint 실제 배선.
- consultant_application 주요 entrypoint 실제 배선.
- ambiguous domain 자동 FINAL 금지.
- LRule report 누락/duplicate/FAIL/REVIEW_REQUIRED/UNVERIFIABLE이면 FINAL 금지.
- artifact/registry hash가 검사 이후 변경되면 FINAL 금지.
- legacy direct FINAL 우회경로 차단.

### TRACK B — 안전한 원격↔로컬 Sync MVP (P0)
사용자가 비개발자로도 현재 상태를 알 수 있게 한다.

최소 기능:
- 현재 repo, base branch, local branch 표시.
- local dirty 여부.
- origin 대비 ahead / behind / diverged 표시.
- 원격 변경 가져오기: **clean + behind only**일 때 fast-forward만 허용.
- 로컬 작업 보내기: 현재 작업 branch push 또는 PR 생성 흐름.
- force push/reset-hard 자동 실행 금지.
- dirty/ahead/diverged 상태에서는 원본 보존 + 안전한 새 branch/worktree 안내 또는 자동 생성 가능한 범위에서 안전 분리.
- sync 전/후 SHA와 결과 로그 표시.

`master를 원격에 강제로 맞추기` 버튼이나 동작은 만들지 않는다.

### TRACK C — L 규칙 전수관리·수정 화면 (P0)
- canonical LRule 전체를 누락 없이 목록화.
- rule id/name/domain/category/status/설명/evidence/guard 여부 표시.
- 검색/필터.
- 수정 가능한 정책 필드는 기존 canonical source of truth를 통해 저장.
- 중복 source of truth 금지.
- 규칙 삭제/비활성화 등 FINAL 안전성에 영향을 주는 변경은 경고/검증/감사로그.
- 런타임 report에서 각 규칙이 PASS/FAIL/N/A/REVIEW_REQUIRED/UNVERIFIABLE/USER_OVERRIDE 중 하나로 정확히 1회 판정되는지 표시.
- UI 수정이 runtime enforcement를 우회하지 못하게 한다.

### TRACK D — 비개발자용 아키텍처·업무플로우 모니터링 (P1)
별도 복잡한 개발자 대시보드가 아니라 한 화면에서 다음만 보여준다:
```text
입력자료
→ 도메인 판정
→ 문서 생성/채움
→ LRule 검사
→ Hash 검증
→ Finalizer
→ FINAL / DRAFT
```

각 단계:
- 현재 상태: 대기/진행/완료/실패/검토필요
- 마지막 실행시각
- 핵심 오류 한 줄
- 결과 산출물 경로
- 관련 규칙/검증 링크

개발자용 내부 class graph를 그대로 노출하지 않는다.

### TRACK E — 문서 작성 흐름 단순화 (P1)
사용자 관점의 문서작성 진입점을 불필요하게 2개 제품으로 분리하지 않는다.

권장 UX:
```text
새 문서 작성
→ 양식 선택
→ 기존 자료 추가(선택)
→ 자동 작성/채움
→ 출처 확인
→ LRule 검증
→ FINAL/DRAFT
```

기존 자료가 있으면 재사용하고 없으면 사용자 입력을 사용.

출처 표기 기준:
```text
파일명 + 페이지 번호
```
근거 없는 출처/내용 생성 금지.

## 수정 금지
- 품질점수 UI 신규 개발.
- 제출가능성/선정가능성 점수 신규 개발.
- 불필요한 프로젝트 관리 대시보드.
- generic KPI dashboard.
- 사용자가 요청하지 않은 CRM/결제/팀협업 확장.
- LRule 우회 FINAL.
- business_plan ↔ consultant_application 내부 직접 의존 확대.
- 중복 LRule registry/source of truth 생성.
- 실제 사용자 개인정보를 테스트 fixture로 사용.
- destructive Git sync.

## 입력검증
- 업로드/입력 파일 존재·형식·크기 기존 정책 검증.
- domain 판단 실패/모호함을 명시적으로 처리.
- source citation은 실제 파일/페이지 존재 여부 검증.
- Git sync는 repo/origin/base/branch/ahead/behind/dirty를 먼저 검증.
- LRule edit는 schema/allowed value/required evidence 검증.

## 빈 상태
- 입력자료 없음: 빈 화면이 아니라 필요한 다음 입력 안내.
- 기존 자료 없음: 새 작성 흐름으로 정상 진행.
- 출처 없음: 출처를 날조하지 않고 `출처 확인 필요`.
- LRule 없음/누락: FINAL 차단.
- sync 변경 없음: `최신 상태` 명시.

## 로딩 상태
- 문서 생성/변환/LRule 검사/Git fetch·sync 각각 진행 상태 표시.
- 중복 실행 방지.
- 장시간 작업은 현재 단계가 보이게 한다.

## 오류 상태
- 문서 파싱/변환 실패.
- LRule report 저장 실패.
- hash mismatch.
- Git fetch/push 실패.
- diverged/merge conflict.
- 저장 권한/파일 잠금 오류.
각 오류는 사용자에게 원인 한 줄 + 다음 행동을 제공하고 성공으로 위장하지 않는다.

## 테스트
최소:
### Runtime
- business_plan E2E
- consultant_application E2E
- ambiguous domain negative
- artifact hash 변경 후 FINAL 차단
- registry hash 변경 후 FINAL 차단
- missing/duplicate LRule FINAL 차단
- direct FINAL bypass 차단

### Git Sync
- clean/current
- clean/behind → ff-only 성공
- ahead → 보존
- dirty → 보존
- diverged → reset 없이 차단/분리
- push branch
- fetch 실패

### LRule UI/API
- 전체 rule count/누락/중복
- edit validation
- invalid edit
- persistence
- runtime report와 rule id 연결

### Workflow UI
- empty/loading/error/success/review-required
- mobile/Windows browser 기본 smoke

가능하면 전체 기존 regression 실행.

## 회귀검증
- 기존 CLI/API 호환.
- 기존 business_plan 결과 생성.
- 기존 consultant_application 결과 생성.
- workspace/results legacy read.
- 기존 HWP/HWPX/DOCX 경로.
- 기존 LRule/Finalizer negative tests.
- 기존 사용자 산출물/데이터 비변경.

## 문서 업데이트
실제 구현과 맞게 필요한 범위에서만:
- README
- AGENTS/CLAUDE 등 실행 규칙 문서
- architecture 문서
- LRule registry/coverage 문서
- TASK/TASKS
를 동기화.

문서가 코드보다 앞서 DONE을 선언하면 안 된다.

## commit/push 규칙
- 최신 `origin/master`를 기준으로 작업 branch/worktree 생성.
- 독립 TRACK은 파일 owner를 분리해 병렬 가능.
- 동일 entrypoint/registry를 동시에 수정 금지.
- 각 TRACK: 구현 → targeted test → regression → commit → push.
- PR 생성 가능.
- master 자동병합 금지.

## DONE/BLOCKED 기준
DONE 조건:
- production runtime이 DomainRouter→Pipeline→LRule→Hash→Finalizer로 실제 연결.
- BP/CA E2E 통과.
- 안전 Git sync 상태/ff-only/push 흐름 검증.
- LRule 전수관리·수정 화면 동작 및 runtime enforcement 유지.
- 비개발자 workflow monitor 동작.
- 빈/로딩/오류 상태 검증.
- 불필요한 score/dashboard 기능 미추가.

BLOCKED:
- AGENTS.md 보호규칙과 필수 구현 충돌.
- repo diverged/dirty 상태를 안전하게 분리할 수 없음.
- 필수 Python/Windows/HWP 환경이 없어 실제 E2E 검증 불가.
- canonical LRule source가 둘 이상이라 사용자 결정 없이는 통합 불가.

## 최종 보고 형식
```text
REPO: pds2225/auto_write
BASE_SYNC: CLEAN_CURRENT | FAST_FORWARDED | LOCAL_CHANGES_PRESERVED | DIVERGED | BLOCKED
TRACK_A_RUNTIME: DONE | BLOCKED
TRACK_B_SYNC: DONE | BLOCKED
TRACK_C_LRULE_UI: DONE | BLOCKED
TRACK_D_WORKFLOW: DONE | BLOCKED
TRACK_E_AUTHORING: DONE | BLOCKED
BRANCHES:
COMMITS:
PUSH:
PRS:
TEST:
REGRESSION:
STATUS: DONE | BLOCKED | FAIL
```
