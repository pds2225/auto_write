# RESUME.md — 다른 위치에서 이어가기

> 이 파일과 docs/SESSION_RECAP.md는 GitHub main의 공유 기록이다. TASK 우선순위·상태의 정본은 origin/main:TASK.md다.

## 0-A. 진행 중 — 제출 마감 기능 7종 (2026-10-11, 브랜치 claude/submit-finish, 기준 main 1f0afef)
- 위치: `D:\auto_write\.worktrees\submit-finish`, 코드는 `app/auto_write/services/submit_finish/`. Draft PR 대상(병합 금지).
- 완료(합성 데이터 단위·통합 테스트): F1 직인(팀원은 사용자 승인 시에만)·F2 체크박스·F3 본문·F4 이미지·F5 첨부 가림·F6 PDF 변환/합본/파일명·F7 구조검증/Visual QA/보고서, 그리고 `pipeline.py` 오케스트레이터 + `pdf_checks.py` PDF 레이아웃 검사(결함 주입 테스트 포함). submit_finish 테스트 71 passed.
- 2026-10-12 실환경 검증(마포 참가신청서 원본 양식 + 실제 한글 COM + 실제 AI 시각 검수 1회, 수동 제출본과 비교): 쪽수 12=12, 본문 문자 유사도 97%, 직인 3곳·동의함 2곳·예비창업자·날짜·초본 가림 일치. 찾아서 고친 일반 결함(전부 가짜 데이터 회귀 테스트 추가): ①떠 있는 표 2개가 한 문단에 있으면 본문이 서약서 뒤로 밀림→표별 문단 분리 ②원본에서 새 쪽에서 시작하던 제목 쪽 시작 고정 ③값이 길어 쪽 넘침→빈 문단 정리(13→12쪽) ④직인이 표식과 떨어짐→렌더 실측 보정+대표자 역할 바인딩 ⑤탭이 낀 서명 줄 이름·날짜 기입 ⑥문서 순서≠배치 순서 검출 ⑦가림 미확정 첨부가 신청서 쪽 AI 전송까지 막음→쪽 단위 허용 ⑧주민번호 앞자리 오탐(날짜·이미 가림) ⑨■ 글머리 체크박스 오탐·그림 캡션 제목 오탐.
- 같은 날 5개 양식(킥스업·마켓게이트 v2.2/대구달구벌 서식·STAR·은평·수원 멘토) 빈 원본→엔진 채움→최종본 라벨 기준 비교: 예시색 안내문(파랑·빨강, 빨강은 지시문일 때만)·한컴 기호 체크박스 글리프(U+1943)·빈 불릿 자리표시자·세로형 서술 블록(라벨 행 아래 전폭 칸)·'라벨: 안내문' 줄 채움을 일반 규칙으로 추가(hwpx_fill·hwpx_protected_regions·hwpx_form_diff). 채움률(라벨 인접 칸 기준) 킥스업 0.64→0.86, 마켓게이트 0.21→0.41. 양식 대조(FORM_INTACT)·읽기 순서 검사는 5개 양식 모두 통과. 보고서·산출물은 로컬 %TEMP%\submit_finish_mapo, %TEMP%\submit_finish_multi(개인정보라 커밋 안 함).
- 남음: 동의서처럼 줄이 쌓인 서명 구간의 직인은 줄 간격(≈7mm) 안으로 제한(수동본은 17mm로 윗줄을 덮음) · 팀원 도장은 사용자 승인 전 자동 기입 안 함 · 라벨 뒤 체크박스('본점 □ 지점 □')·기간·반복 표 중복 라벨은 미지원 · G밸리 양식 미검증 · 전체 pytest 결과는 PR 본문 참고.

## 0. 현재 상태 — 2026-10-07
- 최신 작업: `codex/engine-coverage-fixes`의 기존 미커밋 엔진 변경을 보존·검토하고 main 대상 draft PR로 공유한다. 기준 HEAD는 #216의 `2f630a6`, 원격 main은 `12b5095`. 병합하지 않는다. 아래 Round-5 검증 수치는 이전 작업 기록이다.
- 독립 안전 QA PASS. 임의 빈칸 답안의 P14 보류 우회·제목 없는 구역 중복 진단 회귀·새 그림 문단 ID 중복을 최소 수정했다. 기존 테스트 수정 없음. 실제 양식·개인정보·로컬 증거는 커밋에서 제외한다.
- 직접 영향 검증 66 passed. 지정 회귀 351 passed/2 skipped, 신규 합성 34 passed/실양식 1 skipped. 후속 실제 마포 양식 qualification은 합성 참고자료로 1 passed: 원본 4페이지→작성본 5페이지, 안내문 잔존 0, 이미지 1, PDF attempts=1, 원본 MD5와 사용자 Hwp PID 보존. 서약 내용이 2페이지로 나뉘는 레이아웃 위험은 기록했다. 전체 Windows pytest는 15%에서 `test_gate_faildraft_invariant.py::test_submission_pipeline_fail_doc_forces_draft` 중 한글 COM RPC fatal exception(0x800706ba)으로 종료되어 전체 합격은 미확인이다. 전체 요청 상태는 PARTIAL/REQUEST_SOLVED=NO. 상세: `docs/ENGINE_COVERAGE_FIXES.md`.
- 다음: draft PR과 원격 브랜치를 확인한 뒤 후속 세션이 `codex/engine-full-pipeline` 기준을 선택한다. 이번 PR의 생성은 병합 승인이나 전체 실사용 합격을 뜻하지 않는다.
- 문서 PR #215는 main에 병합됐다. main 기준 SHA는 12b5095f9fbeacb02257b3f169d5924f7fc947a2다. AGENTS.md·CLAUDE.md에 모든 위치에서 fetch 후 원격 TASK→RESUME 필수 확인을 명시했고, GitHub 공유판을 실제 조회했다.
- 현재 codex/round5-fill-fixes는 위 main에서 생성했다. 현재 기간·병합 범위·양옆 라벨 경계와 괄호 실값 보호를 수정했다. 기간 보류는 인라인 동의어 경로에도 적용한다. 커밋: 8284b26(값 채움), 2cb684e8d3310411019656f015b3054451990a9f(PDF mock). 영향 회귀 89 passed/0 failed. 이 코드에서 전체 Windows pytest 1회: 2275 passed/0 failed/5 기존 skipped/23 subtests passed, exit 0. Draft PR #216(https://github.com/pds2225/auto_write/pull/216), main 미병합. 이후 변경은 검증 문서뿐이다.
- 사용자가 이어가기를 확인했다. 검증용 한글 인스턴스는 모두 종료했고 원본 해시·기존 사용자 프로세스 보존 및 소유 프로세스 잔존 없음이 확인됐다.
- 한글 2022 12.0.0.893에서 2026년 IP디딤돌 HWP 사본은 65.609초/2페이지, 2025년 HWPX 사본은 1.578초/2페이지, 변경 추적+문구 삽입 사본은 3.953초/3페이지로 기존 SaveAs[PDF] 성공. FileSaveAsPdf 대안도 추적 사본에서 성공했으나 기존 호출보다 빨라지지 않았다. 120초 타임아웃의 실제 원인은 미재현이며 PDF 코어·120초 제한은 수정하지 않았다. 사용자는 실패 파일 경로를 모른다고 답했다.
- 개발 main 통합 요청은 완료됐다. PR #211·#212 병합, 제품 코드 검증 기준 b0e8eedebc16c6d878d76809b8eeafba0d43a50b. 당시 접근 가능한 14개 작업 위치의 HEAD·제품 코드 해시 일치를 확인했다.
- 세션 마무리의 최신 개발 회고·재개 정보를 이제 원격 공유판으로 관리한다. 회고: [docs/SESSION_RECAP.md](docs/SESSION_RECAP.md). root SESSION_RECAP.md는 로컬 전체 회고이며 Git에서 제외되어 있다.
- 아직 실제 한글 2022 DOCX Open 실패·소유 PID 미확인 시 COM hard timeout 한계가 남아 있다. AW-001 REQUEST_SOLVED=NO. Git 통합 성공을 실제 변환 성공으로 보고하지 않는다.

## 1. 다른 PC·클라우드에서 빠른 재개
저장소를 복제한 폴더에서 다음 명령으로 최신 원격 지시와 기록을 먼저 읽는다. 현재 작업 위치나 브랜치가 달라도 조회할 수 있다.

```powershell
git status --short --branch
git fetch origin --prune
git show origin/main:TASK.md
git show origin/main:RESUME.md
git show origin/main:docs/SESSION_RECAP.md
```

미커밋 변경을 보존하고 현재 브랜치를 확인한 뒤 main을 최신화한다. 현재 브랜치가 main이고 충돌할 변경이 없으면 `git merge --ff-only origin/main`을 사용한다. 자동 pull·reset·clean·force push는 하지 않는다.

## 2. 완료·검증
- 호환 경로·UTF-8·제출 검사 복구: 735531f, fake COM 테스트 조회 격리: a7c369c, 관련 기록: c015e34.
- 전체 pytest는 2217 passed/8 failed/5 skipped/23 subtests passed. 가짜 COM의 실제 프로세스 목록 의존을 격리한 뒤 실패 8건 포함 영향 회귀 54 passed/0 failed, 소유권 회귀 21 passed/0 failed. 합산 대상 2225 passed/남은 실패 0이며 두 번째 전체 실행은 아니다. 제품 보호 코드는 유지했다.
- 합성 HWPX 제출 CLI: 원본 해시 보존·값 채움·DRAFT만 생성·171규칙 증거 저장. cp949 STEP 3A CLI: exit 0·UTF-8 Golden 보고서 일치.
- 기존 stash 9개와 보존용 stash 4개, 브랜치 ref·원본 데이터·깨진 worktree 원문을 보존했다. 개발 감사·항목별 결과는 docs/MAIN_SYNC_20261006.md와 docs/PR211_ROUND4.md를 따른다.

## 3. 다음 액션
1. 다른 위치에서는 원격 main의 TASK→RESUME를 먼저 읽은 뒤, PR #216의 codex/round5-fill-fixes 브랜치와 이 기록·docs/ROUND5_FILL_FIXES.md를 확인한다. 로컬 변경을 보존하고 자동 pull/reset/clean을 하지 않는다.
2. PDF 타임아웃은 정확한 실패 입력 확보 후 한글 2022에서 재현해야 한다. 두 값 채움 수정과 PDF 미재현을 구분한다. Round-5 전체 요청은 PARTIAL/REQUEST_SOLVED=NO이며 main에 병합하지 않는다.
3. 기존 실제 DOCX Open 실패·소유 미확인 hard timeout 한계와 L050 gap을 유지한다. 전체 pytest를 추가 재실행하지 않는다.

## 4. 유지할 제약
- 추가 테스트는 꼭 필요할 때만 한다. 기존 성공 assertion·skip·소유권 보호를 약화하지 않는다. rhwp 기본 OFF, L050 gap 유지.
- 사용자 Hwp/Hword 종료·원본 덮어쓰기·main 직접 push·force push 금지. 실제 변환·원본 양식 9건 E2E 성공은 아직 주장하지 않는다.
- 공개 저장소에는 프로젝트 공유 기록만 넣는다. 로컬 전체 회고·개인 자동화/메일/캘린더 내용·Secret·data·검증 로그·백업은 올리지 않는다.
- 로컬 증거 경로는 다른 PC·클라우드에 존재한다고 가정하지 않는다. 필요하면 해당 Windows 환경에서 접근 가능한 입력을 확인한 뒤 필요한 검증을 다시 한다.

## 5. 파일 인덱스
- docs/SESSION_RECAP.md: 최신 개발 회고와 결정·남은 일.
- docs/MAIN_SYNC_20261006.md: 개발 감사·검증 명령·동기화 대상·보존 기록.
- docs/PR211_ROUND4.md: A~K 처리와 실사용 제한.
- docs/ROUND5_FILL_FIXES.md: Round-5 항목별 수정·전체 테스트·실제 PDF 결과·남은 입력 제한.
- 로컬 전용: D:\auto_write\_preflight_evidence\main-sync-20261005\, 독립 Round-4 복제본의 .round4-evidence/. 개인 체크포인트 원문도 로컬에서 보존하며 원격 공유판에 혼입하지 않는다.
- Round-5 로컬 증거: D:\auto_write\_preflight_evidence\round5-20261006\ (문서 공유 조회 증거·영향 회귀 로그·실제 PDF 저장 기록). 이 폴더는 커밋하지 않는다.
