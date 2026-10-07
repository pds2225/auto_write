# PR #211 Round-3 修正 기록

시작: `aa15a6aea5e8282af6dd3e9cfaa1d474a3d4ab5d`.
브랜치: `cursor/rhwp-unsupported-lrule-status-6a12`. draft 유지, 새 PR/merge 금지.

| 항목 | 수정/검증 상태 |
|---|---|
| 1 | f72e7aa/aa15a6a의 DIPS 지원기관 오기입 회귀 유지 |
| 2 | 예시+안내 혼합 칸, 명시적 예시, 날짜, onlab 팀명/서약 빈칸. 합성 HWPX와 authorization 범위 회귀 12 passed |
| 3 | 미입력/동의어/서술 입력 확인 예정 |
| 4 | 편집 문단 linesegarray 범위 수정 예정 |
| 5 | PDF 대화상자/단계별 hard timeout/사유 기록 예정 |
| 6 | Windows PID 조회 helper 수정 예정 |
| 7 | 동시 COM 인스턴스 소유권 수정 예정 |

실행 위치: `D:\auto_write\.worktrees\pr211-round3`.
검증: `python -m pytest app/tests/test_hwpx_round3_fill.py app/tests/test_hwpx_p03_exact_scope.py app/tests/test_hwpx_p14_authorization.py -q` (별도 basetemp 사용).
실값, 주변 안내, 원본 ZIP을 보호하며 Analyzer가 쓴 동일 라벨의 후속 경로는 예시칸에만 제한.
전체 pytest 및 실 한글 렌더 검증은 아직 완료하지 않음. L050 mechanized=false, rhwp 기본 OFF 유지.
