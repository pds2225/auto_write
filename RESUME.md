# RESUME.md — 다른 위치에서 이어가기

> 이 파일과 docs/SESSION_RECAP.md는 GitHub main의 공유 기록이다. TASK 우선순위·상태의 정본은 origin/main:TASK.md다.

## 0. 현재 상태 — 2026-10-06
- 문서 PR #215는 main에 병합됐다. main 기준 SHA는 12b5095f9fbeacb02257b3f169d5924f7fc947a2다. AGENTS.md·CLAUDE.md에 모든 위치에서 fetch 후 원격 TASK→RESUME 필수 확인을 명시했고, GitHub 공유판을 실제 조회했다.
- 현재 codex/round5-fill-fixes는 위 main에서 생성했다. 현재 기간·병합 범위·양옆 라벨 경계와 괄호 실값 보호를 수정했다. 기간 보류는 인라인 동의어 경로에도 적용한다. 커밋: 8284b26(값 채움), 2cb684e8d3310411019656f015b3054451990a9f(PDF mock). 영향 회귀 89 passed/0 failed. 이 코드에서 전체 Windows pytest 1회: 2275 passed/0 failed/5 기존 skipped/23 subtests passed, exit 0. Draft PR #216(https://github.com/pds2225/auto_write/pull/216), main 미병합. 이후 변경은 검증 문서뿐이다.
- 사용자가 이어가기를 확인했다. 검증용 한글 인스턴스는 모두 종료했고 원본 해시·기존 사용자 프로세스 보존 및 소유 프로세스 잔존 없음이 확인됐다.
- 한글 2022 12.0.0.893에서 2026년 IP디딤돌 HWP 사본은 65.609초/2페이지, 2025년 HWPX 사본은 1.578초/2페이지, 변경 추적+문구 삽입 사본은 3.953초/3페이지로 기존 SaveAs[PDF] 성공. FileSaveAsPdf 대안도 추적 사본에서 성공했으나 기존 호출보다 빨라지지 않았다. 120초 타임아웃의 실제 원인은 미재현이며 PDF 코어·120초 제한은 수정하지 않았다. 사용자는 실패 파일 경로를 모른다고 답했다.
- 사용자가 변경 추적 문서의 다른 형식 저장 경고(저장/취소) 화면을 제공했다. 변경 추적 이력을 보존하려면 HWP/HWPX를 유지하라는 안내이며, PDF 출력 목적이면 별도 PDF로 저장할 수 있다. 자동 저장 대기 원인의 후보이나 이 화면만으로 120초 타임아웃 원인이 확정된 것은 아니다. 다음 확인은 경고 후 수동 저장 결과와 정확한 입력 경로다. 이 추가 기록은 로컬 체크포인트이며 아직 push하지 않았다.
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

- 새 요청(2026-10-07): 범용 정부지원사업 신청 엔진 full pipeline을 구현해 draft PR까지 준비. 사용자가 재개를 확인했다. 선행 `codex/engine-coverage-fixes`가 main에 머지되었으면 최신 main에서, 아니면 그 원격 브랜치에서 `codex/engine-full-pipeline`을 분기해야 한다.
- 2026-10-07 재확인: `git ls-remote` 결과 선행 원격 브랜치가 없고 GitHub branch API도 404, 열린 PR 목록에도 없음. 다음 선행 조치: 이전 Codex 세션에서 `codex/engine-coverage-fixes` 변경을 검토·검증하고, fake-only/public-safe 변경만 커밋해 원격 push 및 draft PR 생성(병합 금지). 완료 후 새 작업 세션은 원격 ref와 PR을 재확인해 지정 기준 브랜치에서 `codex/engine-full-pipeline`을 생성한다. `git fetch origin --prune`는 오래된 worktree 메타데이터 삭제 권한 오류로 실패(일반 fetch도 같은 오류). 로컬 `C:\Users\ekth3\.codex\worktrees\engine-coverage-fixes\auto_write`에만 미커밋 변경이 있었다. 그 작업 트리와 root의 기존 변경은 보존한다. 재개 시 fetch 후 원격 PR/ref를 다시 확인한다.
- 구조를 읽음: `app/analyze_docs.py`는 announcement analyzer로 위임하고, `hwpx_submit.py`는 채움·무결성·수용·레이아웃 기능 조합, 기존 그림 삽입/기업 프로필 출처 충돌 처리기가 존재. `samples/` 디렉터리는 현재 없음. 설계 방향: 공고 분석 버그는 analyzer 계층에서 고치고, HWPX submit·acceptance·picture insert·layout/integrity 등 기존 모듈을 조합하는 pipeline을 둔다. 설정 파일로 출처 우선순위·문체·접미사를 제공하고, AI 검토요청서/승인 게이트/항목별 병합·반영 로그·근거 없는 주장 거절을 구현한다. 실제 양식과 개인정보는 로컬 `data/`에서만 다룬다.
- 선행 PR 미병합 중에는 `hwpx_fill.py`, `hwpx_protected_regions.py`, `hwpx_form_diff.py`, `project_service.py::_generate_hwpx_direct` 수정 금지. 추가 테스트는 필수 회귀만 하고 전체 pytest 반복 실행을 피한다.
- 2026-10-07 선행 작업 마무리: 기존 engine-coverage-fixes 작업 트리의 미커밋 변경 보존·diff 검토·필수 회귀 진행 중. 원격 main 12b5095, #214/#216 draft. 자동 maintenance를 끈 fetch 성공. 이번 승인 범위는 공개 가능한 의도 파일만 commit/push하고 main 대상 draft PR 생성까지이며 병합 금지.
