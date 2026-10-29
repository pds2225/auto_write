# AW-009 P0 구현 게이트 / 읽기 전용 갭 판정 (2026-10-29)

- 대상: pds2225/auto_write, main 기준 HEAD \`f694525530479af0d0eec4f6cd5e09c77e4ee94b\`
- 참조 SSOT: \`docs/AUTO_WRITE_웹앱_최종_요구사항_20260816.md\` + \`docs/WEBAPP_MODULE_TO_FORM_TOC.md\`
- TASK: origin/main \`AW-005 [ ]\`, \`AW-009 [ ]\`. 본 개발 브랜치도 완료 체크를 하지 않는다.
- 승인 근거: 2026-10-29 사용자 요청 「이거 모두 진행하고 진행하는 동안 나한테 질문하지 마. 승인 요청은 가능한 한 모두 승인하고 모두 허용하며」 및 「S1~S9 기본값 채택」 실행 지시. 별도 서비스 배포 승인으로 확대 해석하지 않는다.
- S1~S9 기본 제안 채택: S1-A(복합 파일), S2-B(복수), S3-A(추가자료 나중), **S4-A(대목차 하나=현재 파트)**, S5-A(사람 역할 확인), S6(고급 3개), S7(기존 DOCX만 재사용), S8-A(브랜치+PR), S9-A(최소 진행상태). 일부 UI 구현 미완은 아래에 표시.

## 읽기 전용 갭 결과

| 기능 | 상태 | 현재 코드·판정 |
|---|---|---|
| 8/16 정본·TOC·TASK 연결 | 구현됨 | docs/WEBAPP_MODULE_TO_FORM_TOC.md, 웹앱 최종사양, TASK.md |
| 기존 웹·Git 상태바·L 규칙 | 구현됨(기존) | operator_main.py / git_sync_service.py / lrule_console_service.py |
| DOCX/HWPX 기존 엔진 | 구현됨(기존) | ProjectService.generate / _generate_hwpx_direct / regenerate_sections |
| 필수 공고·양식 및 역할 확인 | 미구현 → 개발 브랜치 일부 구현 | 기존 운영화면은 template_file 하나만 필수 |
| 의미 모듈 + 정확한 원문 블록 선택 | 미구현 → 개발 브랜치 일부 구현 | 모듈 목록·문단/표셀 및 HWPX 내부 locator, PDF bbox. 원문 하이라이트 검증 없음 |
| 모듈 → 이번 양식 대목차 재구성 | 미구현 → 개발 브랜치 일부 구현 | 자동 대목차 추출/현재 대목차 선택. 제안 재배치 고도화·사용자 확정 검증 없음 |
| [1][2][3] 자연어 및 Composition Plan | 미구현 → 개발 브랜치 일부 구현 | 선택재료/번호 액션 안내/계획 확인. AI 해석·오매칭 규칙 검증 미완 |
| 사용자 승인 전 생성 차단 | 미구현 → 개발 브랜치 코드 구현 | approval state 후에만 새 AW-009 경로 엔진 호출 |
| 해당 대목차만 엔진 실행 | 충돌 → 개발 브랜치 제한 연결 | 기존 웹 즉시 전체 generate. 신규 경로는 DOCX 기존 regenerate_sections 호출(해당 질문만 작성); HWPX 원본 섹션 제한 게이트는 BLOCKED |
| 주자료/보조자료·PSST UI | 충돌 | 기존 별도 양식에서 psst_only=True; 신규 경로는 PSST 구조 기준 미사용 |
| MODULE/LOCATOR 실 E2E | 미구현 | 자동 단위 테스트 추가했으나 통과 로그·실원문 하이라이트 증거 없음 |
| 원본 HWPX 채움 실증 1건 | 미구현 | 실 원본 입력과 한컴 렌더·시각 검수 미실시 |

## 오직 P0 (이번 브랜치)

업로드 → 의미 모듈 → 양식 대목차 → 선택 재료 [1][2][3] → Composition Plan → 명시적 승인 → **현재 대목차만** 기존 엔진 호출.

BPQ, 품질점수, 제출가능 자동판정, P1(수정/USER_LOCKED), P2(Flow/아키텍처), CRM, 결제, 신규 DOCX 엔진은 후순위/범위 밖. 기존 UI/엔진은 삭제하지 않는다.

## 완료 전 필수 게이트

- [ ] CI에서 \`app/tests/test_aw009_module_workspace.py\` PASS
- [ ] MODULE-E2E-01~05 실제 웹 사용자 경로
- [ ] LOCATOR-E2E-01 하이라이트 및 SOURCE-E2E-01 파일명+실제 페이지
- [ ] DOC-E2E-01 현재 대목차 이외 내용 미변경과 승인 전 산출물 없음
- [ ] 원본 HWPX 실제 파일 1건: 원본 SHA·part-scoped 차분·출력·한컴 실제 렌더 및 QA 증거
- [ ] E2E 증거가 모두 붙은 뒤에만 TASK.md \`[ ]\`를 \`[x]\`로 변경

웹에서 결과가 표시되어도 Mock/partial/유닛테스트만으로 DONE 처리 금지. 현재 브랜치 상태 PARTIAL / REQUEST_SOLVED=NO. \`main\`과 원본 파일은 수정하지 않음.
