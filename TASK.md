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

[ ] AW-001 | 문서 작성이 정해진 검사 경로를 거쳐 끝나게 한다
[ ] AW-002 | GitHub와 작업 상태를 안전하게 주고받게 한다
[ ] AW-003 | L 규칙을 한 화면에서 보고 고칠 수 있게 한다
[ ] AW-004 | 문서 작성 진행 상태를 한 화면에서 보게 한다
[ ] AW-005 | 새 작성과 기존 자료 작성을 한 흐름으로 단순화한다
[ ] AW-006 | 루트 파일을 역할별로 정리한다
[ ] AW-007 | 중복·미사용 코드를 찾아 정리한다
[ ] AW-008 | 남은 L 규칙 빈칸을 실제 검사로 채운다
[~] T-20260814-01 | 기본 브랜치 보호를 걸고 문서 머지 규칙을 맞춘다
[ ] T-20260814-02 | AIMY급 사업계획서를 공고·양식·기업사실에 맞춰 자동 작성하는 통합 과업을 명세한다


---

# 1. REPOSITORY

REPO: pds2225/auto_write
BASE: main
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

`git rev-list --left-right --count HEAD...origin/main`

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

실행: `git merge --ff-only origin/main`

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
- 이번 작업이 아니거나 BASE를 더럽히면, 별도 worktree에서 `origin/main` 최신으로 작업한다.

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
-->

## T-20260814-01

### 8-1. 사용자 원문
auto_write 공개 전환 후 진행. pds2225/auto_write가 public인지 확인. public이면 기본 브랜치 보호: required docs-gate + 실제 test job, enforce_admins, force push 금지. private면 STOP. mail 건드리지 마. MAIL-002 금지. --admin 금지.

### 최종 결과
auto_write 기본 브랜치에 브랜치 보호가 걸려 있고, 문서 PR은 docs-gate가 초록일 때만 머지된다.

### MUST
- 공개 여부를 확인한 뒤에만 보호를 건다
- required에 있는 job 이름만 넣는다
- enforce_admins
- force push 금지
- TASK.md의 GitHub Pro 403 BLOCKED 문구를 보호 성공 후 갱신한다

### KEEP
- 기존 AW-001~AW-008 과업 내용은 합치지 않는다
- mail은 건드리지 않는다

### REMOVE
- 권한 부족으로 보호를 못 걸었다는 BLOCKED_WITH_EVIDENCE 문구

### FORBIDDEN
- .env / 비밀값
- 요청에 없는 기능 추가
- 존재하지 않는 test job 이름을 required에 넣기
- `gh pr merge --admin`
- mail / MAIL-002

### VERIFY
- `gh repo view` visibility=public
- 기본 브랜치 protection contexts에 docs-gate가 있다
- allow_force_pushes=false, enforce_admins=true

### DONE
- REQUEST_SOLVED=YES: 공개 레포 기본 브랜치 보호가 실제로 걸려 있다

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

## T-20260814-02

REPO: pds2225/auto_write
BASE: main
TASK_ID: T-20260814-02
WORK_BRANCH: docs/task-T-20260814-02-on-main
STATUS_THIS_TURN: 명세만 등록 (`[ ]`). 구현 시작 아님. 제품 코드 0줄.

관계: AW-001~AW-008과 **합치지 않는다**. 본 TASK는 사업계획서 **작성 품질 파이프라인** Epic이다. 구현 시 AW-001의 DomainRouter → LRuleEnforcer → Finalizer 경로를 **KEEP**로 통과해야 한다. AW-001이 `[~]`여도 본 LIST는 `[ ]`로 둔다(이번 턴은 구현 시작이 아님).

ID 채번 메모: 같은 날 LIST에 `[~] T-20260814-01`(기본 브랜치 보호)이 이미 있으므로 본 Epic은 `T-20260814-02`. 기존 T-20260814-01 DETAILS에 내용을 섞지 않는다. GitHub 기본 브랜치는 `main`이며 `master` 브랜치는 원격에 없다(위키의 auto_write BASE=master는 구버전). 이 등록은 실제 default `main`의 루트 TASK.md에 한다.

---

### 8-1. 사용자 원문

아래는 2026-08-14 채팅 요청 전문이다. 축약하지 않는다.

```text
대상 저장소: auto_write

이번 작업의 목적은 코드를 구현하는 것이 아니라, 앞으로 여러 AI 코딩 에이전트가 TASK.md 하나만 읽고 동일한 방향으로 개발할 수 있도록 구현 가능한 수준의 통합 과업 명세를 작성하는 것이다.

## 0. 절대 운영 규칙
우리 저장소는 Wiki에 정의된 방식대로 운영한다.
* 모든 개발 과업의 단일 기준은 main 브랜치 루트의 TASK.md
* 별도의 NEXT_TASK.md, 임시 task 파일, 개인 메모 파일을 새로운 작업 기준으로 만들지 말 것
* 먼저 Wiki의 TASK 운영 규칙을 읽고 그대로 준수할 것
* TASK.md에 이미 진행 중이거나 미완료인 과업이 있다면 임의 삭제·축약·덮어쓰기 금지
* 기존 과업과 이번 과업의 관계를 확인한 뒤 Wiki 규칙에 맞는 위치에 추가/통합할 것
* main 브랜치가 존재하지 않거나 Wiki 규칙과 실제 저장소 상태가 충돌하면 임의 판단하지 말고 BLOCKED로 보고할 것
* 이번 요청에서는 구현 금지
* 소스코드 수정 금지 / 리팩터링 금지 / 마이그레이션 금지 / 실제 사업계획서 생성 금지 / 테스트 코드 구현 금지
* 이번 턴의 산출물은 TASK.md 갱신과 현재 구조 분석 보고뿐이다.

# 1. 먼저 저장소 전체를 조사하라
1. 현재 브랜치, git status, remote, origin/main 상태 확인
2. 저장소 Wiki 및 TASK 운영 규칙 확인
3. 루트 TASK.md 전체 읽기
4. README, architecture 관련 문서, docs 전체에서 사업계획서 자동작성 관련 설계 확인
5. 기존 사업계획서 관련 코드 전수 검색
6. 개념/모듈 존재 여부: DomainRouter, LRuleEnforcer, Finalizer, bizplan, cross-form autofill/rewrite, document ingest, HWP/HWPX/DOCX parser, template parser, renderer, fact/source/provenance, QA/quality
7. 구현됨 / 부분 / 미구현 / 중복 을 표로 정리
8. 재사용 vs 신규 분리. 제안 클래스명을 그대로 만들지 말 것. 중복 시스템 금지.

# 2. 최종 제품 목표
단순한 LLM 문안 생성기가 아니다.
Pipeline: 공고문 + 빈 양식 + 기업 자료 + 기존/과거 사업계획서 + 우수 Benchmark
→ 공고 요구 분석 → 양식 구조 분석 → 기업 사실 추출·통합 → 사실 충돌 검출
→ 평가항목별 작성전략 → 우수본 구조적 품질규칙 → 섹션별 문안·표·도식·증빙 계획
→ 원본 HWP/HWPX/DOCX 양식 렌더 → 사실·수치·분량·누락·양식·증빙 QA → 최종 사업계획서
장기: 사람이 처음부터 쓰지 않아도 AIMY 수준의 구조적 완성도에 접근.
AIMY 내용/숫자 복제 금지. 작성 품질 구조만 일반화. STYLE/QUALITY RULE != FACT.

# 3. Benchmark 자료 (추측 금지)
1. ★AIMY-대한안전보건-사업계획서-분석결과-역추정.txt
2. AI 화상교육 솔루션 AIMY_대한안전보건교육원_본선 제출용 20250919.hwp
3. 동일 계열 PDF
4. 저장소 사업계획서 생성/툴 문서
5. Golden/완성본, 양식 역추정, L Rule
PDF는 레이아웃·표·이미지·강조·증빙 배치까지. 없으면 BLOCKED.

# 4. AIMY에서 가져갈 것 / 가져가면 안 되는 것
가져갈 것(Quality Pattern): 표지 압축, 표지↔본문 동일 Source, Problem→Solution→Scale-up→Team, 주장 직후 근거, 표·불릿 우선, 현황→손실→사례→규제→필요성, 사용자/구매자 이원, AS-IS/TO-BE, 기능표, 개발단계, IP, 경쟁비교, BM, 고객·성과·검증, 일정, 자금, 팀, 증빙 별첨, 표지/본문 계층, 정량·시점 밀도, 평가자 익숙 용어.
가져가면 안 됨: AIMY 회사 고유 사실, 시장규모, 고객 1.1만, 매출, 특허, 정확도, 투자계획, MOU, 사업분야 고유 정책용어.
오류 복제 방지 테스트: 97.9 vs 97.5, 1.1만 기존 vs 목표, 특허 건수, 400억 vs 연차 합, 2025.11.31, MOU 완료 vs 추진중.

# 5. 목표 아키텍처 책임 (명칭은 예시, 기존 재사용)
A Company Master / Fact Graph (fact_id, field, value, unit, as_of, actual/plan/estimate/hypothesis, source, location, confidence, verification)
B Claim Provenance
C Conflict Detector (VERIFIED/CONFLICT/MISSING/ESTIMATE/PLAN/INFERENCE — 임의 선택 금지)
D Canonical Bizplan Schema (COMPANY/ITEM/PROBLEM/SOLUTION/MARKET/CUSTOMER/DIFFERENTIATION/TECHNOLOGY/TRACTION/BUSINESS_MODEL/GO_TO_MARKET/SCALE_UP/TEAM/FINANCE/FUNDING/SCHEDULE/IP/CERTIFICATION/ESG/EVIDENCE)
E Program / Form Compiler → ProgramSpec/FormSpec (코드 복붙 없이)
F Benchmark / Quality Profile (AIMY 종속 금지, 복수 프로필)
G Content Planner (자료→평가전략→결론→Claim→Evidence→표/이미지→분량→문장)
H Renderer (기존 HWP/HWPX/DOCX 재사용)
I QA (누락, unsupported claim, 숫자/날짜, Actual/Plan, source 없는 Claim, KPI 불일치, 분량, 양식 훼손, 표/증빙/공고 제약)

# 6. 4층 데이터 모델 분리
CompanyMaster / ProgramSpec / QualityProfile / DocumentPlan
CompanyMaster + ProgramSpec + QualityProfile → DocumentPlan → Generated Document
현재 코드 대응을 TASK에 명시.

# 7. L Rule 계층
기존 전수 후 깨지 않는 범위에서 L0 Integrity / L1 Universal / L2 Program Family / L3 Program/Form / L4 Benchmark.
권장 우선순위 후보: Integrity > Program/Form > Program Family > Universal Quality > Benchmark Style.
충돌 시 새 파일로 쪼개지 말고 기존 lessons/resume-l-rules/lrule_gate에 통합.

# 8. MarketGate = Golden Case #1
MarketGate 실제 사실만. AIMY 사실 복사 금지. 근거 없는 수치 생성 금지.

# 9. Cross-form 자동재작성 실험
전사(cross_form_autofill)와 서술 재작성은 다른 경로. 기존 전사 KEEP.
1차 corpus 후보 6유형×5=30. 실제 보유 파일로 확정. 없으면 가정 테스트셋 금지.

# 10. Blind / Hold-out
사람 완성본을 generation context에 넣지 않음. 공고+빈양식+당시 기업자료만. 생성 후 사람본과 비교.

# 11. 품질 검증 지표 (개발/회귀용, UI 점수 아님)
Coverage>=98%, Source연결>=95%, Unsupported=0, Numeric inconsistency=0, Actual/Plan 오류=0, 양식보존>=99%, 전문 재작성 비율<=20%, 검토시간 >=70% 감소.
측정 불가면 측정 TASK를 따로. 근거 없이 성공 판정 금지.

# 12. 이미지 3종
Evidence / Data viz / Generated illustration. 생성형을 증빙으로 쓰는 QA 금지.

# 13. Workstream BPQ-00 ~ BPQ-13
00 Baseline Audit / 01 Benchmark Corpus / 02 Canonical Schema / 03 Fact Provenance / 04 Conflict / 05 Program-Form Compiler / 06 Quality Profile / 07 Content Planner / 08 MarketGate Golden / 09 Cross-form Harness / 10 L Rule Mining / 11 Renderer / 12 QA / 13 Regression 100.
각 항목: 목적, 선행, 현재구현, 재사용, 신규, 변경파일, 산출물, 테스트, 수치 DONE, 실패/BLOCKED, 의존.

# 14. TASK 공통 형식
Wiki 우선. 큰 과업마다 목표/현재상태/구현범위/금지/입력검증/빈·로딩·오류/테스트/회귀/문서동기화/Git/DONE·BLOCKED/최종보고.

# 15. 금지 14개
1 AIMY 숫자/사실을 다른 계획서에 전이 금지
2 출처 없는 숫자 생성 금지
3 Actual과 Plan 혼합 금지
4 LLM이 충돌 사실을 임의 선택 금지
5 신규 양식마다 Python 복붙 금지
6 양식별 하드코딩을 기본 전략으로 사용 금지
7 기존 DomainRouter/LRule/Finalizer/cross-form 구조 무시 금지
8 동일 역할 모듈 중복 생성 금지
9 사람 완성본을 generation 입력에 넣은 뒤 Blind Test라고 부르는 것 금지
10 렌더링 성공만으로 품질 성공 판정 금지
11 생성형 이미지를 증빙으로 사용 금지
12 Benchmark 점수를 위해 원문 정답을 generation context에 노출 금지
13 테스트 실패를 삭제/skip하여 DONE 처리 금지
14 원본 HWP/PDF Benchmark 자료 수정 금지

# 16. 이번 턴 수행 = 구현 없이 TASK.md 작성
# 17. 자체검수 YES 14문항
# 18. Git: TASK.md만, dirty 보존, force/reset 금지
# 19. 보고 형식 STATUS/BASELINE/WIKI/EXISTING/GAP/CHANGED/ORDER/BLOCKERS/CODE CHANGES=없음/NEXT
이번 단계에서는 TASK.md 작성까지만 수행하고 구현을 시작하지 마라.
```

운영 주석(원문과 위키 충돌): 사용자 원문과 GitHub default는 `main`. 스킬·위키는 auto_write BASE=`master`이나 **원격 `master` 브랜치는 없다**. master를 되살리지 않고 **실제 기본 브랜치 main**의 루트 TASK.md에 등록한다. 위키 불일치는 BLOCKERS로 남긴다.

---

### 최종 결과

다음 AI가 `원격 기본브랜치 최신화하고 TASK.md만 읽고 적힌 과업만 실행해.` 한 줄만 받아도, AIMY **사실 복제 없이** 품질 구조만 일반화한 사업계획서 자동작성 파이프라인을 **기존 모듈 재사용·확장**으로 BPQ-00부터 구현할 수 있는 실행 명세가 `TASK.md`에 남아 있다. 이번 턴의 사용자 요청 해결 = **명세 등록**. 사업계획서 파일이 생기는 것이 이번 턴 DONE이 아니다.

---

### MUST

- [ ] LIST에 본 ID 1줄 + DETAILS 본 ID 1블록 (기존 AW-* 삭제·축약·혼합 금지)
- [ ] `STYLE/QUALITY RULE != FACT`. AIMY 숫자·고유사실을 Quality Profile에 넣지 않음
- [ ] 4층 분리: CompanyMaster / ProgramSpec / QualityProfile / DocumentPlan
- [ ] 책임 A–I를 **기존 경로 재사용**으로 매핑하고, 갭만 신규. 제안 클래스명(`DomainRouter2` 등) 신설 금지
- [ ] L0–L4를 새 파일로 쪼개지 말고 `lessons` + `lrule_enforcer` + `lrule_gate` + `resume-l-rules`에 계층 태그로 통합. 충돌 시 **기존 L 번호·가드 우선**
- [ ] cross_form **전사**는 KEEP. **서술 재작성**은 별 경로. 혼동 금지
- [ ] MarketGate Golden Case #1: MarketGate 근거만. AIMY 사실 전이 금지
- [ ] Blind/Hold-out: 사람 완성본을 generation context에 넣지 않음
- [ ] 이미지 Evidence / Data viz / Generated illustration 분리 + 생성형 증빙 QA 금지
- [ ] AIMY 내부 충돌 6종을 detector 회귀 케이스로 등록 (복제 금지)
- [ ] 30개 층화는 **실제 보유 파일 조사 후**. 부족하면 N건 + 수집 선행. 가짜 30셋 금지
- [ ] 구현 시 진입: DomainRouter → (본 파이프라인) → LRuleEnforcer → Finalizer. `_DRAFT` 우회 금지
- [ ] 테스트: `py -3.11 -m pytest` (기본 3.14 금지)
- [ ] 원본 HWP/PDF Benchmark 수정 금지. 원본 덮어쓰기 금지

---

### KEEP

- DomainRouter (`app/auto_write/domains/domain_router.py`)
- LRuleEnforcer (`app/auto_write/services/lrule_enforcer.py`) + `app/lrule_gate.py` + `app/tests/lessons_coverage.json` (151)
- Finalizer (`app/auto_write/services/finalizer.py`)
- cross_form_autofill 전사 (`app/auto_write/services/cross_form_autofill.py`). 날조0, 실값/마스킹 보존, 보이는 빈칸만
- company_extract / company_master CLI (식별 필드 마스터 + 파일 간 conflict)
- announcement_analyzer + evaluation_service.parse_announcement
- form_analyzer + analysis.docx_template + document_ingest (HWP/HWPX/PDF/DOCX)
- RenderService + hwpx_fill / hwp_fill / hwp_com_fill / hwpx_submit / hwpx_doctor
- usage_acceptance + self_diagnose + document_quality_orchestrator (서식 점수 ≠ 제출가능)
- bizplan_ai_writer / psst_fill 의 `[확인필요]`·출처 병기 정책
- answers_provenance.json 계측 훅 (project_service)
- bizplan-orchestrator / announcement-form-analysis / cross-form-submission / document-quality-orchestrator / resume-l-rules 스킬 입구
- AW-001~AW-008 미완료 과업 전부

---

### REMOVE

- 해당 없음 (이번 Epic은 기존 기능을 지우지 않는다)
- 구현 단계에서 salvage 중복·미사용 복제본을 건드릴 경우 AW-007과 조율. 본 TASK가 기존 정상 경로를 삭제하지 말 것

---

### FORBIDDEN

공통:

- `.env` / 비밀값 커밋·출력
- 요청에 없는 기능 추가
- `git add -A`, force push, `reset --hard`, 사용자 dirty 삭제
- Google Tasks 조회·동기화
- `NEXT_TASK.md` / CURRENT_TASK.md / 임시 task 파일을 실행 기준으로 만들기
- 기본 3.14로 pytest

사용자 §15 14개 (구현 전 구간에도 적용):

1. AIMY의 숫자/기업사실을 다른 사업계획서에 전이 금지
2. 출처 없는 숫자 생성 금지
3. Actual과 Plan 혼합 금지
4. LLM이 충돌 사실을 임의 선택 금지
5. 신규 양식마다 Python 코드 복붙 금지
6. 양식별 하드코딩을 기본 전략으로 사용 금지
7. 기존 DomainRouter / LRule / Finalizer / cross-form 구조 무시 금지
8. 기존 구현과 동일 역할 모듈 중복 생성 금지
9. 사람 완성본을 generation 입력에 넣은 뒤 Blind Test라고 부르는 것 금지
10. 렌더링 성공만으로 사업계획서 품질 성공 판정 금지
11. 생성형 이미지를 증빙으로 사용 금지
12. Benchmark 점수를 높이기 위해 원문 정답을 generation context에 노출 금지
13. 테스트 실패를 삭제/skip하여 DONE 처리 금지
14. 원본 HWP/PDF Benchmark 자료 수정 금지

추가:

- 제안 클래스명(`FactGraphService`, `LRuleEnforcerV2` 등)을 이유로 병렬 시스템 신설 금지
- MarketGate 테스트셋에 AIMY KPI를 채워 넣는 것 금지
- 비전으로 AIMY 이미지 50장을 Read 하는 것 금지 (connection abort). 파일명+추출문+기존 역추정 md 사용
- 이 TASK 구현을 이번 명세 턴에서 시작 금지

---

### VERIFY

명세 턴 (이번, 이미 수행 대상):

- [ ] origin/main `TASK.md`에 T-20260814-02 LIST 1줄 + DETAILS 1블록
- [ ] AW-001~008 원문·MUST가 그대로
- [ ] diff = TASK.md only
- [ ] 제품 코드 0줄

구현 턴 (이후, BPQ 완료 시):

- [ ] 공고+빈양식+기업자료+과거계획(+품질프로필) → 원본 양식 렌더 → QA
- [ ] AIMY 사실이 출력에 없으면 PASS (MarketGate 등 타 기업)
- [ ] unsupported factual claim = 0, numeric inconsistency = 0, actual/plan 혼동 = 0
- [ ] 양식 구조 보존, fail이면 `_DRAFT`
- [ ] Blind: 사람 완성본 미입력
- [ ] `py -3.11 -m pytest` 관련 신규+회귀
- [ ] REQUEST_SOLVED는 **사용자가 실제로 그 사업계획서를 제출 검토할 수 있을 때**. 테스트 PASS만으로 DONE 금지

---

### DONE

이번 턴(명세) REQUEST_SOLVED=YES 조건:

- master 루트 TASK.md에 본 Epic이 올라갔고, 다음 AI가 BPQ-00부터 구현 가능
- 코드 구현은 하지 않음

전체 Epic REQUEST_SOLVED=YES (미래, `[x]` 조건):

- MarketGate Golden Case가 MarketGate 근거만으로 AIMY **구조 패턴**을 적용한 제출 검토본을 만들고
- Blind 비교가 사람본을 컨텍스트에 넣지 않으며
- 내용 QA(사실·숫자·Actual/Plan·증빙유형) + 서식/수용검사 이중 게이트를 통과
- 30개 층화가 **실제 보유 N건**으로 정직하게 돌아가고, 부족분은 수집 전까지 가짜 30으로 DONE하지 않음
- 사람이 처음부터 다시 쓰지 않아도 되는 수준(전문 재작성 비율 측정 가능할 때 <=20% 목표). 측정기 없으면 그 지표로 DONE 주장 금지

---

## 조사 스냅샷 (2026-08-14, 구현 금지 턴)

### Git (명세 작성 시점)

- 로컬 `D:\auto_write`: 로컬 브랜치명 `master`는 stale, HEAD `aadb500`, dirty 있음 (`.claude/settings.json`, `resume-l-rules/SKILL.md`, `.gitignore`, `REQUEST_LEDGER.md`, `RESUME.md` 등). **삭제·add -A 금지**. 이 TASK는 worktree에서만 수정.
- GitHub default: `main` @ `c9ef152`. LIST=AW-001~008 + `[~] T-20260814-01`. 이 파일 `# 1. REPOSITORY` BASE=`main`.
- 원격 `master` 브랜치: **없음**. Wiki BASE=master와 충돌 → BLOCKERS. master를 재생성하지 않음.
- 원격: `https://github.com/pds2225/auto_write.git`

### 개념 존재 여부

| 개념 | 상태 | 현재 경로 | 비고 |
|---|---|---|---|
| DomainRouter | 구현됨 | `app/auto_write/domains/domain_router.py` | KEEP. 재구현 금지 |
| LRuleEnforcer | 구현됨 | `app/auto_write/services/lrule_enforcer.py` | 151 canonical. fail-closed FINAL |
| Finalizer | 구현됨 | `app/auto_write/services/finalizer.py` | FAIL/REVIEW/UNVERIFIABLE → _DRAFT |
| lrule_gate | 구현됨 | `app/lrule_gate.py` | HWPX CLI |
| bizplan 패키지 | 부분(래퍼) | `app/bizplan/services/*` → `auto_write.services` | 정본은 auto_write.services. 래퍼 복제 확장 금지 |
| core/docx 복제 | 중복 | `app/core/docx/services/cross_form_autofill.py` 등 | AW-007 대상. BPQ가 세 벌을 동시에 수정하지 말 것. **정본=`auto_write.services`** |
| salvage 복제 | 중복 | `salvage/cross-form-pdf/` | 실행 경로 아님 |
| cross-form 전사 | 구현됨 | `cross_form_autofill.py` | KEEP |
| cross-form **재작성** | 미구현 | 없음 | 신규 경로. 전사와 파일/함수 분리 |
| document_ingest | 구현됨 | `app/auto_write/document_ingest.py` | HWP/HWPX/PDF→텍스트/DOCX |
| template parser | 구현됨 | `analysis/docx_template.py` + `form_analyzer.py` | 섹션/표/이미지슬롯. Canonical schema 없음 |
| renderer | 구현됨 | `render_service.py`, hwpx_fill, hwp_fill, hwp_com_fill | 원본 복사 후 칸 채움 |
| CompanyMaster 식별필드 | 부분 | `company_extract.py` (기업명·대표자 등 12필드) | fact graph(unit/as_of/actual-plan) 없음 |
| Claim provenance | 부분 | `answers_provenance.json` (user/docx_seed/psst/ai/fallback) | page/as_of/actual-plan 없음 |
| Conflict detector | 부분 | company_extract `Conflict` (식별값 파일 간 불일치) | KPI·날짜·Actual/Plan 충돌 없음 |
| ProgramSpec | 부분 | `announcement_analyzer.AnnouncementReport` | 평가항목·마감·서류. FormSpec(자수/삭제금지/섹션중요도) 약함 |
| QualityProfile | 미구현 | 없음. `quality_rules.BizplanRulesConfig`는 서식 프리셋 | AIMY 문체 규칙 아님 |
| DocumentPlan (내용) | 부분 | `plan_builder.build_fill_plan` = identity/overview/row_rewrites | evaluator_should_conclude 없음 |
| Content planner | 미구현 | `bizplan_ai_writer`는 PSST 약점 영역에 LLM 문단 직접 작성 | 계획 없이 생성 |
| QA 서식/제출 | 구현됨 | doc_quality_score, usage_acceptance, self_diagnose | 내용 일관성 약함 |
| QA 내용(숫자/Actual) | 부분 | `check_unverified_claims`(옵트인), `check_recruit_date_conflict` | AIMY형 KPI 충돌 미구현 |
| PSST | 구현됨 | psst_check / psst_fill | 구조 4영역. 품질프로필 아님 |
| 이미지 3종 | 미구현 | L017 NotebookLM 프롬프트, image_apply | Evidence/viz/illustration 미분류 |

### 4층 데이터 모델 ↔ 현재 코드

| 목표 층 | 질문 | 현재 대응 | 갭 |
|---|---|---|---|
| CompanyMaster | 이 기업은 무엇인가? | `company_extract.CompanyMaster` + CLI `app/bizplan/cli/company_master.py` (`app/company_master.py` 호환). 필드=기업명/대표자/사업자등록번호/설립일/업종/주소/연락처/이메일/홈페이지/직원수/자본금/팩스. confidence high/medium/conflict. confirmed=false 기본 | 아이템·KPI·IP·매출·일정·증빙 fact_id 그래프 없음. unit/as_of/actual\|plan\|estimate\|hypothesis 없음 |
| ProgramSpec | 이번 지원사업은 무엇을 요구하는가? | `announcement_analyzer` + `evaluation_service.EvalCriterion` + `form_analyzer.FormReport` | 단일 ProgramSpec/FormSpec 산출물 없음. 글자/페이지 한도·삭제금지·섹션 중요도·표/이미지 요구 미구조화. 양식마다 코드 복붙할 유혹 → 금지 |
| QualityProfile | 잘 쓴 계획서는 어떻게 표현하는가? | `quality_rules.PRESETS` (bizplan/report/minimal/off) = 색/pt/공란 등 **서식**. `document_type_classifier` 유형 코드 | AIMY_HIGH_DENSITY 같은 **작성 품질 프로필 없음**. 역추정 md는 자료일 뿐 런타임 아님 |
| DocumentPlan | 이번 기업×이번 사업에 무엇을 어디에 어떻게 쓸 것인가? | `plan_builder` fill_plan + ProjectService.answers | 평가전략·Claim·Evidence·표/시각/분량 계획이 없음. LLM이 자료에서 바로 문단 생성 |

공식: `CompanyMaster + ProgramSpec + QualityProfile → DocumentPlan → Renderer → QA`. 층을 한 JSON에 섞지 말 것.

### 책임 A–I 매핑 (갭만 신규)

| 책임 | 재사용 | 신규(확장) | 만들지 말 것 |
|---|---|---|---|
| A Fact graph | company_extract, doc_text_extract, document_ingest | fact 레코드 확장(동일 모듈 또는 `company_extract` 인접). 식별 12필드는 하위호환 | 별도 CompanyMaster2 |
| B Claim provenance | answers_provenance, bizplan_ai_writer evidence_used | claim→source file/page/as_of/status 연결 | 병렬 provenance DB |
| C Conflict detector | company_extract.Conflict | 동일 normalized field의 값/상태 충돌. LLM 자동해소 금지 | 새 Enforcer 클래스 |
| D Canonical schema | form_analyzer.classify_field_kind, cross_form 동의어, PSST 키워드 | 양식 라벨→스키마 키 매핑 테이블 (데이터). 코드 하드코딩 양식 금지 | 양식마다 Parser 클래스 |
| E Program/Form compiler | announcement_analyzer, form_analyzer, folder_analyzer, notice_pipeline | 두 리포트를 ProgramSpec+FormSpec으로 정규화 | 공고 종류별 파이썬 복붙 |
| F Quality profile | quality_rules 서식 프리셋은 **서식층으로 유지** | 작성품질 프로필 JSON. AIMY 역추정에서 **패턴만** | AIMY 문장 템플릿 창고 |
| G Content planner | evaluation_service 약점 섹션, psst_check | SectionPlan 생성 후 문장. `bizplan_ai_writer`는 planner **이후** 호출로 재배선 | writer를 두 개 |
| H Renderer | RenderService, hwpx_*, hwp_*, conversion | planner 출력을 기존 fill/render에 연결 | 새 DOCX 엔진 |
| I QA | usage_acceptance, doc_quality_score, self_diagnose, conversion_fidelity | 내용 QA 체크를 usage_acceptance 또는 인접 모듈에 **가드 추가** (LRule 기계화와 동일 패턴). 점수 UI 신설 금지 | 별도 QualityGate 앱 |

### L Rule 통합 설계 (쪼개지 않음)

현재:

- 정본 교훈: `D:\.omc\agent-learning\lessons.md` (문서작성 섹션)
- 커버리지 SSOT: `app/tests/lessons_coverage.json` — total **151**, mechanized 44 / gap 21 / judgment 86
- 런타임: LRuleEnforcer → Finalizer
- 이력서 체크리스트 스킬: `.claude/skills/resume-l-rules/SKILL.md` (L009 날조0, L011 서식보존, L019 점수≠제출 등). 이력서 전용 L038–L044, L060은 사업계획서 n/a
- AW-003 = L 규칙 한 화면 관리. AW-008 = gap 기계화. **BPQ-10은 이 둘과 파일군이 겹침 → 순차, 레지스트리 owner는 기존 lessons/enforcer**

통합 방안 (새 L0.py~L4.py **금지**):

- 기존 L 항목에 optional `layer` 태그: `integrity` / `program_form` / `program_family` / `universal_quality` / `benchmark_style`
- 충돌 시 **기존 규칙 우선**. 새 품질규칙은 다음 빈 L 번호로 레지스트리 추가 + guard+test+coverage+runtime 4점 충족 전에는 mechanized 표시 금지 (AW-008과 동일)
- 권장 우선순위는 **태그 해석용**: Integrity > Program/Form > Program Family > Universal Quality > Benchmark Style. 기존 L009(날조0)·L011(서식)·L019(DRAFT)와 모순되면 기존이 이김
- 매핑 예: L009→integrity, L011→program_form, L018 분량→program_form, 표지↔본문 KPI 동일 소스→universal_quality, AIMY 표우선·이원표→benchmark_style (사실값 없이)

### Benchmark 자료 실측

| 요청 자료 | 결과 |
|---|---|
| `★AIMY-대한안전보건-사업계획서-분석결과-역추정.txt` | **없음** (다솜/바탕화면/`D:\auto_write`/`D:\v_up` `*.txt` 검색 0). 추측 대체 금지. **BLOCKED 항목**. 동등 산출은 아래 md |
| AIMY 본선 HWP 20250919 | **있음** `C:\Users\ekth3\OneDrive\바탕 화면\다솜\경영지도사 개인\02. 밸류업파트너스\2025년\20250919 대한보건교육원\AI 화상교육 솔루션 AIMY_대한안전보건교육원_본선 제출용 20250919.hwp` (21,028,864 bytes). **원본 수정 금지** |
| 동일 계열 PDF | **있음** 같은 폴더 `…본선 제출용 20250919.pdf` (2,006,623 bytes). 레이아웃 분석은 이번 세션 역추정 md + 추출문 사용. 이미지 50장 비전 Read 금지 |
| 저장소 역추정 | **있음** `D:\auto_write\results\aimy_form_rules\AIMY_대한안전보건교육원_본선제출_역추정.md` + `extracted_fulltext.txt` + `images/` (png 54, 파일 107) + `_report_parts/` + `_work/` |
| 도보네비 역추정 | **있음** `D:\auto_write\results\dobonevi_form_rules\KICXUP_킥스업_박다솜_최종본_문체섹션_사실매핑.md` 등. **품질 패턴 보조만**. AIMY/MarketGate 사실 전이 금지 |
| MarketGate | **있음 (레포 밖 개인폴더 + 레포 예시 1)** OneDrive `…\2026 AI수출지원공통\` 아래 마켓게이트 HWP/PDF/DOCX 다수, `…\_이화여대_사업계획서_초안\` 초안·검수 md. 레포: `tools/injector/examples/content_marketgate.json`. **근거 없는 수치로 테스트셋 만들지 말 것**. 사실팩 미구축이면 BPQ-08 BLOCKED |
| `templates/` | 저장소에 **디렉터리 없음** |

AIMY에서 **규칙으로 승격할 패턴** (사실 제외): 표지=본문 축약, 동일 블록 재사용, 표·불릿 우선, 관리자/이용자 이원, AS-IS/TO-BE, 주장 직후 표/이미지, 별첨=증빙, 무실적=`해당없음`, PSST 한글+영문 병기.

AIMY에서 **절대 승격 금지**: 97.9/97.5, 1.1만, 400억, 특허 건수, 5.6조/89조/1000조, 대한안전보건교육원·임주원·AIMY 제품명 등.

### 보유 공고+양식 (30개 미달 — 정직)

확인된 **구분 가능한 완성/역추정 계열** (가정 셋 아님):

1. 창업 사업화 — 도전 K-스타트업 2025 부처통합본선 (AIMY 제출본 + 같은 폴더 공고/서식 혼재)
2. 지역·특화/산단 — KICXUP 챌린지 (도보네비 역추정)
3. 수출·판로/AI수출 — MarketGate 관련 공고·초안·HWP 다수 (동일 프로그램 버전 반복이 많음. 5개 독립 양식으로 세면 안 됨)

`6유형×5=30`은 **현재 미달**. BPQ-09 DONE을 30으로 주장 금지. 선행: 공고+빈양식 쌍을 실제 경로로 목록화. 지금 숫자: **독립 프로그램 계열 약 3**, 파일 개체는 더 많으나 버전 중복. 부족분 수집이 BPQ-09 선행.

문서유형 분류기 코드(`business_plan`, `rnd_plan`, `export_report` 등)는 **제출문서 유형**이지 30개 양식 corpus가 아니다.

---

## 목표 파이프라인 (구현 시)

```text
공고 + 빈양식 + 기업자료 + 과거계획서 + QualityProfile(벤치마크 패턴)
→ announcement_analyzer / form_analyzer  (E)
→ company_extract 확장 fact graph     (A)
→ conflict detector                   (C)
→ ProgramSpec + FormSpec              (E)
→ DocumentPlan / Content planner      (G)  ← 사람완성본 입력 금지(Blind)
→ bizplan_ai_writer (계획된 Claim만)
→ RenderService / hwpx|hwp fill       (H)
→ usage_acceptance + 내용 QA + LRule + Finalizer  (I)
→ FINAL 또는 _DRAFT
```

---

## Workstream BPQ-00 ~ BPQ-13

공통(모든 BPQ에 적용, 반복 생략):

- **금지**: 위 FORBIDDEN 14 + 원본 덮어쓰기 + 비밀 커밋 + 기존 AW 과업 삭제
- **입력검증**: 경로 존재, 지원 확장자, 빈 입력, 사람완성본이 generation 플래그로 들어오면 거부
- **빈상태**: 사실 0건·공고 파싱 0건이면 빈 DocumentPlan + `[확인필요]` / needs_confirm. 가짜 숫자 채우지 않음
- **로딩상태**: 장시간 ingest/LLM 시 중복 제출 방지. 키가 없으면 결정론 경로(기존과 동일)
- **오류상태**: 파싱 실패·충돌 미해소·양식 격자 깨짐 → 성공 위장 금지, `_DRAFT` 또는 BLOCKED
- **회귀**: `py -3.11 -m pytest tests/ -q` 관련 스위트. 실패 skip 금지
- **문서동기화** (이번 명세 턴에는 **수정하지 않음**. 구현 시만): `AUTO_WRITE_DOMAIN_MAP.md`, `docs/BIZDOC_HUB_MAP.md`, `CLAUDE.md` 변경이력, 해당 스킬 SKILL.md. architecture를 구현 전에 다시 쓰지 말 것
- **Git**: 작업 브랜치에 TASK_ID, `git add`는 해당 구현 파일만, force 금지, dirty 사용자 파일 보존
- **최종보고**: TASK.md §22 형식 + REQUEST_SOLVED

구현 순서(조사 후 확정):

`00 → 01 → 02 → 03 → 04 → 06 → 05 → 07 → 11 → 12 → 08 → 09 → 10 → 13`

이유: 스키마(02) 없이 fact(03) 키를 정하지 않음. 품질프로필(06)은 AIMY 역추정(01)만으로 가능(공고 컴파일러보다 앞). Planner(07)는 Spec+Profile+Fact 필요. Renderer(11)·내용QA(12)가 있어야 Golden(08)을 측정. 30 corpus(09)는 파일 수집 선행. L 승격(10)은 실패 패턴 이후. 100건(13)은 마지막.

병렬 가능: 01의 파일 등록과 00 확인 커밋; 06과 05는 파일군이 다르면 병렬 가능하나 02 스키마 키를 둘 다 쓰므로 02 이후.

---

### BPQ-00 Baseline & Architecture Audit

- **목적**: 위 매핑표를 구현 시작 SHA에 고정. 중복 모듈 정본=`auto_write.services`
- **선행**: 없음. 본 DETAILS가 초안
- **현재**: 본 턴에서 코드 전수 조사 완료. 구현 턴은 origin/main HEAD에서 경로 존재만 재확인
- **재사용**: AUTO_WRITE_DOMAIN_MAP.md, AGENTS.md, BIZDOC_HUB_MAP.md (읽기)
- **신규**: 코드 없음이 기본. 경로가 사라진 경우만 TASK BLOCKED
- **변경 예상 파일**: 없음(확인만). 문서 수정은 문서동기화 목록에만 남김
- **산출물**: 이 DETAILS 매핑이 유효하다는 구현 로그 한 줄
- **테스트**: import 스모크 선택. 대규모 리팩터 금지
- **수치 DONE**: 표의 핵심 경로 파일이 HEAD에 존재. 정본 1곳
- **실패/BLOCKED**: DomainRouter/LRule/Finalizer/cross_form가 삭제됨
- **의존**: 없음
- **구현범위**: 감사만. 새 클래스 금지
- **목표/현재상태**: 위 표와 동일

---

### BPQ-01 Benchmark Corpus

- **목적**: AIMY HWP/PDF/역추정 md를 **읽기 전용 벤치마크**로 등록. 구조 규칙만 추출
- **선행**: BPQ-00
- **현재**: 역추정 md·추출문·images 존재. 요청 txt **없음**
- **재사용**: `results/aimy_form_rules/*`, document_ingest (읽기)
- **신규**: corpus 매니페스트(경로, sha256, 역할=benchmark, 사실사용=false). 품질 패턴 목록은 md에서 복사하지 말고 일반화 문장만
- **변경 예상 파일**: `app/tests/fixtures/` 또는 `app/auto_write/data/` 매니페스트. **원본 HWP/PDF를 레포에 대량 커밋하지 말 것**(용량·개인문서). 경로+해시+추출문만
- **산출물**: `aimy_benchmark_manifest.json` + 일반화 패턴 리스트 (숫자 없음)
- **테스트**: 매니페스트 경로 존재 또는 skip-if-missing; 패턴 JSON에 AIMY 고유 숫자 정규식 금지
- **수치 DONE**: 매니페스트 1, 패턴≥10, AIMY KPI 문자열이 패턴 파일에 0
- **실패/BLOCKED**: 원본 HWP 삭제/이동; txt 없음은 **대체 md로 진행 가능**하되 txt 미발견을 보고서에 유지
- **의존**: 00

---

### BPQ-02 Canonical Bizplan Schema

- **목적**: 양식 라벨 이형을 공통 키로
- **선행**: 00. 01의 섹션 이름은 예시로만
- **현재**: classify_field_kind fact/narrative, PSST 4키, cross_form 동의어. 스키마 enum 없음
- **재사용**: `form_analyzer.py`, `cross_form_autofill` 동의어, `psst_patterns`
- **신규**: 스키마 키 테이블(데이터). 매퍼 함수는 기존 label_utils 확장
- **변경 예상 파일**: `app/auto_write/services/label_utils.py` 또는 인접 schema 모듈 **하나**. tests
- **산출물**: COMPANY…EVIDENCE 키 + 동의어. 예: 개발배경/추진배경/사업필요성 → PROBLEM
- **테스트**: 동일 의미 3라벨 → 한 키; 이력서 전용 라벨은 n/a
- **수치 DONE**: 최소 키 19종 정의, 픽스처 라벨→키 정확도 측정 가능
- **실패/BLOCKED**: 양식마다 if filename== 분기
- **의존**: 00

---

### BPQ-03 Fact / Claim Provenance

- **목적**: 사실 레코드 + 생성 Claim의 출처
- **선행**: 02 (field 키)
- **현재**: CompanyMaster 12필드 + answers_provenance
- **재사용**: company_extract, document_ingest, project_service provenance 훅
- **신규**: value/unit/as_of/status(actual|plan|estimate|hypothesis)/source/page/confidence/verification. Claim 연결
- **변경 예상 파일**: `company_extract.py` 확장 우선. provenance writer. tests `test_company_extract.py`
- **산출물**: 확장 master JSON (기존 12필드 하위호환)
- **테스트**: 숫자 보존(기존 P3 불변), 페이지 없으면 location=unknown (날조 금지)
- **수치 DONE**: 신규 fact에 source 필드 100%. 식별 12필드 회귀 0
- **실패/BLOCKED**: 출처 없이 시장규모 생성
- **의존**: 02

---

### BPQ-04 Conflict Detection

- **목적**: 같은 사실 다른 값/상태면 CONFLICT. LLM 선택 금지
- **선행**: 03
- **현재**: 식별필드 conflict만
- **재사용**: company_extract.Conflict
- **신규**: KPI/날짜/Actual-Plan 혼동 검출. 상태 VERIFIED/CONFLICT/MISSING/ESTIMATE/PLAN/INFERENCE
- **변경 예상 파일**: company_extract 또는 인접 detector + usage_acceptance 가드 + tests
- **산출물**: conflicts[]. 해소는 needs_confirm
- **테스트**: AIMY 오류 6종을 **익명 픽스처**로 (97.9 vs 97.5 등 값을 일반 키 `metric_x`로). AIMY 사명 불필요
- **수치 DONE**: 6종 픽스처 검출 6/6. 자동 해소 0
- **실패/BLOCKED**: 한쪽 값을 조용히 채택
- **의존**: 03

---

### BPQ-05 Program / Form Compiler

- **목적**: 신규 공고+양식 → ProgramSpec/FormSpec. 코드 복붙 없이
- **선행**: 02
- **현재**: AnnouncementReport + FormReport 분리
- **재사용**: announcement_analyzer, form_analyzer, evaluation_service, folder_analyzer
- **신규**: 두 리포트 병합 스키마. 글자/페이지 한도·표/이미지 요구·삭제금지·필수증빙·섹션 중요도 필드
- **변경 예상 파일**: announcement_analyzer/form_analyzer 확장 또는 얇은 compile 함수 1개
- **산출물**: program_spec.json, form_spec.json
- **테스트**: AIMY 양식(K-스타트업 본선) 섹션 22개가 키로 매핑되는지만. 내용 숫자 단언 금지
- **수치 DONE**: 샘플 1개 공고+양식에서 criteria≥1 또는 notes에 한계 명시. 양식 전용 .py 0
- **실패/BLOCKED**: 공고 종류별 하드코딩 파서
- **의존**: 02 (06과 파일 안 겹치면 병렬 가능)

---

### BPQ-06 Quality Profile

- **목적**: AIMY 작성방법을 일반 규칙으로. 복수 프로필 슬롯
- **선행**: 01
- **현재**: BizplanRulesConfig 서식 프리셋만
- **재사용**: quality_rules는 **서식층으로 유지**(이름 충돌 주의). 새 프로필은 별 키
- **신규**: 프로필 JSON: 표지압축, 표우선, 이원 이해관계자, 주장→근거, 표지↔본문 동일 source, 별첨=evidence 등. 값 없음
- **변경 예상 파일**: `quality_rules.py`에 작성프로필을 섞지 말고 인접 `quality_profile` 데이터 + 로더. 또는 quality_rules에 namespace 분리. **중복 프리셋 금지**
- **산출물**: `AIMY_HIGH_DENSITY` 슬롯 + 빈 슬롯 PSST_STARTUP/RND_TECHNICAL/DATA_VOUCHER/EXPORT_MARKET_ENTRY (구현은 슬롯만, 내용 강제 금지)
- **테스트**: 프로필 파일에 금지 숫자 패턴 0; 표우선 플래그가 planner에 전달
- **수치 DONE**: 일반화 규칙 ≥10, AIMY 고유명사 0
- **실패/BLOCKED**: AIMY 문장을 템플릿으로 저장
- **의존**: 01, 02(키 이름)

---

### BPQ-07 Content Planner

- **목적**: 문장 생성 전 SectionPlan
- **선행**: 02, 03, 05, 06
- **현재**: plan_builder=채움좌표. bizplan_ai_writer=직접 문단
- **재사용**: evaluation_service 약점, psst_check, bizplan_ai_writer를 **후단**으로
- **신규**: SectionPlan 필드: evaluator_should_conclude, claims, evidence, missing_evidence, quantitative_points, table_plan, visual_plan, target_length, source_constraints
- **변경 예상 파일**: plan_builder 확장 **또는** 인접 content_planner에서 fill_plan과 병합. writer 시그니처에 plan 필수
- **산출물**: document_plan.json
- **테스트**: 충돌 fact가 있으면 해당 claim 생성 안 함; 사람완성본 경로 주입 시 거부
- **수치 DONE**: 섹션마다 plan 없이 writer 호출 불가(가드). missing_evidence는 빈칸/[확인필요]
- **실패/BLOCKED**: writer가 기업 원문을 그대로 장문 생성
- **의존**: 02, 03, 05, 06

---

### BPQ-08 MarketGate Golden Case #1

- **목적**: MarketGate 사실만으로 품질 패턴 적용 생성
- **선행**: 03, 06, 07, 11, 12. 자료 경로 확인
- **현재**: 개인폴더에 HWP/PDF/DOCX·검수 md, 레포 example json. **통합 fact 그래프 없음**
- **재사용**: ingest, renderer, QA
- **신규**: MarketGate fact 추출(있는 것만). 없는 수치 생성 금지
- **변경 예상 파일**: tests/golden 매니페스트 (경로 로컬). 제품 코드는 기존 파이프라인 호출
- **산출물**: 생성본(워크스페이스 results, gitignore 준수). 사람본과 Blind 비교 리포트
- **테스트**: 출력에 AIMY 고유 문자열 0; 출처 없는 신규 숫자 0
- **수치 DONE**: Golden 1회 파이프라인 통과(또는 _DRAFT+결함 목록). AIMY 전이 0
- **실패/BLOCKED**: MarketGate 근거 파일 부재·접근 불가 시 가정 데이터 금지, BLOCKED
- **의존**: 03, 06, 07, 11, 12

---

### BPQ-09 Cross-form Test Harness

- **목적**: 양식만 바꿔 재작성 가능한지. **전사가 아님**
- **선행**: 05, 07, 12. **실제 파일 목록**
- **현재**: cross_form_autofill E2E는 전사. 재작성 하네스 없음. 30개 미달
- **재사용**: cross_form_fill CLI는 전사 KEEP. 재작성은 새 서브커맨드/함수
- **신규**: harness: 입력=공고+빈양식+기업자료(사람본 제외). 층화 유형 태그
- **변경 예상 파일**: tests/harness, CLI 얇은 엔트리. autofill 함수 시그니처 파괴 금지
- **산출물**: N건 매트릭스. N=실제 보유
- **테스트**: Blind 플래그 기본 on
- **수치 DONE**: **현재 N건 실행**. 30은 수집 후. N<30이면 PARTIAL이지 30 DONE 아님
- **실패/BLOCKED**: 가짜 30 생성; 전사 성공을 재작성 성공으로 보고
- **의존**: 05, 07, 12, 파일 수집

---

### BPQ-10 L Rule Mining / Integration

- **목적**: 08/09/12 실패를 기존 L 레지스트리에 승격
- **선행**: 12, AW-008 계약(4점 충족). AW-003과 파일 충돌 시 순차
- **현재**: 151 규칙, gap 21
- **재사용**: lessons_coverage, LRuleEnforcer, resume-l-rules (사업계획 규칙은 n/a 표시 유지)
- **신규**: layer 태그 + 새 L 번호. 파일 분할 금지
- **변경 예상 파일**: lessons_coverage.json, lrule_enforcer 가드, tests
- **산출물**: 내용 QA 관련 L이 guard+test+coverage+runtime
- **테스트**: AW-008과 동일 4점
- **수치 DONE**: 신규 내용규칙 중 HIGH는 4점 충족 건수만 mechanized
- **실패/BLOCKED**: L0.md~L4.md 신설; 미기계화 규칙을 mechanized로 표시
- **의존**: 12, AW-008 정책

---

### BPQ-11 Renderer Integration

- **목적**: DocumentPlan을 원본 양식에. 구조 보존
- **선행**: 07 (연결). 엔진 자체는 기존
- **현재**: RenderService DOCX, hwpx_fill, hwp_com, hwpx_doctor 격자
- **재사용**: 위 전부 + conversion_fidelity
- **신규**: plan→answers/fill_plan 어댑터만
- **변경 예상 파일**: render_service 또는 pipeline 배선. 새 렌더러 금지
- **산출물**: 양식 보존 렌더
- **테스트**: 원본 표 수/필수 라벨 보존; 격자 repair
- **수치 DONE**: 구조 보존 목표 99%는 **측정기 구현 후**. 측정 전 렌더 성공만으로 DONE 금지
- **실패/BLOCKED**: 빈 DOCX를 새로 만들어 양식을 버림
- **의존**: 07

---

### BPQ-12 QA / Benchmark

- **목적**: 사실·숫자·분량·양식·증빙 유형 검사. UI 점수판 아님
- **선행**: 03, 04, 07
- **현재**: 서식 100점 + 수용검사. 내용 KPI 충돌 약함
- **재사용**: usage_acceptance, doc_quality_score, self_diagnose
- **신규**: 체크: unsupported claim, numeric inconsistency, actual/plan, 이미지 유형 오용, 표지↔본문 KPI
- **변경 예상 파일**: usage_acceptance.py 가드 추가 우선 + tests
- **산출물**: 내용 QA 리포트. 기존 fail→_DRAFT 유지
- **테스트**: AIMY 익명 6종 + 생성형 이미지를 evidence로 넣으면 fail
- **수치 DONE**: 측정 가능한 것부터: unsupported=0, numeric=0, actual/plan=0 을 **픽스처에서**. Coverage 98% 등은 측정기 없으면 별 이슈로 남김 (근거 없이 달성 주장 금지)
- **실패/BLOCKED**: 서식 90점을 내용 성공으로 보고
- **의존**: 03, 04, 11(렌더 산출)

---

### BPQ-13 Regression Corpus

- **목적**: 검증 양식 100건+ 확대
- **선행**: 09가 실제 N으로 안정
- **현재**: 100건 없음
- **재사용**: 09 harness
- **신규**: 수집 절차만. 합성 공고 금지
- **변경 예상 파일**: corpus 목록
- **산출물**: N→100 로드맵. 100 미달이면 DONE 아님
- **테스트**: 회귀 스위트가 N건에서 깨지지 않음
- **수치 DONE**: 실제 파일 100건. 없으면 PARTIAL/BLOCKED
- **실패/BLOCKED**: 복제·합성으로 100 채우기
- **의존**: 09

---

## MarketGate Golden Case 실행 제약

- 입력: MarketGate 기업자료 + 해당 공고 + 빈 양식 + QualityProfile(일반 패턴)
- 금지: AIMY 매출/고객/정확도/특허/MOU
- 패턴만: Problem 사슬, E2E 솔루션, AS-IS/TO-BE, 기능표, 실제 개발상태, 있는 DB/IP만, BM/GTM/일정/팀/증빙
- 없는 값은 `[확인필요]` 또는 공란

---

## Cross-form 재작성 vs 전사

| | 전사 (KEEP) | 재작성 (신규) |
|---|---|---|
| 모듈 | cross_form_autofill | planner + writer + renderer |
| 동작 | 사실 칸 복사, 서술 칸은 `[작성 필요]` | 평가논리·양식에 맞춰 서술 재구성 |
| Blind | 해당 없음 | 사람본 숨김 |
| 성공 | 라벨 매칭 recall | 내용 QA + 양식 보존. 전사 recall로 대체 금지 |

---

## 이미지 3종

| 유형 | 정의 | QA |
|---|---|---|
| Evidence | 특허증·계약·구매의향·실화면 | 원본 파일 필수. 생성형 이면 fail |
| Data viz | 소스 수치 그래프 | fact_id 연결. 없는 수치면 fail |
| Generated illustration | 구조도·프로세스 | 설명용만. 실적 칸 삽입 금지 |

기존 L017 NotebookLM 프롬프트는 illustration 후보. 증빙 슬롯에 넣으면 I QA fail.

---

## AIMY 오류 → detector 회귀 (복제 금지)

익명 픽스처로만. 출력 문서에 AIMY 사명/제품을 넣지 않음.

| ID | 현상 | 검출 |
|---|---|---|
| C1 | 같은 정확도 97.9 vs 97.5 | numeric inconsistency |
| C2 | 1.1만을 기존 고객 vs 확보 목표 | actual vs plan |
| C3 | 특허 1+3 vs 핵심 4건 | count conflict |
| C4 | 총 400억 vs 연차 합 불일치 | sum mismatch |
| C5 | 2025.11.31 | invalid date |
| C6 | MOU 추진 중 vs 완료 단정 | status conflict |

---

## 자체검수 (명세 턴)

| 질문 | 답 |
|---|---|
| 다른 AI가 TASK.md만 읽고 왜 만드는지 이해? | YES |
| AIMY 사실과 작성 품질 분리? | YES |
| 기존 코드 재사용? | YES |
| 신규 양식 하드코딩 금지? | YES |
| MarketGate Golden 포함? | YES |
| 30 Cross-form Blind? | YES (N 정직, 30 미달 명시) |
| 100 Regression 확장? | YES (후속, 합성 금지) |
| Claim provenance 방향? | YES |
| 숫자 충돌 검출? | YES (BPQ-04) |
| 실제/계획/추정 구분? | YES |
| 원본 양식 보존 QA? | YES (BPQ-11/12) |
| 표/도식/증빙까지? | YES |
| DONE 정량? | YES (측정 불가는 별도, 거짓 달성 금지) |
| 이번 턴 코드 미변경? | YES (이 블록 등록 후 제품 코드 0) |

---

### 8-11. 입력검증

- 공고/양식/기업자료 경로 필수. 없으면 진행 중단 + 빈상태 안내
- generation 입력에 `human_final`/`golden_text` 키가 있으면 거부
- MarketGate 실행인데 AIMY 추출문이 컨텍스트에 있으면 거부

### 8-12. 빈상태

- 사실 0: 빈 칸 + `[확인필요]`. 벤치마크 문장으로 채우지 않음
- corpus N=0: harness 스킵이 아니라 BLOCKED/PARTIAL

### 8-13. 로딩상태

- ingest/LLM 중 중복 실행 방지 (기존 autopilot 패턴 재사용)
- API 키 없음: 결정론 경로, 성공 위장 금지

### 8-14. 오류상태

- 충돌 미해소 → 해당 필드 미기입 + CONFLICT 리포트
- 한글 격자 깨짐 → hwpx_doctor, 열리지 않으면 제출 성공 금지
- 측정기 없는 지표로 PASS 로그 금지

---

## Git 규칙 (본 TASK)

- BASE=`main` (GitHub default). 위키의 master는 원격 브랜치 부재로 사용 불가. master 재생성 금지
- 구현 브랜치 예: `feat/bpq-00-audit`, 커밋에 `T-20260814-02` + `BPQ-NN`
- 로컬 dirty 금지 조작. worktree 권장
- 문서-only PR은 기존 CI 빨강이 **이번 diff와 무관**하면 머지 가능 (intake 관례)

---

## 이번 턴 범위

구현하지 않음. 테스트 추가하지 않음. 사업계획서 생성하지 않음. architecture 문서 수정하지 않음. 다음 실행 한 줄은 채팅 보고 NEXT에만.

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
2. 현재 `origin/main` 확인
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

브랜치 보호: 기본 브랜치 `main`(구 master 이름 변경). required checks=`docs-gate`(제품 test workflow 없음). enforce_admins=true, allow_force_pushes=false.


merge 후:

1. `git fetch`
2. local base clean 확인
3. `git merge --ff-only origin/main`
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
