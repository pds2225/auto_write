# DOCX Duplicate Source Map

> 브랜치: `refactor/repo-split-pm`
> 생성일: 2026-08-07 (Gate 1 rework)
> 기준: `app/core/docx/` 복사본 vs `app/auto_write/` 원본
> 실제 파일 수: **65** (이전 보고 66 오류 — 1개 과다 계수 교정)

## Root Files (`app/core/docx/`)

| staged_path | original_path | identical | file_role | imported_by | imports | ownership | reason | proposed_action |
|---|---|---|---|---|---|---|---|---|
| app/core/docx/document_ingest.py | app/auto_write/document_ingest.py | Yes | SERVICE | doc_text_extract, hwp_docx_convert, resume_extract, company_extract, announcement_analyzer | (stdlib) | CORE | HWP/HWPX/DOCX/PDF→텍스트 추출. 이력서·사업계획서 양쪽 사용 | KEEP_CORE |
| app/core/docx/docx_template.py | app/auto_write/analysis/docx_template.py | Yes | SERVICE | (standalone) | models | BIZPLAN | 사업계획서 양식 템플릿 분석(표/섹션/이미지 감지). 정부지원사업 전용 | MOVE_BIZPLAN |
| app/core/docx/__init__.py | (신규) | - | PACKAGE_META | - | - | NONE | 패키지 마커 | KEEP_PACKAGE_META |

## Services (`app/core/docx/services/`)

| staged_path | original_path | identical | file_role | imported_by | imports | ownership | reason | proposed_action |
|---|---|---|---|---|---|---|---|---|
| services/cross_form_autofill.py | app/auto_write/services/cross_form_autofill.py | Yes | SERVICE | company_extract, folder_analyzer, hwpx_fill, hwp_com_fill, notice_pipeline, pipeline_failure_ux, resume_extract | docx_ops, submittable_filler, hwp_docx_convert | MIXED | 사업계획서 양식 전사 엔진(~90% BIZPLAN) + 범용 파일 순위 유틸리티(rank_source_pool, list_source_pool 등 ~10% CORE). resume_extract가 rank_source_pool/list_source_pool만 import. 범용 유틸을 app/core/source_pool.py로 추출하면 BIZPLAN으로 전환 가능 | MIXED_REFACTOR |
| services/defect_classifier.py | app/auto_write/services/defect_classifier.py | Yes | SERVICE | self_improvement_planner | acceptance_remediation, usage_acceptance | CORE | 자기개선 루프용 결함 분류기. 도메인 비종속(사업계획서/이력서 특정 코드 없음). CheckResult/Remedy 기반 순수 분류 로직 | KEEP_CORE |
| services/document_quality_orchestrator.py | app/auto_write/services/document_quality_orchestrator.py | Yes | SERVICE | autopilot_pipeline, submission_orchestrator | doc_quality_ops, document_type_classifier, psst_check, infographic_suggest, doc_quality_score, quality_rules, usage_acceptance | CORE | 품질 하네스 오케스트레이터. 이력서·사업계획서 양쪽 품질 파이프라인 | KEEP_CORE |
| services/docx_ops.py | app/auto_write/services/docx_ops.py | Yes | SERVICE | cross_form_autofill, doc_quality_ops, doc_quality_score, render_service, submittable_filler | (python-docx) | CORE | 저수준 DOCX 조작(set_cell_text, logical_cells, insert_image) | KEEP_CORE |
| services/doc_quality_ops.py | app/auto_write/services/doc_quality_ops.py | Yes | SERVICE | document_quality_orchestrator, doc_quality_score | docx_ops, quality_rules | CORE | DOCX 후처리(안내문구 삭제, 글머리표 정리, 글자크기 통일, 핵심문장 강조) | KEEP_CORE |
| services/doc_quality_score.py | app/auto_write/services/doc_quality_score.py | Yes | SERVICE | autopilot_pipeline, document_quality_orchestrator | doc_quality_ops, docx_ops, qa_service | CORE | 100점 품질점수 산정 | KEEP_CORE |
| services/doc_text_extract.py | app/auto_write/services/doc_text_extract.py | Yes | SERVICE | announcement_analyzer, company_extract, notice_pipeline, resume_extract | document_ingest | CORE | DOCX/PDF/HWP/HWPX 텍스트 추출 | KEEP_CORE |
| services/hwpx_fill.py | app/auto_write/services/hwpx_fill.py | Yes | SERVICE | hwpx_fill_coverage, hwpx_form_extract, hwpx_layout_fix, hwpx_pic_insert, hwpx_resume_supplement, hwpx_section_split, hwpx_submission_cleanup, hwpx_submit, hwp_com_fill, resume_fill_service, resume_form_map | cross_form_autofill, hwpx_charpr_guard | CORE | HWPX 직접 XML 채움 엔진. 이력서·사업계획서 양쪽 사용 | KEEP_CORE |
| services/hwpx_fill_coverage.py | app/auto_write/services/hwpx_fill_coverage.py | Yes | SERVICE | (standalone) | hwpx_fill, hwpx_resume_supplement | RESUME | HWPX 섹션 커버리지 리포트. 이력서/신청서 전용 | MOVE_RESUME |
| services/hwp_com_fill.py | app/auto_write/services/hwp_com_fill.py | Yes | SERVICE | (standalone) | cross_form_autofill, hwp_docx_convert, hwpx_fill | BIZPLAN | HWP COM 기반 양식 채움(필드/표) | MOVE_BIZPLAN |
| services/hwp_docx_convert.py | app/auto_write/services/hwp_docx_convert.py | Yes | SERVICE | conversion_fidelity, cross_form_autofill, hwp_com_fill, hwp_fill, runtime_env | hancom_com_guard, usage_acceptance, document_ingest | CORE | HWP/HWPX ↔ DOCX 양방향 변환 | KEEP_CORE |
| services/hwp_fill.py | app/auto_write/services/hwp_fill.py | Yes | SERVICE | (standalone) | conversion_fidelity, hwp_docx_convert, submittable_filler, bizplan_autopilot | BIZPLAN | HWP end-to-end 채움 파이프라인(convert→fill→convert back) | MOVE_BIZPLAN |
| services/psst_fill.py | app/auto_write/services/psst_fill.py | Yes | SERVICE | autopilot_pipeline | psst_check, usage_acceptance | BIZPLAN | PSST(Problem/Solution/Scale/Team) 스캐폴드 삽입. 사업계획서 전용 | MOVE_BIZPLAN |
| services/quality_ratchet.py | app/auto_write/services/quality_ratchet.py | Yes | SERVICE | (standalone) | (pure functions) | CORE | 품질 baseline ratchet 로직 | KEEP_CORE |
| services/quality_rules.py | app/auto_write/services/quality_rules.py | Yes | SERVICE | document_quality_orchestrator, doc_quality_ops | (config) | BIZPLAN | 사업계획서 집필 규칙 프리셋(BizplanRulesConfig). 기본 프리셋 "bizplan", 문서유형 매핑 business_plan/pitch_deck → bizplan | MOVE_BIZPLAN |
| services/render_service.py | app/auto_write/services/render_service.py | Yes | SERVICE | project_service, main.py, submit.py | models, docx_ops | CORE | 범용 DOCX 템플릿 렌더러(TemplateProfile/ProjectInput 기반). psst_only/psst_field_ids 인자는 선택적 2줄 필터 가드로, 미전달 시 완전 범용 동작. 분리 불필요 | KEEP_CORE |
| services/resume_fill_service.py | app/auto_write/services/resume_fill_service.py | Yes | SERVICE | (standalone) | hwpx_fill, hwpx_layout_fix, resume_form_map | RESUME | 이력서 양식 채움(신원+반복행). HWPX 전용 | MOVE_RESUME |
| services/submittable_filler.py | app/auto_write/services/submittable_filler.py | Yes | SERVICE | cross_form_autofill, hwp_fill, submission_orchestrator | docx_ops | BIZPLAN | 렌더 후 사업계획서 DOCX 채움(라벨 매칭, 더미 정리) | MOVE_BIZPLAN |
| services/__init__.py | (신규) | - | PACKAGE_META | - | - | NONE | 패키지 마커 | KEEP_PACKAGE_META |

## CLI (`app/core/docx/cli/`)

| staged_path | original_path | identical | file_role | imported_by | imports | ownership | reason | proposed_action |
|---|---|---|---|---|---|---|---|---|
| cli/company_master.py | app/company_master.py | Yes | CLI | (standalone) | company_extract, document_ingest, cross_form_autofill | BIZPLAN | 기업 마스터 JSON 빌더 CLI | MOVE_BIZPLAN |
| cli/conversion_fidelity.py | app/conversion_fidelity.py | Yes | CLI | (standalone) | conversion_fidelity | CORE | 변환 충실도 측정 CLI | KEEP_CORE |
| cli/cross_form_fill.py | app/cross_form_fill.py | Yes | CLI | (standalone) | cross_form_autofill | BIZPLAN | 양식 간 전사 CLI | MOVE_BIZPLAN |
| cli/document_quality_orchestrator.py | app/document_quality_orchestrator.py | Yes | CLI | (standalone) | DocumentQualityOrchestrator | CORE | 품질 하네스 CLI 엔트리포인트 | KEEP_CORE |
| cli/docx2hwp.py | (신규) | - | TOOLING | (standalone) | (COM automation) | CORE | DOCX→HWP 변환 스크립트. 원본 scripts/docx2hwp.py를 실행 진입점으로 유지 | KEEP_SCRIPT |
| cli/extract_doc_data.py | (신규) | - | CASE_SCRIPT | (standalone) | - | NONE | 특정 미래큐러스 문서 데이터 추출. 로컬 임시경로 하드코딩. 공유 core 분류 불가 | KEEP_LEGACY_OR_SALVAGE |
| cli/hwp_docx.py | app/hwp_docx.py | Yes | CLI | (standalone) | hwp_docx_convert | CORE | HWP↔DOCX 변환 CLI | KEEP_CORE |
| cli/hwp_fill.py | app/hwp_fill.py | Yes | CLI | (standalone) | hwp_fill | BIZPLAN | HWP 채움 end-to-end CLI | MOVE_BIZPLAN |
| cli/hwp_fill_direct.py | app/hwp_fill_direct.py | Yes | CLI | (standalone) | hwp_com_fill, hwpx_fill | BIZPLAN | 직접 HWP/HWPX 채움 CLI | MOVE_BIZPLAN |
| cli/learn_run.py | app/learn_run.py | Yes | CLI | (standalone) | defect_classifier, usage_acceptance | BIZPLAN | 자기학습 CLI | MOVE_BIZPLAN |
| cli/quality_ratchet.py | app/quality_ratchet.py | Yes | CLI | (standalone) | quality_ratchet | CORE | 품질 ratchet CLI | KEEP_CORE |
| cli/resume_fill.py | app/resume_fill.py | Yes | CLI | (standalone) | resume_extract, resume_fill_service | RESUME | 이력서 자동작성 CLI | MOVE_RESUME |
| cli/run_document_quality_harness.py | (신규) | - | TOOLING | (standalone) | - | CORE | 품질 하네스 래퍼 스크립트. 원본 scripts/run_document_quality_harness.py를 실행 진입점으로 유지 | KEEP_SCRIPT |
| cli/self_diagnose.py | app/self_diagnose.py | Yes | CLI | (standalone) | usage_acceptance | BIZPLAN | 제출 준비 진단 CLI | MOVE_BIZPLAN |
| cli/strip_notebooklm.py | app/strip_notebooklm.py | Yes | CLI | (standalone) | image_apply, usage_acceptance | BIZPLAN | NotebookLM 블록 제거 CLI | MOVE_BIZPLAN |
| cli/__init__.py | (신규) | - | PACKAGE_META | - | - | NONE | 패키지 마커 | KEEP_PACKAGE_META |

## Tests (`app/core/docx/tests/`)

| staged_path | original_path | identical | file_role | ownership | reason | proposed_action |
|---|---|---|---|---|---|---|
| tests/test_autofill.py | app/tests/test_autofill.py | Yes | TEST | BIZPLAN | autofill 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_company_extract.py | app/tests/test_company_extract.py | Yes | TEST | BIZPLAN | company_extract 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_cross_form_autofill.py | app/tests/test_cross_form_autofill.py | Yes | TEST | BIZPLAN | cross_form_autofill 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_document_ingest.py | app/tests/test_document_ingest.py | Yes | TEST | CORE | document_ingest 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_document_quality_harness.py | app/tests/test_document_quality_harness.py | Yes | TEST | CORE | document_quality_orchestrator 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_docx_ops.py | app/tests/test_docx_ops.py | Yes | TEST | CORE | docx_ops 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_hwpx_fill.py | app/tests/test_hwpx_fill.py | Yes | TEST | CORE | hwpx_fill 테스트(양쪽 사용) | KEEP_TEST_WITH_OWNER |
| tests/test_hwpx_fill_coverage.py | app/tests/test_hwpx_fill_coverage.py | Yes | TEST | RESUME | hwpx_fill_coverage 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_hwpx_form_extract.py | app/tests/test_hwpx_form_extract.py | Yes | TEST | BIZPLAN | hwpx_form_extract 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_hwp_com_fill.py | app/tests/test_hwp_com_fill.py | Yes | TEST | BIZPLAN | hwp_com_fill 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_hwp_docx_convert.py | app/tests/test_hwp_docx_convert.py | Yes | TEST | CORE | hwp_docx_convert 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_hwp_fill.py | app/tests/test_hwp_fill.py | Yes | TEST | BIZPLAN | hwp_fill 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_company_extract.py | app/tests/test_pure_company_extract.py | Yes | TEST | BIZPLAN | company_extract 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_doc_quality_ops_dominant.py | app/tests/test_pure_doc_quality_ops_dominant.py | Yes | TEST | CORE | doc_quality_ops 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_doc_text_extract.py | app/tests/test_pure_doc_text_extract.py | Yes | TEST | CORE | doc_text_extract 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_hwpx_fill_coverage_report.py | app/tests/test_pure_hwpx_fill_coverage_report.py | Yes | TEST | RESUME | hwpx_fill_coverage 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_hwpx_form_extract.py | app/tests/test_pure_hwpx_form_extract.py | Yes | TEST | BIZPLAN | hwpx_form_extract 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_hwp_docx_convert_paths.py | app/tests/test_pure_hwp_docx_convert_paths.py | Yes | TEST | CORE | hwp_docx_convert 경로 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_psst_fill.py | app/tests/test_pure_psst_fill.py | Yes | TEST | BIZPLAN | psst_fill 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_qa_render_helpers.py | app/tests/test_pure_qa_render_helpers.py | Yes | TEST | BIZPLAN | QA/렌더 헬퍼 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_pure_submittable_filler.py | app/tests/test_pure_submittable_filler.py | Yes | TEST | BIZPLAN | submittable_filler 순수 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_quality_ratchet.py | app/tests/test_quality_ratchet.py | Yes | TEST | CORE | quality_ratchet 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_quality_rules.py | app/tests/test_quality_rules.py | Yes | TEST | BIZPLAN | quality_rules 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_resume_extract.py | app/tests/test_resume_extract.py | Yes | TEST | RESUME | resume_extract 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_resume_form_fill.py | app/tests/test_resume_form_fill.py | Yes | TEST | RESUME | resume_fill_service 테스트 | KEEP_TEST_WITH_OWNER |
| tests/test_slide_asset_extractor.py | app/tests/test_slide_asset_extractor.py | Yes | TEST | BIZPLAN | slide_asset_extractor 테스트 | KEEP_TEST_WITH_OWNER |
| tests/__init__.py | (신규) | - | PACKAGE_META | NONE | 패키지 마커 | KEEP_PACKAGE_META |

---

## 핵심 발견사항

### 순환 import 위험
- `hwpx_fill.py` → `cross_form_autofill.py` → `docx_ops.py` (안전, 단방향)
- `cross_form_autofill.py` ↔ `submittable_filler.py` (상호 참조 — 분리 시 주의 필요)

### PM 지적 파일 재검토 결과

| 파일 | 기존 판정 | 수정 판정 | 사유 |
|---|---|---|---|
| cross_form_autofill.py | BIZPLAN | **MIXED** | resume_extract가 rank_source_pool/list_source_pool만 import. 범용 유틸 추출 시 BIZPLAN 전환 가능 |
| render_service.py | BIZPLAN | **CORE** | psst_only 인자는 선택적 2줄 필터 가드. 미전달 시 완전 범용 동작. 분리 불필요 |
| defect_classifier.py | BIZPLAN | **CORE** | 도메인 비종속. CheckResult/Remedy 기반 순수 분류 로직 |
| quality_rules.py | BIZPLAN | BIZPLAN (확인) | BizplanRulesConfig, 기본 프리셋 "bizplan" |

### 중요 의존성
- `hwpx_fill.py`: 이력서·사업계획서 양쪽 핵심 엔진 → CORE 유지 필수
- `document_ingest.py`: 전체 파이프라인 문서 입구 → CORE 유지 필수
- `hwp_docx_convert.py`: HWP↔DOCX 변환 유일 경로 → CORE 유지 필수
- `cross_form_autofill.py`: MIXED. rank_source_pool 추출 후 BIZPLAN 전환 예정

---

## 집계표

```
TOTAL_FILES = 65

ownership:
CORE = 22
RESUME = 7
BIZPLAN = 28
MIXED = 1
NONE = 7
SUM = 65

file_role:
SERVICE = 21
CLI = 13
TEST = 26
PACKAGE_META = 3
TOOLING = 2
SUM = 65
```
