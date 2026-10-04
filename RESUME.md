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
