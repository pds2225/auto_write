## 요약

HWPX 직접 채움의 기존 변경을 보존·검토하고, 발견된 세 회귀를 수정해 main 대상 draft PR로 공유했습니다. 후속 Windows 실양식 qualification도 수행했습니다.

**PARTIAL / REQUEST_SOLVED=NO. Draft 유지, 병합하지 않습니다.** 전체 pytest는 Windows 한글 COM RPC fatal exception으로 중단됐습니다.

## 변경

- 브랜치 `codex/engine-coverage-fixes`, 기초 구현 커밋 `89dada627414ffb625df6cfe349b291c559da55a`, 후속 검증 문서 커밋 `f567336c221476e3ab81d9caf46af70ca3355ed3`.
- base는 `main`. 미병합 #216 선행 커밋 3개 포함, #214는 별도 draft입니다.
- 기존 커밋은 의도한 코드·합성 테스트·TASK/RESUME/검토 문서 14개 파일만 포함했습니다. 이번 후속 커밋은 공개 검토 문서와 RESUME만 갱신합니다.
- 실제 양식·개인정보·원본·로컬 증거·변환 산출물은 저장소에서 제외했습니다. 테스트 입력은 합성 이름·연락처·특허번호·이미지입니다.
- 기존 테스트의 삭제·assert 완화·skip/xfail 추가 없음.

## 확인

- [x] 최종 지정 회귀(§5 + 신규 합성): **351 passed / 0 failed / 2 skipped**, 31.83초.
- [x] 신규 테스트 첫 실행: **34 passed / 0 failed / 1 skipped**, 4.49초.
- [x] 실양식 qualification 재실행: **1 passed / 0 failed**, 13.08초. `/console/documents/write`, `routing_status=NORMAL`, `_DRAFT` 아님, 안내문 잔존 0, 이미지 1개, PDF 생성 `attempts=1`, form diff intact, geometry delta 0.
- [x] 원본 MD5 `eb680cbcfd61398c694508a003f42b68` 전후 동일, 사용자 Hwp PID 0→0.
- [x] 원본 렌더 4페이지, 작성본 5페이지. 그림이 대상 칸 폭 안에 있고 텍스트를 덮지 않는 것을 연락처 시트로 확인. 서약 내용은 작성본 4–5페이지로 나뉘어 남은 레이아웃 위험입니다.
- [x] 직접 영향 회귀 66 passed. 독립 에이전트 안전 QA PASS.
- [x] `git diff --check` PASS.
- [ ] 전체 `py -3.11 -m pytest -q --tb=short` 1회 실행은 15%에서 `test_gate_faildraft_invariant.py::test_submission_pipeline_fail_doc_forces_draft` 실행 중 Windows fatal exception `0x800706ba`로 종료됐습니다. 스택은 `hangul_default.emit_hangul_file` → `hwp_docx_convert.docx_to_hwp` COM 호출입니다. assertion 실패 여부로 확정된 것이 아니며 전체 PASS로 인정하지 않습니다. 전체 suite는 반복하지 않았습니다.

전체 AUTO APPROVAL 판정과 함수별 변경·제약은 [검토 보고서](docs/ENGINE_COVERAGE_FIXES.md)에 있습니다. PR은 draft 상태이며 병합하지 않습니다.

