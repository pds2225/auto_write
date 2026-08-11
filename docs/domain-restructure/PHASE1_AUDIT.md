# PHASE 1 — 저장소 전수조사 및 Dependency Map

> 브랜치: `refactor/domain-restructure-v2`
> 기준일: 2026-08-09
> 기준: `app/auto_write/services/` 71개 파일 + 상위 CLI/분석 파일

## 1. 도메인 분류 요약

| 도메인 | 파일 수 | 비고 |
|--------|---------|------|
| CORE | 37 | 공통 문서처리 엔진 (DOCX/HWPX/HWP/AI/QA/수용검사) |
| BUSINESS_PLAN | 18 | 사업계획서 작성/PSST/평가/공고분석/학습 |
| CONSULTANT_APPLICATION | 7 | 이력서/신청서 자동작성/커버리지 |
| MIXED | 9 | 두 도메인에서 공유되는 크로스커팅 모듈 |

## 2. 파일별 분류 상세

### CORE (37개)

| 파일 | 핵심 기능 | import 수 |
|------|----------|----------|
| docx_ops.py | DOCX 셀/단락 조작, 색상 정규화 | 16 |
| hwp_docx_convert.py | HWP↔DOCX 양방향 변환 | 22 |
| hwpx_fill.py | HWPX 직접 XML 채움 엔진 | 28 |
| doc_text_extract.py | DOCX/PDF/HWP/HWPX 텍스트 추출 | 9 |
| openai_client.py | AI 클라이언트 (OpenAI/Anthropic) | 23 |
| render_service.py | DOCX 템플릿 렌더링 | 18 |
| qa_service.py | 문서 품질 검사 (가이드/placeholder) | 16 |
| evidence_service.py | 웹 근거 검색 + AI 요약 | 14 |
| image_service.py | 이미지 생성 오케스트레이션 | 15 |
| image_providers.py | Gemini/OpenAI 이미지 생성 | 1 |
| submittable_filler.py | 렌더 후 잔존 채움 | 11 |
| doc_quality_ops.py | DOCX 후처리 (안내문구/글머리표/폰트/강조) | 8 |
| doc_quality_score.py | 100점 품질점수 산정 | 8 |
| document_type_classifier.py | 문서 유형 9종 분류 | 8 |
| document_quality_orchestrator.py | 품질 하네스 오케스트레이터 | 10 |
| infographic_suggest.py | 인포그래픽 배치 제안 | 9 |
| conversion_fidelity.py | DOCX↔HWP 충실도 측정 | 7 |
| hwpx_layout_fix.py | HWPX 레이아웃 정규화/격자 수리 | 8 |
| hwpx_form_extract.py | HWPX 양식 섹션 추출 | 6 |
| hwpx_form_diff.py | HWPX 원본vs채움 구조 비교 | 2 |
| hwpx_charpr_guard.py | HWPX charPr append-only 검증 | 4 |
| hwpx_submission_cleanup.py | HWPX 제출 정리 | 4 |
| hwpx_pic_insert.py | HWPX 이미지 삽입/리사이즈 | 1 |
| hancom_com_guard.py | 한글 COM 안전 가드 | 6 |
| chart_generator.py | matplotlib 차트 생성 | 0 |
| chart_insert.py | DOCX 차트 삽입 | 1 |
| image_apply.py | NotebookLM 슬라이드 프롬프트 삽입/추출 | 7 |
| runtime_env.py | 런타임 환경 감지 | 3 |
| output_naming.py | 제출 파일명 규칙 | 3 |
| quality_rules.py | 문서 품질 규칙 프리셋 설정 | 6 |
| quality_ratchet.py | 품질 baseline ratchet 로직 | 4 |
| usage_acceptance.py | 제출 수용검사 게이트 (15+ 항목) | **39** |
| acceptance_remediation.py | 수용검사 결함 → 보안 가이드 | 8 |
| hwpx_acceptance.py | HWPX 전용 수용검사 | 3 |
| submission_regression_check.py | 제출 합본 회귀 검사 | 3 |
| user_pipeline_config.py | 사용자 파이프라인 설정 | 2 |
| defect_classifier.py | 결함 분류기 (자기개선용) | 8 |

### BUSINESS_PLAN (18개)

| 파일 | 핵심 기능 | import 수 |
|------|----------|----------|
| psst_check.py | PSST 4영역 구조 검사 | 9 |
| psst_fill.py | PSST 스캐폴드 삽입 | 4 |
| evaluation_service.py | 공고 평가기준 채점 | 10 |
| announcement_analyzer.py | 공고 종합 분석 | 5 |
| bizplan_autopilot.py | 사업계획서 E2E 자동 루프 | 7 |
| bizplan_ai_writer.py | PSST 약영역 AI 작성 | 2 |
| autopilot_pipeline.py | 품질 자동 수정 파이프라인 | 4 |
| eval_loop_runner.py | 평가 루프 실행기 | 3 |
| plan_builder.py | 제출 계획 빌더 | 3 |
| submission_orchestrator.py | 제출 E2E 파이프라인 | 3 |
| self_improvement_planner.py | 자기개선 계획 | 5 |
| learning_report.py | 학습 리포트 생성 | 4 |
| learning_store.py | 학습 데이터 저장소 | 8 |
| run_evaluator.py | 실행 평가기 | 3 |
| sft_export.py | SFT 학습데이터 내보내기 | 0 |
| generation_store.py | AI 호출 추적 저장소 | 0 |
| d_trigger.py | 서술 항목 판별 | 3 |
| form_analyzer.py | 양식 분석 (항목 분류) | 10 |

### CONSULTANT_APPLICATION (7개)

| 파일 | 핵심 기능 | import 수 |
|------|----------|----------|
| resume_extract.py | 이력서 → 구조화 프로필 | 7 |
| resume_fill_service.py | HWPX 이력서 양식 채움 | 5 |
| resume_form_map.py | 이력서 양식 테이블 매핑 | 6 |
| hwpx_resume_supplement.py | HWPX 이력서 테이블 보충 | 6 |
| hwpx_fill_coverage.py | HWPX 이력서 커버리지 리포트 | 7 |
| hwpx_specialty_profile.py | 전문분야 체크박스 좌표 맵 | 3 |
| hwpx_section_split.py | HWPX 섹션 분할 | 2 |

### MIXED (9개) — 도메인 분리 필요

| 파일 | 핵심 기능 | import 수 | 분리 방향 |
|------|----------|----------|----------|
| **cross_form_autofill.py** | 양식 간 전사 엔진 (SYNONYMS, _key, _cluster_rep) | **33** | 핵심 유틸 → CORE, 양식 전사 → 공유 |
| **company_extract.py** | 기업 정보 추출 | 2 | 공유 (양쪽 사용) |
| **hwp_com_fill.py** | 바이너리 .hwp 한글COM 채움 | 7 | CORE 엔진 (양쪽 사용 가능) |
| **hwp_fill.py** | HWP E2E 채움 파이프라인 | 4 | CORE 엔진 |
| **hwpx_submit.py** | HWPX 제출 파이프라인 | 2 | CORE (수용검사 결합) |
| **notice_pipeline.py** | 공고→자동 파이프라인 오케스트레이터 | 2 | BUSINESS_PLAN (공고 처리) |
| **pipeline_failure_ux.py** | 실패 UX 분류 | 3 | CORE |
| **folder_analyzer.py** | 폴더 분석 (공고+양식) | 6 | BUSINESS_PLAN (공고 분석 결합) |
| **cross_form_output_policy.py** | 출력 형식/엔진 정책 | 2 | CORE |

## 3. 핵심 크로스커팅 의존성

### 가장 위험한 coupling

| 모듈 | import 수 | 문제 |
|------|----------|------|
| cross_form_autofill.py | 33 | _key, _cluster_rep, SYNONYMS가 모든 도메인에서 사용 |
| usage_acceptance.py | 39 | 수용검사 게이트 — 양쪽 도메인 필수 |
| hwpx_fill.py | 28 | cross_form_autofill에서 매칭 지능 import |
| docx_ops.py | 16 | 저수준 DOCX 조작 — 모든 도메인 기반 |
| hwp_docx_convert.py | 22 | 형식 변환 — 모든 도메인 기반 |

### 금지 dependency 검증

| 규칙 | 현재 상태 |
|------|----------|
| core → domains | 위반 없음 (확인 필요) |
| business_plan → consultant_application | 위반 없음 (확인 필요) |
| consultant_application → business_plan | 위반 없음 (확인 필요) |

## 4. 기존 app/resume/, app/bizplan/ 상태

어제 야간 작업으로 이미 생성된 구조:
- `app/resume/services/` — 4개 파일 (resume_extract, resume_fill_service, resume_form_map, hwpx_fill_coverage)
- `app/resume/cli/` — 1개 파일 (resume_fill)
- `app/bizplan/services/` — 8개 파일 (cross_form_autofill, psst_fill, quality_rules, submittable_filler, hwp_com_fill, hwp_fill, render_service, docx_template)
- `app/bizplan/cli/` — 5개 파일 (company_master, cross_form_fill, self_diagnose, learn_run, strip_notebooklm)

이 구조를 기반으로 확장하되, dev_20260809.md의 목표 구조에 맞게 정리합니다.

## 5. 목표 구조 (dev_20260809.md 기반)

```
app/auto_write/
├── core/                    ← 공통 문서처리 엔진
│   ├── document/            ← DOCX/HWPX/HWP 조작
│   ├── ai/                  ← AI 클라이언트
│   ├── qa/                  ← 품질 검사
│   ├── rendering/           ← 렌더링
│   ├── submission/          ← 제출 인프라
│   └── storage/             ← 저장소
├── domains/
│   ├── business_plan/       ← 사업계획서 도메인
│   │   ├── pipeline.py
│   │   ├── analyzer.py
│   │   ├── writer.py
│   │   ├── psst.py
│   │   ├── evaluator.py
│   │   ├── validators.py
│   │   └── rules.py
│   └── consultant_application/  ← 컨설턴트 신청서 도메인
│       ├── pipeline.py
│       ├── analyzer.py
│       ├── autofill.py
│       ├── resume.py
│       ├── evidence.py
│       ├── validators.py
│       └── rules.py
├── lrules/                  ← L규칙 시스템
├── classifiers/             ← 문서/도메인 분류기
└── cli/                     ← CLI 진입점
```
