# RESUME.md — PR #211 Round-4

## 현재 상태 — 2026-10-05 17:27 KST
- 저장소 pds2225/auto_write, 브랜치 cursor/rhwp-unsupported-lrule-status-6a12.
- 작업 위치 D:\auto_write\.worktrees\pr211-round4 (독립 복제본). 시작 head 360cbf9. 코드/CI 커밋 fefb950, 79a5e03, 38a0048.
- A~G 채움, H PID 조회 분리, I 소유 Hword 정리, J 소유권 실패 시 사용자 객체 보존, K 임시 CI 삭제 반영.
- 분할 날짜 원문 보호 회귀와 PID 조회 실패/다른 세션 Automation/기존 사용자 객체 보존 회귀 추가.
- 전체 pytest 2206 passed, 0 failed, 5 skipped, 23 subtests passed (958.21초, exit 0). 이전 실패 12건 해소. COM 회귀 두 파일 43 passed.
- 실제 한글 2022 합성 DOCX→HWP smoke는 Open 실패(ok=False). 입력 이름 변경/해시 보존/새 Hwp·Hword 잔존 없음 확인. 실제 변환 성공 또는 원본 양식 9건 E2E 완료로 보고하지 않는다.
- 소유 PID를 확인하지 못하면 watchdog이 COM operation 자체를 반환시키지 못하는 hard timeout 한계가 남아 있다.

## 제약
- 같은 draft PR #211에 commit/push 및 Round-4 본문 갱신. 새 PR·merge·force push 금지 유지.
- 테스트 삭제/약화/추가 skip 금지. rhwp 기본 OFF, L050 gap/mechanized=false 유지.
- 사용자 Hwp/Hword 종료 금지. 조회 실패·기존 사용자 객체·소유 미확인 PID는 문서 Open/Visible 변경 전에 차단.
- .round4-evidence/ 및 검증용 data/는 커밋하지 않는다. 데이터 489개는 기존 D:\auto_write\data에서 복사했으며 해시 일치 확인.
- 루트·Round-3·다른 worktree/stash 보존. 루트 RESUME.md의 다른 자동화 기록은 별도다.

## 다음 액션
1. 문서/TASK 기록 커밋 후 같은 origin 브랜치에 push하고 PR #211 Round-4 섹션 갱신, 새 head와 checks 확인.
2. 새 head에서 5차 실제 한글 2022/원본 양식 검증. DOCX Open 실패와 소유 미확인 시 hard timeout 한계를 별도 해결한다.

## 증거와 인덱스
- 항목별 결과 docs/PR211_ROUND4.md. 로그/JUnit/smoke/해시 증거 .round4-evidence/ (로컬 전용).
- 이전 체크포인트는 .round4-evidence/RESUME-before-finalize.md에 보존.
- 공식 TASK 정본 origin/main:TASK.md. 작업 브랜치 기록은 main 머지 전 제안이며 AW-001은 진행 중/REQUEST_SOLVED=NO.
