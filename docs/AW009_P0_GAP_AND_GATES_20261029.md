# AW-009 P0 게이트 체크리스트 / 읽기 전용 갭 조사 (2026-10-29)

- 저장소: pds2225/auto_write, 조사 기준 main HEAD는 브랜치 분기 시점 기준. 본 브랜치 tip은 커밋 후 갱신.
- 정본 SSOT: docs/AUTO_WRITE_웹앱_최종_요구사항_20260816.md + docs/WEBAPP_MODULE_TO_FORM_TOC.md
- TASK: origin/main AW-005 [ ], AW-009 [ ]. 본 작업 브랜치에서 완료 체크를 하지 않는다.
- 진행 근거: 2026-10-29 사용자 요청 「가능한데까지 끝까지」「요청없이 요구사항 모두 해결」. S1~S9 기본값 채택 확정. 별도 선택 지시 없으면 확인 질문하지 않는다.
- S1~S9 기본 제안 채택: S1-A(단일 화면), S2-B(로컬), S3-A(중간재료 유지), **S4-A(대목차 하나=현재 파트)**, S5-A(엔진 재사용 확정), S6(근거 3건), S7(검증 DOCX+HWPX), S8-A(브랜치+PR), S9-A(최소 게이트통과). 일부 UI 디테일 이외는 아래 표로.

## 읽기 전용 갭 표

| 항목 | 상태 | 근거 코드·문서 |
|---|---|---|
| 8/16 대목차·TOC·TASK 정본 | 구현됨 | docs/WEBAPP_MODULE_TO_FORM_TOC.md, 최종 요구사항, TASK.md |
| 문서 작업·Git 콘솔·L 규칙 | 구현됨(기존) | operator_main.py / git_sync_service.py / lrule_console_service.py |
| DOCX/HWPX 엔진 본체 | 구현됨(기존) | ProjectService.generate / _generate_hwpx_direct / regenerate_sections / guidance writers |
| 필수 양식파일 한 개 업로드 고정 | 구현됨 · 본 브랜치 | module workspace template_file 하나 필수 |
| 의미 모듈 + 페이지·표 단위 재료 추출 | 구현됨 · 본 브랜치 일부 | PDF bbox / DOCX 하이라이트 경로. HWPX 모듈 locator는 약함 |
| 공고·양식 대목차 재구성 | 구현됨 · 본 브랜치 일부 | 자동 대목차 추출/수동 편집 경로. 실양식 대목차 정규화 확인은 양식별 |
| [1][2][3] 근거선택 + Composition Plan | 구현됨 · 본 브랜치 일부 | 선택·승인 액션. AI 해석·자동매핑 규칙은 최소 |
| 대목차 한정 · 현재 파트만 엔진 | 구현됨 · 본 브랜치 | DOCX=
egenerate_sections; HWPX=w009_hwpx_part.fill_current_section (기존 guidance writer 재사용) |
| 전체문서 generate 금지 | 구현됨 · 본 브랜치 | _aw009_execute_approved_part가 파트 한정만 호출 |
| 품질점수·BPQ·PSST UI | 후순위(충돌/제외) | P0에서 BPQ·품질점수 제외. PSST는 표시 전용 |
| MODULE/LOCATOR 웹 E2E | 부분 · 유닛 PASS / 웹 UI E2E 미완 | 	est_aw009_module_workspace.py + 	est_aw009_hwpx_part.py PASS. 브라우저 하이라이트 E2E 없음 |
| 원본 HWPX 채움 증거 1건 | 구현됨 · 합정PC 증거 | GovTech 기획서 참가작 주요내용 요약 part-scoped fill + 한컴 PDF 120KB (
esults/aw009_hwpx_hapjeong_verify/) |

## 확정 P0 (이번 브랜치)

업로드 → 의미 모듈 → 대목차 재구성 → 근거 선택 [1][2][3] → Composition Plan → 승인 후 **현재 대목차만** 기존 엔진 호출.

BPQ, 품질점수, 생성가능 자동판정, P1(병렬/USER_LOCKED), P2(Flow/패키지화), CRM, 결제, 신규 DOCX 템플릿 파서 재작성 제외. 운영 UI/배포는 건드리지 않는다.

## 완료 전 필수 게이트

- [x] 로컬 pp/tests/test_aw009_module_workspace.py + 	est_aw009_hwpx_part.py PASS (12)
- [ ] MODULE-E2E-01~05 브라우저 실화면 로그
- [ ] LOCATOR-E2E-01 하이라이트 + SOURCE-E2E-01 파일명·페이지 검증
- [ ] DOC-E2E-01 빈 사업계획 양식 전체 문서작업 단일화면 루프
- [x] 원본 HWPX 대목차 채움 1건: 원본 SHA·part-scoped 성공·scope_ok·한컴 렌더 (합정 part_fill_evidence.json / part_filled_hangul.pdf)
- [ ] E2E 증거가 모두 쌓인 뒤에만 TASK.md [ ]→[x]

로컬 유닛·한 건 채움이 있어도 Mock/partial/유닛만으로 DONE 처리 금지. 본 브랜치 상태 PARTIAL / REQUEST_SOLVED=NO(웹 E2E·빈 사업계획 양식 전체루프 남음). main 머지는 사용자 승인 전 금지.
