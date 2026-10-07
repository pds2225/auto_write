# auto_write Domain Refactor Report

> 브랜치: `refactor/domain-restructure-v2`
> 작업일: 2026-08-09

## 1. Executive Summary

auto_write 저장소의 도메인 경계를 명확화하고, 기존 기능을 보존하면서 점진적 migration을 수행했습니다.

## 2. Architecture

```
app/
├── auto_write/
│   ├── domains/
│   │   ├── business_plan/pipeline.py      ← BP 도메인 facade
│   │   ├── consultant_application/pipeline.py  ← CA 도메인 facade
│   │   └── domain_classifier.py           ← 도메인 분류기
│   ├── services/
│   │   ├── label_utils.py                 ← CORE: 공용 라벨 유틸 (SYNONYMS, key, cluster_rep)
│   │   ├── psst_patterns.py               ← CORE: PSST 정규식 패턴
│   │   ├── lrule_domain_gate.py           ← CORE: 도메인 인식 L규칙 게이트
│   │   ├── psst_check.py                  ← psst_patterns에서 import (decoupled)
│   │   ├── cross_form_autofill.py         ← label_utils에서 import (decoupled)
│   │   ├── company_extract.py             ← label_utils에서 import (decoupled)
│   │   ├── hwp_com_fill.py                ← label_utils에서 import (decoupled)
│   │   └── project_service.py             ← psst_patterns에서 import (decoupled)
│   └── config.py                          ← 도메인 라우팅 추가
├── bizplan/                               ← BUSINESS_PLAN 도메인 패키지
│   ├── services/ (13 wrappers)
│   └── cli/ (5 wrappers)
├── resume/                                ← CONSULTANT_APPLICATION 도메인 패키지
│   ├── services/ (8 wrappers)
│   └── cli/ (1 wrapper)
└── tests/
    ├── test_architecture_boundaries.py    ← 아키텍처 경계 검증 (3 tests)
    ├── test_lrule_domain_gate.py          ← LRule domain 테스트 (6 tests)
    └── lessons_coverage.json              ← 151개 규칙에 domain 필드 추가
```

## 3. Dependency Direction

```
domains → core (허용)
core → domains (금지)
business_plan → consultant_application (금지)
consultant_application → business_plan (금지)
```

## 4. Key Changes

| 파일 | 변경 내용 |
|------|----------|
| label_utils.py (신규) | cross_form_autofill에서 SYNONYMS, key, cluster_rep 추출 |
| psst_patterns.py (신규) | project_service에서 PSST 정규식 추출 |
| lrule_domain_gate.py (신규) | 도메인 인식 L규칙 enforcement |
| domain_classifier.py (신규) | business_plan/consultant_application/other 분류기 |
| BP/CA pipeline.py (신규) | 도메인 facade (기존 서비스 호출) |
| config.py | get_domain_workspace, get_domain_results, get_project_dir 추가 |
| lessons_coverage.json | 151개 규칙에 domain 필드 (all=105, bp=20, ca=26) |
| cross_form_autofill.py | label_utils에서 import로 변경 |
| company_extract.py | label_utils에서 import로 변경 |
| hwp_com_fill.py | label_utils에서 import로 변경 |
| project_service.py | psst_patterns에서 import로 변경 |
| psst_check.py | psst_patterns에서 직접 import로 변경 |

## 5. Tests

| 테스트 파일 | 결과 |
|------------|------|
| test_architecture_boundaries.py | 3 passed |
| test_lrule_domain_gate.py | 6 passed |
| test_docx_ops.py | 5 passed |
| test_document_quality_harness.py | 33 passed |
| test_hwpx_fill.py | 76 passed |
| test_resume_form_fill.py | 11 passed |
| test_quality_ratchet.py | 13 passed |
| test_cross_form_autofill.py | 77 passed, 5 env failures (baseline) |
| **새 코드 회귀** | **0** |

## 6. Commits

| SHA | 메시지 |
|-----|--------|
| 03c59d5 | docs: complete Phase 1 domain audit and dependency map |
| 0987dcd | refactor: add domain module placeholders |
| c07cff9 | refactor: add domain wrappers |
| 0de5c43 | refactor: add domain pipelines, classifier, architecture tests |
| b7ac6b0 | refactor: extract shared label utilities from cross_form_autofill |
| 01fc24e | refactor: extract PSST patterns, decouple psst_check |
| ea6f8ed | feat: add domain-aware LRule gate |
| f1a22e3 | feat: add domain-aware workspace/results routing |

## 7. Remaining Work

| 우선순위 | 작업 |
|----------|------|
| P0 | PR #115 병합 |
| P1 | project_service.py 추가 분리 (72개 메서드 중 BP 전용 facade) |
| P1 | MIXED 파일 8개 추가 분리 (notice_pipeline, folder_analyzer 등) |
| P2 | LRule gap 규칙 mechanized 확대 |
| P2 | workspace/results 실운영 라우팅 적용 |
