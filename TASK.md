# auto_write

> 이 파일은 이 GitHub 레포의 유일한 AI 작업지시 기준이다.
> Google Tasks와는 완전히 별개이며 Google Tasks의 항목을 조회·복사·동기화하지 않는다.

---

# 0. TASK LIST

<!--
비개발자가 이 부분만 보고도 현재 작업을 이해·수정·삭제할 수 있어야 한다.
상태: 대기 / 진행 중 / 완료 / 막힘 / 취소 는 아래 기호만 사용한다.
TASK 1개 = 반드시 1줄. LIST의 TASK_ID와 DETAILS의 TASK_ID는 반드시 1:1.
사용자가 "삭제"하면 LIST + DETAILS 모두 삭제. "취소"하면 취소 상태로 보존 가능.
REQUEST_SOLVED=YES가 아닌 작업은 완료 표시 금지.
-->

[~] AW-001 | 문서 작성이 정해진 검사 경로를 거쳐 끝나게 한다
[ ] AW-002 | GitHub와 작업 상태를 안전하게 주고받게 한다
[ ] AW-003 | L 규칙을 한 화면에서 보고 고칠 수 있게 한다
[ ] AW-004 | 문서 작성 진행 상태를 한 화면에서 보게 한다
[ ] AW-005 | 새 작성과 기존 자료 작성을 한 흐름으로 단순화한다
[ ] AW-006 | 루트 파일을 역할별로 정리한다
[ ] AW-007 | 중복·미사용 코드를 찾아 정리한다
[ ] AW-008 | 남은 L 규칙 빈칸을 실제 검사로 채운다
[ ] AW-009 | 요구사항 문서로 운영 웹앱 P0를 만든다


---

# 1. REPOSITORY

REPO: pds2225/auto_write
BASE: master
REMOTE: https://github.com/pds2225/auto_write

## 작업지시 파일

실행 기준은 이 파일 하나뿐이다.

- `TASK.md`만 작업지시 파일로 사용한다.
- `NEXT_TASK.md`는 없다. 실행 기준은 TASK.md만.
- 별도의 CURRENT_TASK.md / NEW_TASK.md / NEXT_TASK.md를 만들지 않는다.
- 다른 레포 TASK, Google Tasks, 과거 채팅 내용을 임의 실행하지 않는다.
- 사용자의 새 요청은 이 TASK.md에 새로운 TASK 항목으로 등록한다.

---

# 2. GOOGLE TASKS 완전 분리

Google Tasks는 이 개발 TASK 시스템과 무관하다.

금지:

- Google Tasks 조회
- Google Tasks 항목 가져오기
- Google Tasks → TASK.md 자동등록
- TASK.md → Google Tasks 등록
- 상태/제목/완료 여부 동기화
- Google Tasks 내용을 개발 우선순위 판단에 사용

---

# 3. GIT 안전 동기화

원칙: 작업은 로컬에서 한다. 기준과 병합은 원격이다.
로컬이 원격보다 **앞서기만** 하면(갈라지지 않음) 막지 않는다. 커밋된 내용을 **push한 뒤 원격에서 머지**해서 로컬=원격을 맞춘다.

작업 시작 전 반드시:

1. `git fetch --all --prune`
2. `git remote get-url origin` — 이 파일 `# 1. REPOSITORY`의 REPO와 일치하는지 확인
3. `git branch --show-current`
4. `git status --short`
5. ahead / behind / diverged 확인:

`git rev-list --left-right --count HEAD...origin/master`

왼쪽 숫자 = 로컬이 앞선 커밋(ahead). 오른쪽 = 로컬이 뒤처진 커밋(behind).
둘 다 0보다 크면 diverged(갈라짐). 둘 다 0이면 동기화됨.

쉬운 말:

- 나만 앞이면 → 올려서 맞춘다. 막지 않는다.
- 나만 뒤면 → 받아서 맞춘다.
- 서로 갈라졌으면 → 강제로 덮지 말고 합친다. 못 합치면 멈춘다.
- 저장 안 한 수정이 있으면 → 지우지 않는다.
- 남이 같은 브랜치에 올렸으면 → 덮어쓰지 말고 먼저 받고 합친다.

## 판정 (fetch 후, AI가 그대로 실행)

`<BASE>`는 `# 1. REPOSITORY`의 BASE다. 이 레포는 `master`.

동기화됨(ahead=0, behind=0, clean)이면 그대로 작업을 시작한다.

### 1. behind only

조건: 현재 브랜치가 BASE, working tree clean, ahead=0, behind>0.

실행: `git merge --ff-only origin/master`

실패하면 `BLOCKED`. `reset --hard`로 맞추지 않는다.

### 2. ahead only

조건: ahead>0, behind=0 (diverged 아님). **ahead only는 BLOCKED가 아니다.**

실행:

1. 미커밋 변경이 있으면 **이번 작업 파일만** 커밋한다. `git add -A` 금지. 사용자 쓰레기 파일을 올리지 않는다.
2. `git push` (force 금지).
3. 현재가 작업 브랜치면 PR을 만든다. 충돌 없음 + GitHub Checks 초록일 때만 머지한다. 실패 체크를 무시하는 `gh pr merge --admin`은 금지한다.
4. 이미 BASE면 push로 원격을 로컬에 맞춘다. 보호 규칙으로 push가 거절되면 PR로 올린다.
5. 이후 `git fetch`로 로컬=원격을 확인한다.

### 3. diverged

조건: ahead>0 그리고 behind>0. 양쪽이 다 앞선 상태다.

force push 금지.

`git fetch` 후 안전하게 합칠 수 있으면 합친다 (`git merge origin/<현재브랜치>` 또는 해당 원격 브랜치). 충돌을 무조건 ours/theirs로 해결하지 않는다.

합친 뒤 `git push` (force 금지).

안전하게 합칠 수 없으면 `BLOCKED`.

### 4. dirty uncommitted

사용자 변경 삭제 금지. `git reset --hard` / `git clean -fd` / stash drop 금지.

선택:

- 이번 작업 파일이면 커밋한 뒤 **2. ahead only** 경로로 간다.
- 이번 작업이 아니거나 BASE를 더럽히면, 별도 worktree에서 `origin/master` 최신으로 작업한다.

안전하게 분리하지 못하면 `BLOCKED`.

### 5. 남이 같은 브랜치에 올린 뒤

로컬 push 전에 다시 `git fetch`.

behind가 생겼으면 force로 덮지 말고 먼저 받고 합친다. 그다음 push.

## 절대 금지

- `git reset --hard`
- force push (`--force`, `--force-with-lease` 포함)
- `git clean -fd`
- 사용자 변경 삭제
- 임의 stash/drop
- 충돌을 무조건 ours/theirs로 해결
- 로컬 파일을 원격 상태에 강제로 덮어쓰기
- `git add -A`

---

# 4. TASK 실행 계약 고정 — TASK PINNING

AI가 TASK를 시작할 때 반드시 아래 값을 기록한다.

TASK_ID: <현재 [~] TASK ID>
TASK_START_SHA: <작업 시작 시 origin/base commit SHA>
TASK_BLOB_SHA: <그 시점 TASK.md blob SHA>
WORK_BRANCH: <task/TASK-ID 등>

## 목적

작업 도중 `TASK.md`가 새 요청으로 변경되더라도,
이미 시작한 일반 TASK는 최초 실행 계약을 기준으로 완료한다.

필요하면 최초 TASK는:

`git show <TASK_START_SHA>:TASK.md`

로 다시 확인한다.

## 작업 중 TASK.md 변경 감지

새 TASK가 일반적인 후속 요청:

- 현재 ACTIVE TASK에 섞지 않는다.
- 현재 TASK를 최초 TASK_ID 기준으로 계속 수행한다.
- 새 TASK는 다음 실행에서 수행한다.

새 TASK가 아래에 해당:

- STOP
- CANCEL
- 기존 작업 즉시 중단 요청
- 보안 긴급지시
- 데이터 손실 방지 지시

→ 현재 TASK를 즉시 중단하고 상태를 기록한다.

---

# 5. TASK 선택 규칙

기본적으로 `[~]` 상태의 TASK 1개를 ACTIVE TASK로 실행한다.

`[~]`가 없으면 실행 가능한 `[ ]` TASK 중 우선순위가 가장 높은 작업을 선택한다.

## TASK 상태

- `[ ]` READY / 대기
- `[~]` ACTIVE / 진행 중
- `[x]` DONE / 실제 요청 해결 완료
- `[!]` BLOCKED / 현재 진행 불가능
- `[-]` CANCELLED / 사용자 취소

## 동시에 ACTIVE

같은 파일·API·DB·entrypoint를 수정하지 않는 독립 작업만 여러 `[~]` 허용.

---

# 6. TASK 우선순위

상충 시 아래 순서로 판단한다.

1. 데이터 손실 방지 / 보안 / Git 안전규칙
2. 가장 최신 사용자의 명시적 요청
3. 현재 ACTIVE TASK
4. ACTIVE TASK 수행에 필수인 선행조건
5. repo의 필수 보호규칙 / architecture contract
6. 기존 대기 TASK
7. backlog
8. 리팩터링 / 고도화 / 미관 개선

판단할 수 없는 충돌은 임의 선택하지 않는다.

→ `BLOCKED`

---

# 7. TASK 간 충돌·의존성

## 병렬 가능

다음을 모두 만족하면 병렬 가능:

- 수정 파일군이 다름
- 같은 public API를 변경하지 않음
- 같은 DB schema/migration을 변경하지 않음
- 같은 runtime entrypoint를 변경하지 않음
- TASK A 결과가 TASK B의 입력이 아님

## 순차 필수

하나라도 해당하면 순차:

- 같은 파일 수정
- 같은 API contract 변경
- 같은 DB migration 변경
- 같은 entrypoint 변경
- 한 TASK가 다른 TASK의 선행조건

순차 예:

TASK-A
→ 실사용 검증
→ 최신 코드 기준 TASK-B
→ 통합 E2E

---

# 8. TASK DETAILS

<!--
TASK LIST 한 줄 요약과 아래 상세 TASK는 TASK_ID로 연결한다.
새 사용자 요청을 TASK로 만들 때 반드시 MUST / KEEP / REMOVE / FORBIDDEN / VERIFY / DONE 관점으로 변환한다.
독립 TRACK은 파일군이 겹치지 않으면 병렬 가능. 동일 entrypoint/registry는 한 owner만 수정.
NEXT_TASK.md 이관(2026-08-13): A/B/C/D/E→AW-001, H→§12 테스트. F→AW-006, G→AW-007, I→AW-008. ACTIVE(AW-001)에 내용 합치지 않음. 파일 삭제.
AW-009(2026-08-14): 웹앱 최종 사양서 실행 TASK. AW-001에 합치지 않음. AW-002~005는 사양서 부분 요구.
-->

## AW-001

### 8-1. 사용자 원문 요청

> 실제 문서 생성 경로가 DomainRouter → DomainPipeline → LRuleEnforcer → Hash 검증 → Finalizer로 수렴하게 하고, business_plan / consultant_application을 실제로 검증한다.

원문 보존:

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

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

문서 작성이 정해진 검사 경로를 거쳐 끝나게 한다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 사업계획서/컨설턴트 신청서 작성이 위 경로로 실제 연결됨
- 모호한 도메인·규칙 실패·해시 변경이면 FINAL이 되지 않음
- 우회 FINAL 경로가 막힘

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: DomainRouter, 도메인 Pipeline, LRule, Finalizer, workspace/results 구조가 존재
- 현재 문제: production caller 배선/FINAL 우회 차단/실제 E2E가 미완료일 수 있음
- 이미 구현된 부분: 기존 CORE/shared services, LRule, Finalizer
- 확인 필요한 부분: 주요 entrypoint 실제 배선

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] business_plan 주요 entrypoint 실제 배선
- [ ] consultant_application 주요 entrypoint 실제 배선
- [ ] ambiguous domain 자동 FINAL 금지
- [ ] LRule report 누락/duplicate/FAIL/REVIEW_REQUIRED/UNVERIFIABLE이면 FINAL 금지
- [ ] artifact/registry hash가 검사 이후 변경되면 FINAL 금지
- [ ] legacy direct FINAL 우회경로 차단
- [ ] business_plan / consultant_application 실제 E2E

### 8-6. KEEP — 유지

- [ ] 기존 DomainRouter / Pipeline / LRule / Finalizer
- [ ] 기존 HWP/HWPX/DOCX 경로
- [ ] 기존 CLI/API 호환
- [ ] 기존 사용자 산출물/데이터

### 8-7. REMOVE — 제거

- [ ] legacy direct FINAL 우회경로

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- LRule 우회 FINAL
- business_plan ↔ consultant_application 내부 직접 의존 확대
- 품질점수/제출가능성 점수 UI 신규 개발
- 실제 사용자 개인정보를 테스트 fixture로 사용

### 8-9. 선행조건·의존성

DEPENDS_ON:

- NONE

파일군이 겹치지 않으면 AW-002/AW-003과 병렬 가능. 동일 entrypoint/registry는 한 owner만 수정.

### 8-10. 구현범위

수정 가능 범위:

- production entrypoint 배선
- Finalizer/LRule 가드
- BP/CA E2E 테스트

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

반드시 확인:

- 업로드/입력 파일 존재·형식·크기 기존 정책
- domain 판단 실패/모호함을 명시적으로 처리
- 정상 입력 / 필수값 없음 / 잘못된 형식 / 허용범위 밖 값

해당되지 않는 항목은 N/A 근거를 남긴다.

### 8-12. 빈상태

검증:

- 입력자료 없음: 필요한 다음 입력 안내
- LRule 없음/누락: FINAL 차단
- 데이터 0건 / 결과 없음 / 일부 필드 없음 / 최초 사용 상태

### 8-13. 로딩상태

문서 생성/변환/LRule 검사 각각 진행 상태 표시. 중복 실행 방지. 장시간 작업은 현재 단계가 보이게 한다.

### 8-14. 오류상태

필요한 경우:

- 문서 파싱/변환 실패
- LRule report 저장 실패
- hash mismatch
- 저장 권한/파일 잠금 오류

각 오류는 사용자에게 원인 한 줄 + 다음 행동을 제공하고 성공으로 위장하지 않는다.

---

## AW-002

### 8-1. 사용자 원문 요청

> 원격 GitHub 레포와 작업상태를 안전하게 쌍방향 sync할 수 있게 한다. 비개발자로도 현재 상태를 알 수 있어야 한다.

원문 보존: 원격 repo와 쌍방향 sync가 가장 중요. `master를 원격에 강제로 맞추기` 버튼이나 동작은 만들지 않는다.

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

GitHub와 작업 상태를 안전하게 주고받게 한다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 현재 repo/브랜치/dirty/ahead/behind/diverged를 볼 수 있음
- 깨끗한 뒤에만 fast-forward로 가져옴
- 로컬 작업은 작업 브랜치 push 또는 PR
- 강제 맞춤/reset-hard가 없음

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: Git 관련 유틸이 있을 수 있음
- 현재 문제: 비개발자용 안전 sync MVP가 미완일 수 있음
- 이미 구현된 부분: 확인 필요
- 확인 필요한 부분: ff-only, dirty 보존, diverged 차단

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] 현재 repo, base branch, local branch 표시
- [ ] local dirty 여부
- [ ] origin 대비 ahead / behind / diverged 표시
- [ ] 원격 변경 가져오기: **clean + behind only**일 때 fast-forward만 허용
- [ ] 로컬 작업 보내기: 현재 작업 branch push 또는 PR 생성 흐름
- [ ] force push/reset-hard 자동 실행 금지
- [ ] dirty/ahead/diverged에서는 원본 보존 + 안전한 새 branch/worktree 안내 또는 안전 분리
- [ ] sync 전/후 SHA와 결과 로그 표시

### 8-6. KEEP — 유지

- [ ] 기존 안전한 secret sync 정책이 있으면 그 정책만 사용
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

- [ ] `master를 원격에 강제로 맞추기` 버튼/동작이 있으면 제거

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- destructive Git sync
- force push / `git reset --hard` / `git clean -fd`
- secret 값 수정/커밋

### 8-9. 선행조건·의존성

DEPENDS_ON:

- NONE

파일군이 겹치지 않으면 병렬 가능.

웹으로 구현할 때는 최신 사양 AW-009를 따른다. 이 TASK를 별도 SaaS sync 제품으로 확장하지 않는다.

### 8-10. 구현범위

수정 가능 범위:

- Git sync UI/CLI
- 상태 표시
- ff-only / push / PR 흐름
- 관련 테스트 (clean/current, clean/behind→ff-only, ahead 보존, dirty 보존, diverged 차단, push, fetch 실패)

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

반드시 확인:

- Git sync는 repo/origin/base/branch/ahead/behind/dirty를 먼저 검증
- 정상 입력 / 필수값 없음 / 잘못된 형식

해당되지 않는 항목은 N/A 근거를 남긴다.

### 8-12. 빈상태

검증:

- sync 변경 없음: `최신 상태` 명시
- 데이터 0건 / 결과 없음

### 8-13. 로딩상태

Git fetch·sync 진행 상태 표시. 중복 실행 방지.

### 8-14. 오류상태

필요한 경우:

- Git fetch/push 실패
- diverged/merge conflict
- 저장 권한/파일 잠금 오류

성공으로 위장하지 않는다.

---

## AW-003

### 8-1. 사용자 원문 요청

> 전체 L 규칙을 한 화면에서 조회·관리·수정할 수 있게 한다.

원문 보존: L로 시작하는 규칙 전체 관리 + 수정 가능 화면 필요. 중복 source of truth 금지. UI 수정이 runtime enforcement를 우회하지 못하게 한다.

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

L 규칙을 한 화면에서 보고 고칠 수 있게 한다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- canonical L 규칙이 누락 없이 보임
- 허용된 필드를 기존 정본을 통해 수정할 수 있음
- 화면에서 고친 내용이 검사를 우회하지 않음

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: LRule 구조 존재
- 현재 문제: 전수관리·수정 화면이 미완일 수 있음
- 이미 구현된 부분: canonical LRule
- 확인 필요한 부분: 누락/중복, runtime report 연결

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] canonical LRule 전체를 누락 없이 목록화
- [ ] rule id/name/domain/category/status/설명/evidence/guard 여부 표시
- [ ] 검색/필터
- [ ] 수정 가능한 정책 필드는 기존 canonical source of truth를 통해 저장
- [ ] 중복 source of truth 금지
- [ ] 규칙 삭제/비활성화 등 FINAL 안전성에 영향을 주는 변경은 경고/검증/감사로그
- [ ] 런타임 report에서 각 규칙이 PASS/FAIL/N/A/REVIEW_REQUIRED/UNVERIFIABLE/USER_OVERRIDE 중 하나로 정확히 1회 판정되는지 표시
- [ ] UI 수정이 runtime enforcement를 우회하지 못하게 한다

### 8-6. KEEP — 유지

- [ ] 기존 canonical LRule source of truth
- [ ] runtime enforcement
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

없음 (중복 registry가 있으면 통합은 사용자 결정 없이 강제하지 않고 BLOCKED)

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- 중복 LRule registry/source of truth 생성
- LRule 우회 FINAL

### 8-9. 선행조건·의존성

DEPENDS_ON:

- NONE

canonical LRule source가 둘 이상이면 사용자 결정 없이는 통합 불가 → BLOCKED.

웹으로 구현할 때는 최신 사양 AW-009(L 규칙 전수조회·수정·Git 반영)를 따른다.

### 8-10. 구현범위

수정 가능 범위:

- LRule 전수관리·수정 화면/API
- 검색/필터
- runtime report 연결
- 관련 테스트 (전체 rule count/누락/중복, edit validation, invalid edit, persistence, runtime report와 rule id 연결)

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

반드시 확인:

- LRule edit는 schema/allowed value/required evidence 검증
- 정상 입력 / 필수값 없음 / 잘못된 형식 / 허용범위 밖 값

해당되지 않는 항목은 N/A 근거를 남긴다.

### 8-12. 빈상태

검증:

- LRule 없음/누락: FINAL 차단
- 목록 0건일 때 사용자가 다음 행동을 알 수 있음

### 8-13. 로딩상태

규칙 목록/저장 진행 상태. 중복 실행 방지.

### 8-14. 오류상태

필요한 경우:

- invalid edit
- 저장 실패
- runtime report 연결 실패

성공으로 위장하지 않는다.

---

## AW-004

### 8-1. 사용자 원문 요청

> 비개발자가 이해할 수 있는 아키텍처·업무흐름 모니터링 화면을 제공한다.

원문 보존: 별도 복잡한 개발자 대시보드가 아니라 한 화면에서 다음만 보여준다.

```text
입력자료
→ 도메인 판정
→ 문서 생성/채움
→ LRule 검사
→ Hash 검증
→ Finalizer
→ FINAL / DRAFT
```

대시보드/프로젝트관리 자체는 불필요. 개발자용 내부 class graph를 그대로 노출하지 않는다.

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

문서 작성 진행 상태를 한 화면에서 보게 한다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 위 단계가 한 화면에 보임
- 각 단계의 대기/진행/완료/실패/검토필요와 핵심 오류 한 줄을 알 수 있음
- 프로젝트 관리 대시보드나 KPI 점수가 추가되지 않음

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: 파이프라인 단계는 코드에 존재
- 현재 문제: 비개발자용 한 화면 모니터가 없을 수 있음
- 이미 구현된 부분: 단계별 산출물 경로가 있을 수 있음
- 확인 필요한 부분: UI 존재 여부

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] 한 화면에 입력자료→도메인 판정→문서 생성/채움→LRule 검사→Hash 검증→Finalizer→FINAL/DRAFT
- [ ] 각 단계: 현재 상태(대기/진행/완료/실패/검토필요), 마지막 실행시각, 핵심 오류 한 줄, 결과 산출물 경로, 관련 규칙/검증 링크
- [ ] 개발자용 내부 class graph를 그대로 노출하지 않는다

### 8-6. KEEP — 유지

- [ ] 기존 파이프라인 단계
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

없음

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- 불필요한 프로젝트 관리 대시보드
- generic KPI dashboard
- 품질점수 UI / 제출가능성 점수
- 사용자가 요청하지 않은 CRM/결제/팀협업 확장

### 8-9. 선행조건·의존성

DEPENDS_ON:

- AW-001 (단계 상태가 실제 runtime과 연결되려면)

파일군이 겹치지 않으면 화면 골격은 병렬 착수 가능. 완료 처리는 AW-001 이후.

웹으로 구현할 때는 최신 사양 AW-009(P2 업무흐름·runtime 모니터링)를 따른다. P0 미완 상태에서 이 화면만 고도화하지 않는다.

### 8-10. 구현범위

수정 가능 범위:

- 비개발자 workflow monitor 화면
- empty/loading/error/success/review-required
- mobile/Windows browser 기본 smoke

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

해당되지 않는 항목은 N/A 근거를 남긴다. 모니터는 주로 상태 표시.

### 8-12. 빈상태

검증:

- 아직 실행 전: 대기 상태 명시
- 결과 없음 / 일부 필드 없음

### 8-13. 로딩상태

각 단계 진행 상태. 중복 실행 방지. 장시간 작업은 현재 단계가 보이게 한다.

### 8-14. 오류상태

필요한 경우:

- 단계 실패를 성공으로 위장하지 않음
- 핵심 오류 한 줄 + 다음 행동

---

## AW-005

### 8-1. 사용자 원문 요청

> 새 사업계획서 작성과 기존 자료→새 양식 작성을 별도 복잡한 제품으로 쪼개지 말고, 하나의 문서작성 흐름에서 source 존재 여부로 처리한다. 출처 표시는 파일명 + 페이지 기준.

원문 보존:

```text
새 문서 작성
→ 양식 선택
→ 기존 자료 추가(선택)
→ 자동 작성/채움
→ 출처 확인
→ LRule 검증
→ FINAL/DRAFT
```

출처 표기 기준: `파일명 + 페이지 번호`. 근거 없는 출처/내용 생성 금지.

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

새 작성과 기존 자료 작성을 한 흐름으로 단순화한다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 문서 작성 진입점이 불필요하게 2개 제품으로 나뉘지 않음
- 기존 자료가 있으면 재사용, 없으면 사용자 입력
- 출처가 `파일명 + 페이지`로 표시되고 날조되지 않음

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: 문서 작성 경로가 여러 진입점일 수 있음
- 현재 문제: 새 작성과 기존 자료 작성이 제품처럼 분리됐을 수 있음
- 이미 구현된 부분: 양식/변환 경로
- 확인 필요한 부분: UX 진입점, 출처 표기

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] 사용자 관점의 문서작성 진입점을 불필요하게 2개 제품으로 분리하지 않는다
- [ ] 권장 UX: 새 문서 작성 → 양식 선택 → 기존 자료 추가(선택) → 자동 작성/채움 → 출처 확인 → LRule 검증 → FINAL/DRAFT
- [ ] 기존 자료가 있으면 재사용하고 없으면 사용자 입력을 사용
- [ ] 출처 표기: `파일명 + 페이지 번호`
- [ ] 근거 없는 출처/내용 생성 금지

### 8-6. KEEP — 유지

- [ ] 기존 양식/변환 경로
- [ ] LRule 검증 후 FINAL/DRAFT
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

- [ ] 불필요하게 분리된 두 번째 문서작성 제품 진입점 (확인 후)

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- 근거 없는 출처/내용 생성
- 품질점수/제출가능성 점수 신규 개발

### 8-9. 선행조건·의존성

DEPENDS_ON:

- AW-001

완료 처리는 runtime 경로가 연결된 뒤.

웹으로 구현할 때는 최신 사양 AW-009(문서 작업 단일 화면, Module 선택, 출처=파일명+페이지)를 따른다.

### 8-10. 구현범위

수정 가능 범위:

- 문서 작성 진입 UX
- source 존재 여부에 따른 한 흐름
- 출처 표기 (파일명+페이지)
- 관련 테스트

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

반드시 확인:

- source citation은 실제 파일/페이지 존재 여부 검증
- 업로드/입력 파일 존재·형식·크기
- 정상 입력 / 필수값 없음 / 잘못된 형식

해당되지 않는 항목은 N/A 근거를 남긴다.

### 8-12. 빈상태

검증:

- 기존 자료 없음: 새 작성 흐름으로 정상 진행
- 출처 없음: 출처를 날조하지 않고 `출처 확인 필요`
- 입력자료 없음: 필요한 다음 입력 안내

### 8-13. 로딩상태

문서 생성/변환 진행 상태. 중복 실행 방지.

### 8-14. 오류상태

필요한 경우:

- 문서 파싱/변환 실패
- 출처 검증 실패
- 잘못된 요청 / 재시도 가능 상태

---

## AW-006

### 8-1. 사용자 원문 요청

> 루트 모든 파일/1단계 디렉터리를 역할별로 분류하고, 안전성이 증명된 문서·스크립트·archive만 기존 구조에 맞게 정리한다.

원문 보존 (NEXT_TASK.md F. Root cleanup):

- KEEP_ROOT / DOC / SCRIPT / DATA / GENERATED / ARCHIVE / DUPLICATE / UNKNOWN 등으로 분류
- 이동 전 저장소 전체 경로 참조를 확인
- business_plan/consultant_application/LRule 구조 자체를 다시 설계하지 않음
- 삭제보다 이동/보존을 우선

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

루트 파일을 역할별로 정리한다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 루트에 역할 불명 파일이 쌓여 있지 않음
- 문서 작성 경로(사업계획서/신청서/L규칙)는 그대로 동작
- 삭제가 아니라 이동·보존이 우선됨

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: 루트에 문서·스크립트·생성물이 혼재할 수 있음
- 현재 문제: 분류·참조 확인 없이 옮기면 깨질 수 있음
- 이미 구현된 부분: 기존 폴더 구조
- 확인 필요한 부분: 전체 경로 참조, KEEP_ROOT 범위

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] 루트 모든 파일/1단계 디렉터리를 KEEP_ROOT / DOC / SCRIPT / DATA / GENERATED / ARCHIVE / DUPLICATE / UNKNOWN 등으로 분류
- [ ] 이동 전 저장소 전체 경로 참조를 확인
- [ ] 안전성이 증명된 문서·스크립트·archive만 기존 구조에 맞게 정리
- [ ] 삭제보다 이동/보존을 우선

### 8-6. KEEP — 유지

- [ ] business_plan / consultant_application / LRule 구조
- [ ] 기존 사용자 산출물/데이터
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

없음 (삭제가 아니라 이동/보존. UNKNOWN은 옮기지 않음)

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- business_plan/consultant_application/LRule 구조 재설계
- 참조 미확인 파일 삭제
- `git reset --hard` / `git clean -fd`

### 8-9. 선행조건·의존성

DEPENDS_ON:

- NONE

파일군이 겹치지 않으면 병렬 가능. 동일 entrypoint/registry는 한 owner만 수정.

### 8-10. 구현범위

수정 가능 범위:

- 루트 문서·스크립트·archive 배치
- 참조 경로 갱신
- 분류 기록

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

반드시 확인:

- 이동 대상 경로가 저장소 다른 곳에서 참조되는지
- 정상 입력 / 필수값 없음 / 잘못된 경로

해당되지 않는 항목은 N/A 근거를 남긴다.

### 8-12. 빈상태

검증:

- UNKNOWN 분류는 그대로 두고 다음 행동을 명시
- 데이터 0건 / 결과 없음

### 8-13. 로딩상태

정적 정리 작업이면 N/A 가능. 대량 이동 시 진행 상태를 남긴다.

### 8-14. 오류상태

필요한 경우:

- 참조가 깨진 이동
- 저장 권한/파일 잠금 오류

성공으로 위장하지 않는다.

---

## AW-007

### 8-1. 사용자 원문 요청

> 도메인 사이 잘못된 의존, 이중 정본, caller 없는 placeholder를 찾고, 중복이 명확하면 정본 구현으로 모은다.

원문 보존 (NEXT_TASK.md G. Architecture / duplicate / placeholder cleanup):

- cross-domain import, core→domains 역의존, dual source of truth를 검사
- 기존 facade/wrapper 중 production caller가 없는 placeholder-only 코드를 식별
- 동일 구현의 중복이 명확한 경우 canonical implementation으로 수렴
- unrelated 대규모 리팩터링은 하지 않음

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

중복·미사용 코드를 찾아 정리한다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 문서 작성은 기존과 같이 동작
- 실제 호출되지 않는 껍데기 코드가 정본처럼 남아 있지 않음
- 같은 기능이 두 곳에 있으면 한곳으로 모음

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: facade/wrapper와 도메인 코드가 함께 있을 수 있음
- 현재 문제: caller 없는 placeholder, dual source of truth 가능
- 이미 구현된 부분: 기존 architecture 테스트가 있을 수 있음
- 확인 필요한 부분: production caller, 역의존

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] cross-domain import, core→domains 역의존, dual source of truth 검사
- [ ] production caller가 없는 placeholder-only facade/wrapper 식별
- [ ] 동일 구현 중복이 명확하면 canonical implementation으로 수렴
- [ ] 관련 architecture 테스트로 회귀 확인

### 8-6. KEEP — 유지

- [ ] 실제 production caller가 있는 기존 경로
- [ ] 기존 CLI/API 호환
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

- [ ] caller 없는 placeholder-only 코드 (식별·근거 후)

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- unrelated 대규모 리팩터링
- business_plan ↔ consultant_application 내부 직접 의존 확대
- 실제 사용 경로 삭제

### 8-9. 선행조건·의존성

DEPENDS_ON:

- NONE

파일군이 겹치지 않으면 병렬 가능. 동일 entrypoint는 AW-001 owner만 수정.

### 8-10. 구현범위

수정 가능 범위:

- 의존/중복/placeholder 식별과 최소 정리
- architecture 테스트
- 정본 수렴이 명확한 중복 구현

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

해당되지 않는 항목은 N/A 근거를 남긴다. 코드 정리 작업.

### 8-12. 빈상태

검증:

- placeholder만 있고 caller 없음: 식별 목록에 명시
- 결과 없음 / 일부 필드 없음

### 8-13. 로딩상태

정적 정리면 N/A 가능.

### 8-14. 오류상태

필요한 경우:

- import 순환/역의존 발견 시 성공으로 위장하지 않음
- 관련 테스트 실패

---

## AW-008

### 8-1. 사용자 원문 요청

> P0가 안정된 뒤에 HIGH impact·LOW/MEDIUM effort L 규칙 빈칸을, guard+test+coverage+runtime wiring이 모두 있을 때만 실제 검사로 전환한다.

원문 보존 (NEXT_TASK.md I. LRule gap mechanization — 여유가 있을 때):

- P0 작업이 안정된 브랜치에서만 수행
- HIGH impact + LOW/MEDIUM effort gap을 우선
- `guard + test + coverage + runtime wiring` 4개가 모두 있을 때만 mechanized로 전환

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

남은 L 규칙 빈칸을 실제 검사로 채운다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 우선순위 높은 L 규칙 빈칸이 실제 검사로 동작
- 검사 없이 이름만 있는 규칙은 mechanized로 표시되지 않음
- P0 문서작성 경로가 깨지지 않음

이 결과가 달성되지 않으면 DONE이 아니다.

### 8-4. 현재상태

- 현재 구현: canonical LRule과 enforcer가 존재
- 현재 문제: gap 중 일부는 guard/test/coverage/runtime이 빠졌을 수 있음
- 이미 구현된 부분: AW-001/AW-003 범위의 규칙 골격
- 확인 필요한 부분: HIGH impact gap 목록

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다.

### 8-5. MUST — 반드시 구현

- [ ] P0(AW-001)이 안정된 브랜치에서만 수행
- [ ] HIGH impact + LOW/MEDIUM effort gap을 우선
- [ ] guard + test + coverage + runtime wiring 4개가 모두 있을 때만 mechanized로 전환
- [ ] 4개 중 하나라도 없으면 mechanized 표시 금지

### 8-6. KEEP — 유지

- [ ] 기존 canonical LRule source of truth
- [ ] runtime enforcement
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

없음 (미완성 gap을 mechanized로 위장하지 않음)

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- LRule 우회 FINAL
- 4개 조건 미충족 규칙을 mechanized로 표시
- 실제 사용자 개인정보를 테스트 fixture로 사용

### 8-9. 선행조건·의존성

DEPENDS_ON:

- AW-001

P0가 안정되기 전에는 착수하지 않는다. 완료 처리는 AW-001 이후.

### 8-10. 구현범위

수정 가능 범위:

- HIGH impact LRule gap의 guard/test/coverage/runtime wiring
- 관련 LRule 테스트

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

반드시 확인:

- mechanized 전환은 4개 조건 충족 여부 검증
- 정상 입력 / 필수값 없음 / 잘못된 형식

해당되지 않는 항목은 N/A 근거를 남긴다.

### 8-12. 빈상태

검증:

- gap이 남아 있으면 목록에 명시하고 mechanized로 위장하지 않음
- LRule 없음/누락: FINAL 차단 (AW-001 계약)

### 8-13. 로딩상태

정적 규칙 전환이면 N/A 가능.

### 8-14. 오류상태

필요한 경우:

- guard 미연결
- coverage 부족
- runtime wiring 누락

성공으로 위장하지 않는다.

---

## AW-009

### 8-1. 사용자 원문 요청

> 내드라이브 요구사항문서와 ChatGPT 공유본을 대조한 최종 사양으로 웹앱을 구현하라고 TASK.md에 넣고 시키려고 한다. 한국어·영어 프롬프트 둘 다 넣는다.

원문 보존:

- 유일한 사양서: Google Docs `auto_write 웹앱 구축 요구사항_최종_20260814`
- 최신본: https://docs.google.com/document/d/1afL0r7pk0Iei0RZoDNgSulpd5uc8fYbdT7eb_wrTxuY/edit
- 동일 제목 사본: https://docs.google.com/document/d/1KXaO0fjsbAaacaLOtjgm5NotSJ4I3LAZoPWpW7OwizQ/edit
- 대화 근거: https://chatgpt.com/share/6a7e7a01-2e24-83e9-8447-125f43d8c454
- 실행 시 영어 프롬프트를 기본으로 쓰고, 문서 제목/링크는 한국어 그대로 둔다.

원문의 의미를 축약 과정에서 변경하지 않는다.

### 8-2. 비개발자용 1줄 요약

요구사항 문서로 운영 웹앱 P0를 만든다

이 문장이 상단 TASK LIST에 그대로 표시된다.

### 8-3. 사용자가 원하는 최종 결과

사용자가 실제로 사용했을 때:

- 브라우저에서 파일을 올리고 자연어로 시키면 기존 auto_write 엔진이 문서를 만든다
- GitHub `pds2225/auto_write`와 웹 상태가 실제로 같고, 다른데 SYNCED라고 하지 않는다
- L 규칙을 웹에서 보고 고치면 GitHub에 실제 반영된다
- 여러 과거 문서에서 원문을 직접 보고 필요한 부분만 골라 `[1][2][3]`으로 조합 지시할 수 있다
- 품질점수·제출가능성·프로젝트 대시보드·DOCX 신규기능이 생기지 않는다

이 결과가 달성되지 않으면 DONE이 아니다. 사양서 §31 DoD 중 P0 항목과 §30 E2E 근거가 있어야 한다.

### 8-4. 현재상태

- 현재 구현: auto_write 엔진/CLI/DomainRouter/LRule/Finalizer, 기존 웹 흔적 가능(`web/operator-console` 등)
- 현재 문제: 사양서 P0 운영 웹앱(문서작업 단일화면 + Git 양방향 Sync + Module 원문선택)이 미완
- 이미 구현된 부분: 기존 엔진. 재사용만 하고 웹용으로 다시 만들지 않는다
- 확인 필요한 부분: 기존 웹/API 코드 위치, LRule registry 정본 경로, HWP/HWPX 실제 지원 범위

문서의 DONE 표시만 믿지 말고 실제 코드/runtime을 확인한다. Drive 문서가 안 열리면 BLOCKED로 보고하고 가짜 사양으로 진행하지 않는다.

### 8-5. MUST — 반드시 구현

P0만 이번 TASK 완료 조건이다. P1/P2는 P0 E2E가 산 뒤에만 착수한다.

- [ ] 사양서를 읽고 기존 repo를 전수 분석한 뒤 P0 계획 → 구현 → E2E 근거 보고
- [ ] GitHub 원격이 Source of Truth. GitHub → Web, Web → GitHub 양방향 Sync 실제 동작
- [ ] 상단에 repo/branch/Web SHA/Remote SHA/Sync 상태 표시. Remote SHA 미확인·push/PR 실패면 SYNCED 금지
- [ ] 기존 엔진/서비스/CLI/DomainRouter/LRuleEnforcer/Finalizer 재사용. 동일 기능 웹 재구현 금지
- [ ] 메뉴: 문서 작업 / L 규칙 / 업무 흐름 / 시스템. 별도 대시보드·프로젝트관리·품질점수·제출가능성 메뉴 금지
- [ ] 문서 작업 단일 화면. 신규/기존자료/수정을 별도 메뉴로 나누지 않고 자동 라우팅
- [ ] 업로드 파일 역할 자동판별 + 사용자가 결과 수정 가능
- [ ] 과거 문서를 Module → Block → 문장/표로 분해. 실제 원문 Viewer
- [ ] 내부 Locator와 사용자 출처(파일명+페이지) 분리. 줄 번호를 찾게 만들지 않음
- [ ] 선택 재료 `[1][2][3]` 번호화, 직접 붙여넣기, 주자료/보조자료 UI 없음
- [ ] 자연어 작성지시 → 작성계획 확인 → Composition Plan → 기존 엔진 실행
- [ ] PRESERVE/ADAPT/REWRITE/NEW 라디오 기본 노출 금지
- [ ] L 규칙 repo 전수 수집·조회(P0 분석). 웹 수정·Git 반영은 사양상 P1이나, Sync 기반이 P0에 포함되면 가짜 목록을 만들지 말 것
- [ ] 사양서 §30 중 P0 관련 E2E: GIT-E2E-01/02/04, MOD-E2E-01/02/03, COMP-E2E-01/02
- [ ] 보고는 사양서 §34 `[WEB BUILD RESULT]` + 이 파일 `# 22. 최종보고`

### 8-6. KEEP — 유지

- [ ] 기존 auto_write 엔진, CLI, DomainRouter, LRule, Finalizer
- [ ] 기존 HWP/HWPX 경로와 repo에 이미 있는 DOCX 호환(삭제하지 않음)
- [ ] TASK.md Git 안전규칙(force push / reset --hard 금지)
- [ ] AW-001 엔진 검사 경로. 이 TASK가 AW-001을 대체하지 않음
- [ ] 사용자가 변경 요청하지 않은 기존 동작

### 8-7. REMOVE — 제거

- [ ] 주자료/보조자료 사용자 선택 UI
- [ ] 그대로활용/최소수정/보완재작성/새로작성 4단 라디오
- [ ] `master를 원격에 강제로 맞추기` 류 destructive Git 동작
- [ ] 품질점수·제출가능성 자동판정 UI가 있으면 신규로 넣지 않고 기존도 웹 메뉴에 올리지 않음

### 8-8. FORBIDDEN — 금지

- 사용자 요청에 없는 기능 임의 추가 금지
- 불필요한 대규모 리팩터링 금지
- 관련 없는 DB/API/UI 변경 금지
- 테스트를 통과시키기 위한 기능 삭제 금지
- 기존 실패 테스트 skip 금지
- 근거 없는 값/데이터 생성 금지

TASK별 추가 금지사항:

- 품질점수 / 제출가능성 자동판정 / CRM / 프로젝트관리 / 매출대시보드 / SaaS 결제
- DOCX 신규 개발·고도화(기존 DOCX 코드 삭제는 금지, 이번 범위 추가도 금지)
- 웹 DB에만 L 규칙 저장
- Remote와 다른 상태를 SYNCED/완료로 표시
- force push / reset --hard / 사용자·원격 작업 덮어쓰기
- UI 목업만 만들고 엔진 미연결
- runtime과 무관한 가짜 progress
- 기존 엔진 중복 재구현
- 고객 문서를 GitHub 코드 repo에 커밋
- 페이지 번호만 주고 몇 번째 줄인지 찾게 하는 UX
- AW-001 ACTIVE 내용에 이 요청을 합치지 않음
- 사양서 없이 기억만으로 기능 추가

### 8-9. 선행조건·의존성

DEPENDS_ON:

- NONE (P0 웹 골격+엔진 호출은 착수 가능)
- 엔진 FINAL 경로 강화는 AW-001 owner. 웹은 기존 엔진을 호출만 한다

관련 대기 TASK (별도 제품으로 다시 만들지 말 것):

- AW-002 = 사양서 Git Sync
- AW-003 = 사양서 L 규칙 화면 (P1)
- AW-004 = 사양서 업무흐름·모니터링 (P2)
- AW-005 = 사양서 문서 작업 단일 진입

같은 web entrypoint를 동시에 고치지 않는다. AW-001과 파일군이 겹치면 순차.

### 8-10. 구현범위

수정 가능 범위:

- 운영 웹앱(문서 작업 P0 화면, Git Sync 상태, 기존 엔진 연결 API)
- Module/Block/Locator/작성계획/Composition Plan
- 사양서 P0 E2E 테스트
- 새 브랜치 + PR

P0 완료 전 금지:

- P1/P2 UI 고도화만 하기
- 디자인 시스템 과투자

기존 구조를 최대한 유지하고 최소 변경한다.

### 8-11. 입력검증

반드시 확인:

- 업로드 파일 존재·형식은 repo가 실제로 지원하는 범위만 표시
- 지원하지 않는 포맷을 지원한다고 표시하지 않음
- 파일 역할 자동판별 오판은 사용자가 고칠 수 있어야 함
- 출처는 실제 파일/페이지가 있을 때만 표시. 없으면 날조하지 않음

해당되지 않는 항목은 N/A 근거를 남긴다.

### 8-12. 빈상태

검증:

- 파일 없음: 다음 입력 안내
- 선택 재료 없음: 새로 작성 지시로 진행 가능, 출처 날조 금지
- Git 변경 없음: 최신/SYNCED는 SHA 확인 후에만
- L 규칙 0건: 하드코딩 목록으로 채우지 않음

### 8-13. 로딩상태

문서 분석·Module 분해·작성계획·엔진 실행·Git fetch/push 각각 실제 runtime 상태. 가짜 timer 금지. 중복 실행 방지.

### 8-14. 오류상태

필요한 경우:

- 파싱/변환 실패
- Git fetch/push/PR 실패
- Sync 충돌
- 엔진 호출 실패
- 사양서/Drive 문서 읽기 실패

각 오류는 원인 한 줄 + 다음 행동. 성공으로 위장하지 않는다. 막히면 `BLOCKED`.

### 8-15. 에이전트 실행 프롬프트 (이 블록을 그대로 사용)

영어를 기본 입력으로 쓴다. 사양서 제목·링크는 그대로 둔다. 불확실하면 멈추고 묻고, 엔진을 지어내거나 SYNCED를 위장하지 않는다.

#### English (default)

```text
Use Google Doc “auto_write 웹앱 구축 요구사항_최종_20260814”
(https://docs.google.com/document/d/1afL0r7pk0Iei0RZoDNgSulpd5uc8fYbdT7eb_wrTxuY/edit)
as the ONLY spec. Build a production web app on top of GitHub repo `pds2225/auto_write`.

This TASK.md item is AW-009. Do not merge it into AW-001.

Rules:
1) Implement P0 only first. Do not polish UI or start P1/P2 before P0 works end-to-end.
2) Reuse existing auto_write engines/services/CLI/DomainRouter/LRuleEnforcer/Finalizer. Do NOT reimplement the same logic for the web.
3) GitHub remote is Source of Truth. Bidirectional GitHub ↔ Web sync must actually work. Never show SYNCED/complete without verifying Remote SHA. Never mark push/PR failure as success. No force-push.
4) Explicitly out of scope: quality scoring, auto submit-readiness judgment, CRM, project management, dashboards, SaaS billing, any new/enhanced DOCX development.
5) Core UX: one “Document Work” screen. Upload → auto role detection → decompose into Module/Block/sentence/table with real source text → user selects materials numbered [1][2][3] (allow paste-in) → natural-language compose instructions → show structured writing plan → Composition Plan → run existing engines. No primary/secondary material UI. Do not expose PRESERVE/ADAPT/REWRITE/NEW radios.
6) User-facing citation = filename + page. Internals use precise Locators. Never force users to hunt “which line on page N”.
7) L-rules: full inventory from repo, search, edit, Git history/rollback. Do not store canonical rules only in a web DB.
8) Non-dev Flow / live runtime monitoring / Architecture are P2. No fake progress animations.
9) Work on a new branch and open a PR. Done means spec §30 E2E + §31 DoD with evidence. Mock-only is FAIL.
10) Final report must follow spec §34 [WEB BUILD RESULT] and TASK.md §22. If blocked, say BLOCKED with cause—do not hide failures.

If unsure, stop and ask; do not invent engines or fake SYNCED.

First analyze the remote repo + the spec, then propose a P0 plan, implement it, and report with real E2E evidence.
```

#### 한국어

```text
Google Docs 「auto_write 웹앱 구축 요구사항_최종_20260814」
(https://docs.google.com/document/d/1afL0r7pk0Iei0RZoDNgSulpd5uc8fYbdT7eb_wrTxuY/edit)
를 유일한 사양서로 삼아, GitHub `pds2225/auto_write` 위에 운영용 웹앱을 구현하라.

이 항목은 AW-009다. AW-001에 합치지 마라.

규칙:
1) 사양서 P0만 먼저 구현. P0 미완이면 P1/P2·UI 고도화 금지.
2) 기존 auto_write 엔진/서비스/CLI/DomainRouter/LRuleEnforcer/Finalizer를 재사용할 것. 동일 기능 웹용 중복 구현 금지.
3) GitHub 원격이 Source of Truth. GitHub↔Web 양방향 Sync 실제 동작 필수. Remote SHA 미확인·push/PR 실패 시 SYNCED/완료 표시 금지. force push 금지.
4) 금지: 품질점수, 제출가능성 자동판정, CRM, 프로젝트관리, 대시보드, SaaS 결제, DOCX 신규 개발/고도화.
5) UX 핵심: ‘문서 작업’ 단일 화면. 업로드 → 파일역할 자동판별 → Module/Block/문장·표 원문 보기·선택 → 선택재료 [1][2][3] 번호화(+직접붙여넣기) → 자연어 작성지시 → AI 작성계획 확인 → Composition Plan → 기존 엔진 실행. 주자료/보조자료 UI 금지. PRESERVE/ADAPT/REWRITE/NEW 라디오 노출 금지.
6) 출처 표시는 파일명+페이지. 내부는 정확한 Locator. 페이지 번호만 주고 줄을 찾게 만들지 말 것.
7) L 규칙은 repo 전수 수집·조회·수정·Git history/rollback. 웹 DB에만 저장 금지.
8) 비개발자용 업무 Flow / 실시간 runtime 모니터링 / Architecture는 P2. 가짜 progress 금지.
9) 새 브랜치에서 작업 후 PR. 완료 판정은 사양서 §30 E2E + §31 DoD만. 목업만으로 PASS 금지.
10) 보고는 사양서 §34 [WEB BUILD RESULT]와 TASK.md §22. BLOCKED는 숨기지 말 것.

불확실하면 멈추고 물어라. 엔진을 지어내거나 SYNCED를 위장하지 마라.

먼저 원격 repo와 사양서를 분석한 뒤, P0 구현 계획 → 구현 → E2E 근거와 함께 보고하라.
```

---

# 9. 실제사용 시나리오

TASK 완료 전에 반드시 실제 사용자 관점으로 검증한다.

해당 TASK DETAILS의 최종 결과·구현범위와 함께 적용한다.

## USER FLOW

사용자 시작점:
화면 / CLI / 이메일 / API / 파일 등 실제 진입점

사용자 행동:
1. 사용자가 실제로 하는 행동
2. 다음 행동
3. 다음 행동

시스템 처리:
실제 production 경로 (mock-only로 대체하지 않음)

사용자 최종 결과:
사용자가 실제 보게 되는 것

## 핵심 질문

`이 결과가 사용자의 최초 요청을 실제로 해결했는가?`

YES가 아니면 DONE 금지.

---

# 10. VERIFY — 해결 여부 검증

사용자 요청과 결과를 1:1로 대조한다.

| 사용자 요구 | 실제 결과 | 판정 |
|---|---|---|
| DETAILS의 MUST 항목 | 실제 결과 | PASS/FAIL |

하나라도 필수 요구가 FAIL이면:

`REQUEST_SOLVED = NO`

---

# 11. 실사용 E2E

최소 1개의 실제 사용자 흐름을 처음부터 끝까지 실행한다.

원칙:

- 단위 테스트만으로 대체 금지
- mock-only 검증만으로 DONE 금지
- 가능한 실제 runtime/production entrypoint 사용
- 실제 외부 유료 호출이나 위험 작업은 안전한 staging/dry-run/preview 사용

E2E 결과:

USER_E2E: PASS | FAIL | BLOCKED

근거:
명령 / 화면 / 산출물 / preview / API 결과

---

# 12. 테스트

실사용 검증을 보조하는 테스트를 수행한다.

최소:

- 정상경로
- 주요 경계값
- 입력검증
- 빈상태
- 주요 오류
- 변경한 기능 단위 테스트
- 관련 integration test

테스트 PASS만으로 DONE 처리하지 않는다.

---

# 13. 회귀검증

이번 변경 때문에 기존 핵심 기능이 깨지지 않았는지 확인한다.

- [ ] 기존 핵심 사용자 흐름
- [ ] 관련 API
- [ ] 인증/권한
- [ ] DB 계약
- [ ] 기존 사용자 데이터
- [ ] 기존 자동화
- [ ] 기존 주요 테스트

관련 없는 전체 제품 고도화는 하지 않는다.

---

# 14. 문서동기화

실제 구현과 문서가 달라진 경우에만 최소 수정:

- README
- TASK 관련 문서
- ARCHITECTURE
- 운영문서
- 테스트/사용법 문서

거짓 DONE 기록을 남기지 않는다.

---

# 15. DONE 기준 — 실제 사용자 요청 해결 기준

## 절대 원칙

다음은 단독으로 DONE 근거가 아니다.

- 코드 작성 완료
- 테스트 PASS
- build PASS
- 오류 없음
- commit 존재
- PR 생성
- 화면이 열림

## DONE

다음을 모두 만족해야 한다.

- [ ] 사용자의 필수 요청사항 전부 해결
- [ ] `REQUEST_SOLVED = YES`
- [ ] 실제 사용자 E2E PASS
- [ ] 사용자가 원하는 최종 결과 확인
- [ ] 필요한 입력/빈/로딩/오류상태 사용 가능
- [ ] 기존 핵심 기능 회귀 없음
- [ ] 금지사항 위반 없음
- [ ] 필요한 문서 동기화
- [ ] commit 완료
- [ ] push 완료

## ALREADY_DONE

새 코드를 만들지 않아도 이미 요청사항이 해결되어 있고
실제사용 E2E로 이를 확인한 경우.

## PARTIAL

일부 구현했지만:

`REQUEST_SOLVED = NO`

인 경우.

작업량이 많아도 DONE 금지.

## BLOCKED

외부 의존성/권한/정책/Git 충돌/검증환경 때문에
안전하게 사용자의 요청을 해결할 수 없는 경우.

## FAIL

구현을 시도했으나 사용자 요청 해결에 실패한 경우.

---

# 16. 작업 종료 전 Git 최신 상태 재확인

작업 완료 직전 다시:

1. `git fetch --all --prune`
2. 현재 `origin/master` 확인
3. `TASK_START_SHA`와 최신 base 비교

## base가 작업 중 변경된 경우

코드를 최신 base와 안전하게 통합한다.

필요하면:

- conflict 해결
- 관련 test 재실행
- USER E2E 재실행
- regression 재실행

단:

최신 TASK.md의 새로운 일반 작업을 현재 ACTIVE TASK에 섞지 않는다.

코드는 최신화할 수 있지만,
ACTIVE TASK의 목적과 DONE 조건은 최초 TASK snapshot을 유지한다.

---

# 17. 작업 완료 후 Git 동기화

TASK 구현 완료:

1. 변경 파일 확인
2. 필요한 파일만 stage (`git add -A` 금지)
3. commit
4. remote work branch에 push

확인:

WORK_BRANCH_PUSHED: YES | NO

## PR/merge가 TASK 범위인 경우

- 필요한 검사 통과
- PR
- merge

머지는 이 TASK가 허용한 경우만 한다. 명시가 없으면 기본 브랜치 병합 금지.

조건:

- 충돌 없음
- GitHub Checks 초록

실패면 merge 명령 실행 금지.

문제: 머지 규칙이 TASK 글뿐이라 `gh pr merge`로 문서 PR을 Checks 빨강인데도 머지할 수 있었다. 예외 머지는 폐지한다.

머지는 GitHub Checks가 초록일 때만 한다. 문서만(`TASK.md`, `*.md`, `docs/**`) 바뀌면 무거운 테스트 대신 `docs-gate`가 초록이면 된다. `gh pr merge --admin` 및 실패 체크를 무시하는 머지는 금지한다.

브랜치 보호(required checks)는 권한/플랜 부족으로 설정하지 못했다. BLOCKED_WITH_EVIDENCE: branch protection classic HTTP 403 Upgrade to GitHub Pro or make this repository public to enable this feature.; ruleset HTTP 403 Upgrade to GitHub Pro or make this repository public to enable this feature.


merge 후:

1. `git fetch`
2. local base clean 확인
3. `git merge --ff-only origin/master`
4. local base와 remote base 일치 확인

절대 reset --hard로 맞추지 않는다.

---

# 18. TASK LIST 상태 갱신 규칙

TASK LIST의 상태는 실제 결과와 반드시 일치한다.

### `[x]`

다음일 때만:

`REQUEST_SOLVED = YES`

### `[~]`

현재 실행 중.

### `[!]`

BLOCKED.

### `[-]`

사용자가 취소.

### `[ ]`

아직 시작하지 않음.

LIST와 DETAILS가 불일치하면 TASK 파일 오류로 간주한다.

---

# 19. TASK 수정/삭제 규칙

## 사용자가 TASK 설명을 수정

TASK LIST 1줄 요약과 해당 DETAILS를 함께 수정한다.

## 사용자가 "삭제"

- TASK LIST 행 삭제
- TASK DETAILS 전체 삭제

## 사용자가 "취소"

- LIST를 `[-]`로 변경
- 상세에는 취소 이유 최소 기록 가능

## 완료 TASK

사용자가 목록에서 완료 TASK도 계속 보고 싶다면 `[x]` 유지.

별도 요청으로 정리할 때만 제거한다.

---

# 20. 새 사용자 요청 등록 규칙

새 요청:

1. 기존 TASK와 동일한 요청인지 확인
2. 이미 해결됐으면 중복 생성 금지
3. 새 TASK_ID 발급
4. 사용자 원문 보존
5. 비개발자용 1줄 요약 생성
6. TASK LIST에 `[ ]` 추가
7. TASK DETAILS 생성
8. MUST/KEEP/REMOVE/FORBIDDEN/VERIFY/DONE 변환
9. 기존 TASK와 dependency/충돌 검사
10. 실행 순서 결정

기존 ACTIVE TASK에 새 요청을 임의 합치지 않는다.

---

# 21. TASK 완료 후 다음 TASK

현재 TASK가 DONE된 후:

- TASK LIST에서 다음 READY 작업 확인
- dependency가 해결된 작업 우선
- 독립 작업은 병렬 가능
- BLOCKED 작업은 건너뛰되 이유 유지

새 TASK가 없으면:

`NO_ACTIVE_TASK`

를 보고하고 개발을 중단한다.

---

# 22. 최종보고

반드시 아래 형식으로 보고한다.

REPO:
TASK_ID:

USER_REQUEST:
REQUEST_SOLVED: YES | NO

TASK_START_SHA:
TASK_BLOB_SHA:
WORK_BRANCH:

USER_E2E: PASS | FAIL | BLOCKED
USER_RESULT:
VERIFY_RESULT:

TEST:
REGRESSION:

COMMIT:
WORK_BRANCH_PUSHED: YES | NO

PR:
MAIN_MERGED: YES | NO | N/A

REMOTE_BASE_SYNC:
LOCAL_BASE_SYNC:

TASK_STATUS:
DONE | ALREADY_DONE | PARTIAL | BLOCKED | FAIL

NEXT_READY_TASK:
PENDING_TASKS:

---

# 23. 최종 STOP 조건

아래 중 하나면 임의 개발을 계속하지 않는다.

- ACTIVE TASK 없음
- 사용자 요청과 TASK 내용이 명백하게 불일치
- repo/origin 불일치
- 안전한 Git 작업공간 확보 불가
- 사용자 데이터를 잃을 위험
- 최신 CANCEL/STOP 지시 발견
- 해결방법 선택이 제품정책을 바꾸며 사용자의 결정이 반드시 필요함

상태를 `BLOCKED` 또는 `NO_ACTIVE_TASK`로 보고한다.
