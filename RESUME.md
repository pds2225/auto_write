# RESUME.md — 개발 main 통합·위치별 동기화

## 현재 상태 — 2026-10-06
- 사용자 요청: 「ㅇㅇ 지금까지 개발한거 모두 메인반영해서 위치관계없이 동기화시켜」. 이전 PR #211 draft·병합 금지 제약은 이 요청으로 해제됐다. 추가 테스트는 꼭 필요한 영향 범위만 실행한다.
- 저장소 pds2225/auto_write, 공식 TASK 정본 origin/main:TASK.md. PR #211은 2697bef5aa5e0e30d5defa129a70afa7026cf20d로 병합 완료. Round-4 기록은 docs/PR211_ROUND4.md.
- 추가 통합 위치 D:\auto_write\.worktrees\pr211-round4, branch codex/main-sync-20261005. 호환·UTF-8·제출 증거 검사 커밋 735531f, COM 테스트 조회 격리 a7c369c.
- 전체 pytest: 2217 passed/8 failed/5 skipped/23 subtests passed. 가짜 COM이 실제 사용자 Hwp 목록에 의존하던 실패 8건 포함 54 passed/0 failed, 소유권 회귀 21 passed/0 failed로 재검증했다. 전체+재검증 합산 2225 passed/남은 실패 0이며 두 번째 전체 실행은 아니다. 전체 실행 뒤 제품 코드 해시는 동일하다.
- 실제 합성 HWPX 제출 CLI: 원본 보존·값 채움·DRAFT만 생성·171규칙 증거 저장. cp949 STEP 3A CLI: exit 0·UTF-8 Golden 보고서 일치.
- 로컬 ref 18개·원본 stash 9개·추가 원격 ref 21개·끊긴 작업 폴더 5개 대조 완료. 누락 조각을 회수했다. 감사·검증·위치 목록: docs/MAIN_SYNC_20261006.md.

## 보존과 제약
- root/Round-3 미커밋 변경·개인 체크포인트·끊긴 worktree 전체: D:\auto_write\_preflight_evidence\main-sync-20261005\ 및 stash 61d9c745·288c2558. 원본 stash 9개와 개발 branch ref는 삭제하지 않았다.
- .round4-evidence/·검증용 data/·_preflight_evidence/·개인 산출물은 커밋하지 않는다. 로그·JUnit·합산 검증 JSON은 독립 복제본의 .round4-evidence/에 있다.
- 실제 한글 2022 DOCX Open 실패·소유 PID 미확인 시 COM hard timeout 한계는 미해결이다. 실제 변환 성공·원본 양식 9건 E2E 완료로 보고하지 않는다. AW-001 REQUEST_SOLVED=NO, rhwp 기본 OFF, L050 gap 유지.
- 사용자 Hwp/Hword 종료·force push·main 직접 push·원본 삭제 금지.

## 다음 확인
1. 추가 통합 PR의 docs-gate와 main 병합 확인. 14개 접근 가능한 작업 위치를 최종 origin/main SHA로 맞추고 HEAD·코드 해시·보존 stash를 대조한다.
2. 다른 PC·클라우드는 GitHub main을 fetch하고 자기 변경을 보존하여 최신화한다. 접근하지 못한 checkout을 완료라고 말하지 않는다. Git 통합 뒤 남은 실제 한글 변환·COM 시간제한을 별도 해결한다.
