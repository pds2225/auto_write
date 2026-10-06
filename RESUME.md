# RESUME.md — 다른 위치에서 이어가기

> 이 파일과 docs/SESSION_RECAP.md는 GitHub main의 공유 기록이다. TASK 우선순위·상태의 정본은 origin/main:TASK.md다.

## 0. 현재 상태 — 2026-10-06
- 개발 main 통합 요청은 완료됐다. PR #211·#212 병합, 제품 코드 검증 기준 b0e8eedebc16c6d878d76809b8eeafba0d43a50b. 당시 접근 가능한 14개 작업 위치의 HEAD·제품 코드 해시 일치를 확인했다.
- 세션 마무리의 최신 개발 회고·재개 정보를 이제 원격 공유판으로 관리한다. 회고: [docs/SESSION_RECAP.md](docs/SESSION_RECAP.md). root SESSION_RECAP.md는 로컬 전체 회고이며 Git에서 제외되어 있다.
- 아직 실제 한글 2022 DOCX Open 실패·소유 PID 미확인 시 COM hard timeout 한계가 남아 있다. AW-001 REQUEST_SOLVED=NO. Git 통합 성공을 실제 변환 성공으로 보고하지 않는다.

## 1. 다른 PC·클라우드에서 빠른 재개
저장소를 복제한 폴더에서 다음 명령으로 최신 원격 지시와 기록을 먼저 읽는다. 현재 작업 위치나 브랜치가 달라도 조회할 수 있다.

```powershell
git status --short --branch
git fetch origin
git show origin/main:TASK.md
git show origin/main:RESUME.md
git show origin/main:docs/SESSION_RECAP.md
```

미커밋 변경을 보존하고 현재 브랜치를 확인한 뒤 main을 최신화한다. 현재 브랜치가 main이고 충돌할 변경이 없으면 `git merge --ff-only origin/main`을 사용한다. 자동 pull·reset·clean·force push는 하지 않는다.

## 2. 완료·검증
- 호환 경로·UTF-8·제출 검사 복구: 735531f, fake COM 테스트 조회 격리: a7c369c, 관련 기록: c015e34.
- 전체 pytest는 2217 passed/8 failed/5 skipped/23 subtests passed. 가짜 COM의 실제 프로세스 목록 의존을 격리한 뒤 실패 8건 포함 영향 회귀 54 passed/0 failed, 소유권 회귀 21 passed/0 failed. 합산 대상 2225 passed/남은 실패 0이며 두 번째 전체 실행은 아니다. 제품 보호 코드는 유지했다.
- 합성 HWPX 제출 CLI: 원본 해시 보존·값 채움·DRAFT만 생성·171규칙 증거 저장. cp949 STEP 3A CLI: exit 0·UTF-8 Golden 보고서 일치.
- 기존 stash 9개와 보존용 stash 3개, 브랜치 ref·원본 데이터·깨진 worktree 원문을 보존했다. 개발 감사·항목별 결과는 docs/MAIN_SYNC_20261006.md와 docs/PR211_ROUND4.md를 따른다.

## 3. 다음 액션
1. 실제 한글 2022가 설치된 환경에서 DOCX Open 실패 원인을 재현·진단한다. 소유 객체·사용자 원본과 창을 보존한다.
2. 소유 PID 미확인 때도 COM operation을 제한 시간 안에 끝낼 수 있는 방식을 별도 검토·구현한다. 필요한 영향 범위만 테스트하고 이유 없이 전체 suite를 반복하지 않는다.

## 4. 유지할 제약
- 추가 테스트는 꼭 필요할 때만 한다. 기존 성공 assertion·skip·소유권 보호를 약화하지 않는다. rhwp 기본 OFF, L050 gap 유지.
- 사용자 Hwp/Hword 종료·원본 덮어쓰기·main 직접 push·force push 금지. 실제 변환·원본 양식 9건 E2E 성공은 아직 주장하지 않는다.
- 공개 저장소에는 프로젝트 공유 기록만 넣는다. 로컬 전체 회고·개인 자동화/메일/캘린더 내용·Secret·data·검증 로그·백업은 올리지 않는다.
- 로컬 증거 경로는 다른 PC·클라우드에 존재한다고 가정하지 않는다. 필요하면 해당 Windows 환경에서 접근 가능한 입력을 확인한 뒤 필요한 검증을 다시 한다.

## 5. 파일 인덱스
- docs/SESSION_RECAP.md: 최신 개발 회고와 결정·남은 일.
- docs/MAIN_SYNC_20261006.md: 개발 감사·검증 명령·동기화 대상·보존 기록.
- docs/PR211_ROUND4.md: A~K 처리와 실사용 제한.
- 로컬 전용: D:\auto_write\_preflight_evidence\main-sync-20261005\, 독립 Round-4 복제본의 .round4-evidence/. 개인 체크포인트 원문도 로컬에서 보존하며 원격 공유판에 혼입하지 않는다.
