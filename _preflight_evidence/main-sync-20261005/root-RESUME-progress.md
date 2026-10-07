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

## 현재 main 통합 실행 — 2026-10-06 00:21 KST
- 사용자 요청으로 이전 병합 금지 해제. PR #211은 2697bef5aa5e0e30d5defa129a70afa7026cf20d로 병합 완료. 루트 main도 이 SHA로 fast-forward했다.
- 추가 개발 회수 branch: codex/main-sync-20261005, 위치 D:\auto_write\.worktrees\pr211-round4. 야간 호환 조각 3개와 닫힌 #186의 LRule/Finalizer 증거·registry 검사 및 제출 CLI 강제 배선을 최소 회수했다.
- 영향 회귀 70 passed, HWPX/검사 영향 64 passed, 승인 타입/모순 PASS 보완 후 41 passed. 최종 전체 pytest 세션 79135는 마지막 확인 시 86%까지 진행했다. .round4-evidence/main-sync-full-final.xml 및 로그로 최종 종료코드와 통과/실패 수를 확인한다. 추가 회수 branch는 아직 커밋·push·새 PR 생성 전이다.
- 실제 합성 HWPX 제출 CLI smoke는 exit 2, 원본 해시 유지, 값 채움, DRAFT만 생성, 171규칙 증거 JSON 저장 확인. cp949 환경 STEP 3A 한글 CLI는 exit 0·UTF-8 Golden 보고서 일치.
- root/Round-3 미커밋 변경은 SHA-256 백업과 보존용 stash 2개에 남겼다(61d9c745, 288c2558). 원본 stash 9개도 그대로다. 끊긴 worktree 5개 전체는 _preflight_evidence/main-sync-20261005/orphan-worktrees/에 보존 후 원래 위치 main으로 재생성했다.
- 다음: 전체 pytest 결과 확인 → 추가 코드·기록 PR의 docs-gate 통과 후 자동 병합 → 접근 가능한 14개 작업 위치를 최종 main SHA로 맞추고 코드 해시/원격 SHA 대조. 실 한글 Open 실패와 COM hard timeout 제한은 미해결, AW-001 REQUEST_SOLVED=NO.
- 루트의 이전 자동화·개인 체크포인트 원문은 _preflight_evidence/main-sync-20261005/root-RESUME-before-sync.md 및 보존 stash에 있다. 개인 기록·data·.round4-evidence·백업 archive는 코드 PR에 넣지 않는다.
