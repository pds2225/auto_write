# HWPX 직접 채움 커버리지 — 선행 작업 검토

상태: PARTIAL / REQUEST_SOLVED=NO. 이번 작업은 기존 변경 보존·검토·회귀 확인 후 main 대상 draft PR 공유까지다. 병합하지 않는다.

## 기준과 변경 범위

- 브랜치: `codex/engine-coverage-fixes`. 선행 기준: `codex/round5-fill-fixes`의 `2f630a6`. 원격 main: `12b5095`.
- 사용자 최신 요청에 따라 PR base는 main이다. 미병합 #216의 선행 커밋 3개도 PR diff에 포함된다. #214는 별도 draft이며 이 작업에 합치지 않는다.
- 기존 작업 트리의 production 변경 8개, TASK 변경, 신규 서비스 1개 및 테스트 2개를 보존한다. 기존 테스트의 삭제·assert 완화·skip/xfail 추가는 없다.
- 실제 양식·개인정보·원본·검증 로그·PDF/HWPX 산출물은 커밋하지 않는다. 신규 테스트의 입력은 합성 이름·연락처·특허번호와 생성 이미지다.

## 구현과 재검토

| 항목 | 주요 위치 | 내용 및 제한 |
|---|---|---|
| D1 서술 | `hwpx_protected_regions.py::find_guidance_value_targets`, `hwpx_fill.py::commit_guidance_value_writes`, `hwpx_narrative_source.py` | SHA·좌표·원문을 재검증하는 셀 grant. DOCX 제목 정확 일치 본문 사용. 셀 밖 XML 보존. |
| D2 조건 | `hwpx_fill.py::_conditional_guidance_value` | 등록번호/예비창업·팀 사실을 근거로 결정. 판단 불가 시 미기입. |
| D3 반복 | `hwpx_protected_regions.py::document_parts`, `hwpx_narrative_source.py::direct_cell_plan` | 제목 경계별 아이디어명·신청자명(팀명) fan-out. 같은 파트 중복 차단. 기존 제목 없는 섹션 중복 진단 유지. 기존 T02 grant 계약은 그대로 유지. |
| D4 기록행 | `hwpx_protected_regions.py::find_record_row_targets` | 헤더·열 좌표와 입력 개수 정확 일치. 행 추가 없이 overflow 보고. |
| D5 그림 | `hwpx_pic_insert.py::insert_cell_reference_images` | 제공된 DOCX inline 이미지만 승인된 서술 칸에 삽입. 폭 제한·manifest 등록·문단 고유 ID. 생성형 이미지 없음. |
| D5 PDF | `hwp_docx_convert.py::_com_stage_timeout`, `submission_gates.py::_try_hangul_com_pdf` | Dispatch 환경설정 10–180초. timeout만 5초 후 1회 재시도. 기존 소유 PID 정리 및 SaveAs 120초 유지. |
| D6 비교 | `hwpx_form_diff.py::_compare_roots`, `project_service.py::_generate_hwpx_direct` | 선택기호·값 문단·안내문 교체 별도 집계. 일반 `as_dict()` 키는 기존 exact-key 계약 보존, 신규 카운터는 route의 `form_diff_allowed`로 보고. |

검토 중 발견한 회귀 3건은 기존 테스트를 유지하여 수정했다. 임의 `PART_VALUE` 답안이 P14 보류를 우회하지 못하도록 신규 blank-cell 경로를 요청된 반복 라벨 2개로 제한했다. 제목 없는 섹션의 기존 중복 잔여 진단을 보존했다. 독립 QA에서 지적한 그림/캡션 문단 ID 중복도 고유 ID 발급과 합성 회귀 assert 추가로 해결했다.

## 검증

- 초기 지정 회귀: 343 passed / 7 failed / 3 skipped, 50.37초. 실패 4건은 작업 트리에 비공개 실제 검증 양식이 없어 발생; 원본을 수정하지 않고 ignored data에 로컬 복사했다. 실패 3건은 위 회귀 수정 대상이었다.
- 수정 후 직접 영향 검증: `py -3.11 -m pytest app/tests/test_hwpx_engine_coverage_synthetic.py app/tests/test_p14_analyzer_wire.py app/tests/test_hwpx_repeated_row_residual.py app/tests/test_hwpx_safety_golden10.py app/tests/test_hwpx_t02_auto.py app/tests/test_hwpx_guidance_narrative.py app/tests/test_hwpx_merged_value.py -q --tb=short` → 66 passed, 13.37초.
- 전체 Windows suite: `py -3.11 -m pytest -q --tb=short` 1회 실행. 보존된 출력은 실제로 **15%에서 중단**됐으며, pytest 요약·exit code 없이 Windows fatal exception `0x800706ba`가 발생했다. 스택은 `test_gate_faildraft_invariant.py::test_submission_pipeline_fail_doc_forces_draft` 실행 중 `hangul_default.emit_hangul_file` → `hwp_docx_convert.docx_to_hwp` COM 호출에 있다. assertion 실패로 확정된 것은 아니며, 한글 COM/RPC 환경 중단으로 분류한다. 전체 PASS로 인정하지 않았고 전체 suite는 반복하지 않았다.
- 독립 에이전트 읽기 전용 QA: 안전·권한/소유권·변경범위·가짜 샘플·기존 테스트 보존·문단 ID 수정 PASS. 실양식 렌더 미확인으로 전체 판정 PARTIAL.
- `git diff --check`: PASS.

## 미충족 및 다음 작업

- 실제 양식 qualification은 아래 후속 검증에서 PASS했다. 한글 GUI에서의 별도 시각 확인은 수행하지 않았다.
- D3는 기존 T02 중복 보호를 유지하는 보수적 확장이다. 모든 반복 라벨에 대한 legacy grant fan-out 완료를 주장하지 않는다.
- `as_dict()` 신규 카운터 미노출은 호환성 제한이다. 기존 테스트 exact-key 계약 변경은 별도 합의가 필요하다.
- 전체 AUTO APPROVAL 조건을 전부 충족하지 않았으므로 draft 유지. 후속 full pipeline 세션은 이 원격 브랜치/PR의 실제 상태를 다시 확인한 뒤 진행한다.

## 최종 회귀와 공개 게이트

- §5 지정 회귀 + 합성 엔진 테스트: **351 passed / 0 failed / 2 skipped**, 31.83초. 명령은 `py -3.11 -m pytest` 뒤 §5의 24개 파일을 지정하고 `-q --tb=short`로 실행했다. 기존 skipped를 삭제하거나 완화하지 않았다.
- 신규 2개 테스트 최초 실행: `py -3.11 -m pytest app/tests/test_hwpx_engine_coverage_synthetic.py app/tests/test_hwpx_mapo_real_qualification.py -q --tb=short` → **34 passed / 0 failed / 1 skipped**, 4.49초. 당시 지정 data/env 경로에 실양식이 없어 qualification이 skip됐다.
- 후속 실양식 qualification: `AUTO_WRITE_MAPO_FORM`에 로컬 원본 사본을 지정해 `py -3.11 -m pytest app/tests/test_hwpx_mapo_real_qualification.py -q -vv --tb=short` → **1 passed / 0 failed**, 13.08초. 테스트 입력은 합성 참고 DOCX(홍길동 등 가짜 값)이며 원본 양식은 읽기 전용으로 사용했다. 원본 MD5 `eb680cbcfd61398c694508a003f42b68` 전후 동일, 사용자 Hwp PID 0→0. 출력은 `routing_status=NORMAL`, `_DRAFT` 아님, 안내문 잔존 0, 이미지 1개, PDF 생성 성공(attempts=1), form diff intact 및 geometry delta 0이었다. 실제 양식은 저장소에 포함하지 않았다.
- 렌더 비교: 원본 4페이지, 작성본 5페이지. 안내문 대체와 서술/이미지 삽입으로 1페이지가 늘었고 서약 내용이 작성본 4–5페이지에 걸친다. 이미지가 텍스트를 덮지 않고 대상 칸 폭 안에 들어간 것을 PDF 연락처 시트에서 확인했다. 페이지 증가와 서약 분할은 남은 레이아웃 위험으로 기록한다.
- 직접 영향 66 passed는 최소 수정 검증이고, 위 351 passed는 최종 제품 코드와 그림 ID 수정에 대한 지정 회귀 결과다.
- 공개 stage 검사: 14개 의도 파일. 실제 문서/이미지/로그 경로 0, Secret 패턴 탐지 0. 원본/개인자료와 로컬 증거는 ignored data 또는 원래 위치에 보존했다.

| AUTO APPROVAL 조건 | 판정 | 근거 |
|---|---|---|
| D1–D6 전체 구현 | FAIL | 보수적 반복 라벨 확장 및 as_dict 호환성 제한; 전체 실사용 합격 아님 |
| 신규 gate 전부 | PASS | 합성 34 PASS, 실양식 qualification 후속 1 PASS |
| 독립 QA | PASS | 별도 에이전트 diff 재검토: 안전·권한·소유권·공개범위·기존 테스트 보존 및 그림 문단 ID 수정 확인 |
| 지정 회귀 + 전체 pytest | FAIL | 지정 회귀 351 PASS, 전체 suite 중단·종료 수치 미확인 |
| 실제 qualification | PASS | 원본 4p→작성본 5p, 안내문 0, 이미지 1, PDF attempts=1, 원본 해시/PID 보존. 서약 페이지 분할은 위험으로 보고 |
| BLOCKER=0 | FAIL | 전체 suite가 15%에서 Windows 한글 COM RPC fatal exception으로 종료되어 전수 회귀 PASS 증거가 부족 |
| 기존 테스트 약화 없음 | PASS | 기존 테스트 diff 0; 추가 테스트의 assert만 보강 |
| 변경 범위 | PASS | production 변경은 원 지시의 허용 파일 내. main PR은 #216 선행 커밋도 포함 |
| Git 충돌 없음 | PASS | main은 선행 브랜치의 조상, 작업 트리 conflict 없음. #214는 별도 미병합 상태이며 통합 후 검증은 별도 |
| P0/F01/writer 회귀 | PASS | §5 지정 회귀에 포함되어 통과 |

PR은 draft로 유지하며 병합하지 않는다. 표적 재실행을 추가하지 않은 이유는 보존된 full-suite 로그가 assertion 실패가 아니라 Windows 프로세스를 종료한 한글 COM RPC fatal exception을 명확히 가리키기 때문이다. 전체 suite 완료는 아직 확인되지 않았다.
