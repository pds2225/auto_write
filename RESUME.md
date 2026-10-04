# RESUME.md — PR #211 Round-3

## 현재 상태
- 사용자 지정: pds2225/auto_write draft PR #211, cursor/rhwp-unsupported-lrule-status-6a12. 시작 SHA aa15a6aea5e8282af6dd3e9cfaa1d474a3d4ab5d.
- 작업 공간: D:\auto_write\.worktrees\pr211-round3. 루트 main의 기존 변경, stash, 다른 worktree 보존.
- 원격 PR/branch/main SHA 확인. fetch는 기존 broken backup ref 때문에 실패; 원격 직접조회로 교차 확인.
- 결함 1(DIPS 사업명→지원기관)은 f72e7aa/aa15a6a에 해결됨. 2~7 수정 진행.

## 제약
- 같은 브랜치에 항목별 검증 후 commit+push. 새 PR/merge 금지.
- 테스트 삭제/약화/추가 skip 금지. 범위 최소. L050 mechanized=false 유지.
- rhwp 기본 OFF, AUTO_WRITE_ENABLE_RHWP=1만 ON.
- 사용자 Hwp 종료 금지; 소유 PID만 종료. 원본 데이터 보존.

## 다음 액션
1. 2 예시+안내/날짜/팀명 등 → 3 미입력/동의어/서술 → 4 편집 문단 linesegarray 범위 수정.
2. 5 PDF 대화상자·단계별 hard timeout → 6 Windows PID helper → 7 동시 COM 소유권.
3. 합성 HWPX/COM mock 회귀와 python -m pytest app/tests -q 실행, 결과·새 head 한국어 보고.

## 인덱스
- 정본: app/core/docx/services/hwpx_fill.py, hwp_docx_convert.py, submission_gates.py.
- app/auto_write/services는 호환 모듈. 기존 회귀: app/tests/test_hwpx_round2_fill.py, test_hwp_docx_convert.py.
- 이전 루트 체크포인트 보존: _preflight_evidence/pr211-round3/RESUME-before-round3.md.
- TASK 공식 정본: origin/main:TASK.md (AW-001 진행 중). 이전 주간 검토의 타 저장소 조치는 이번 범위에 없음.

## 재개 상태 확인 — 2026-10-04 18:35 KST
- 현재 요청: resume. 복원 요약과 재개 순서를 제시했으며, 재개 방향 확인 대기. 이번 턴 제품 코드·테스트 수정 없음.
- 라이브 확인: repo D:\auto_write, origin https://github.com/pds2225/auto_write.git. main/origin/main=6ed289fd4d7875f143436d966073177a2837528b. draft PR #211은 OPEN·미병합, 원격 head=360cbf99f6fda4008d790eb67976da0028b9438d.
- 기존 Round-3 작업 트리 HEAD=aa15a6a. 원격은 그 이후 결함 2~7 및 CI 관련 12개 커밋이 추가됨. 위의 '2~7 수정 진행'은 이전 체크포인트이며, 새 원격 코드 검증 결과를 뜻하지 않음.
- 미커밋 보존: .worktrees\pr211-round3의 RESUME.md, TASK.md, hwpx_submit.py, hwpx_fill.py; 미추적 test_hwpx_round3_fill.py, docs/PR211_ROUND3.md. 루트 RESUME.md·_preflight_evidence 및 다른 worktree·stash도 보존.
- D:\aw_pr211은 원격 head 360cbf9의 detached worktree이며 조회 당시 clean. 이전 HANDOFF.md/RESUME.md의 과거 완료·대기 기록을 현재 증거로 사용하지 않음.
- git fetch origin --prune는 exit 0. 오래된 worktree 메타데이터 삭제 권한 경고 있음; 별도 정리/복구 미실행. GitHub API와 git ls-remote로 PR/head/main 교차 확인. .session/closeout_due.json due=false.
- 다음 1: 원격 최신 코드와 기존 미커밋 변경을 항목별 대조해 이미 반영된 수정과 잔여 수정을 구분한다. 기존 변경 삭제·덮어쓰기 금지.
- 다음 2: 최신 head의 영향 회귀 및 Windows 한글 실제 사용자 경로를 검증하고, 남은 blocker만 같은 PR 브랜치에서 수정한다. 새 PR·merge 금지 유지. 이번 턴 테스트·실사용 검증 미실행.