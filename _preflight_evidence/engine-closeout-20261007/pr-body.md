## 요약

HWPX 직접 채움에서 안내문·서술·파트별 반복 라벨·기록행·사용자 제공 이미지·PDF 재시도·양식 비교의 기존 미커밋 변경을 보존하고 검토했습니다. 임의 빈칸 답안의 P14 보류 우회, 제목 없는 구역의 중복 진단 회귀, 새 이미지 문단 ID 중복을 최소 수정했습니다.

**PARTIAL / REQUEST_SOLVED=NO. Draft 유지, 병합하지 않습니다.**

## 변경

- 브랜치 `codex/engine-coverage-fixes`, head `89dada627414ffb625df6cfe349b291c559da55a`.
- 사용자 최신 요청으로 base는 `main`. #216의 `2f630a6` 위 작업이므로 미병합 #216 선행 커밋 3개도 포함합니다. #214는 별도 draft입니다.
- 이번 커밋은 의도한 코드·합성 테스트·TASK/RESUME/검토 문서 14개 파일만 포함합니다.
- 신규 샘플은 합성 이름·연락처·특허번호·생성 이미지입니다. 실제 양식·개인정보·원본·로컬 증거·변환 산출물은 제외했습니다.
- 기존 테스트 수정·삭제·assert 완화·skip/xfail 추가 없음.

## 확인

- [x] 최종 지정 회귀(§5 + 신규 합성): **351 passed / 0 failed / 2 skipped**, 31.83초.
- [x] 신규 테스트 2개: **34 passed / 0 failed / 1 skipped**, 4.49초. 실양식 skip은 지정 data/env 경로의 입력 부재입니다.
- [x] 최소 수정 직접 영향: **66 passed**, 13.37초.
- [x] 별도 에이전트 독립 QA: 권한·원본/소유 PID 보존·공개 범위·기존 테스트 계약·문단 ID 수정 PASS.
- [x] `git diff --check`, conflict marker 및 공개 stage 검사 통과.
- [ ] 전체 `py -3.11 -m pytest -q --tb=short`는 1회 실행했으나 세션 중단 후 56% 로그만 남아 최종 요약/exit code가 없습니다. 실패 표시 1건과 COM RPC 진단이 있어 전체 PASS로 인정하지 않습니다. 전체 suite 반복 실행 없음.
- [ ] 실제 Windows HWPX qualification·원본 페이지 기준선·이미지 시각 렌더 검증 미완료.

일반 `FormDiffReport.as_dict()` 키는 기존 exact-key 계약을 유지합니다. 새 카운터는 route의 `form_diff_allowed`에서 제공합니다. 반복 라벨 확장은 보수적인 셀 경로이며 기존 T02 중복 보호를 약화하지 않았습니다.

전체 AUTO APPROVAL 10조건과 함수별 변경·검증 명령·남은 제한은 [검토 보고서](docs/ENGINE_COVERAGE_FIXES.md)에 있습니다. 후속 full pipeline 작업은 이 원격 브랜치/PR을 재확인한 뒤 진행해야 합니다.