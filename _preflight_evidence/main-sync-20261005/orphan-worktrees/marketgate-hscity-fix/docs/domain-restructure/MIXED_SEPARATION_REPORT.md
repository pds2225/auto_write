# MIXED File Separation — Final Report

> 브랜치: `refactor/mixed-file-separation`
> 작업일: 2026-08-09

## 1. Executive Summary

cross_form_autofill.py를 포함한 MIXED 파일 10개를 CORE/BIZPLAN으로 분리 완료.
기존 기능 보존, 새 코드 회귀 0.

## 2. MIXED → Domain 분류 결과

| 파일 | 이전 | 이후 | 핵심 조치 |
|------|------|------|----------|
| cross_form_autofill.py | MIXED | BIZPLAN | label_utils + source_pool_utils 추출 |
| company_extract.py | MIXED | CORE | label_utils import로 decoupling |
| hwp_com_fill.py | MIXED | CORE | label_utils import로 decoupling |
| hwp_fill.py | MIXED | BIZPLAN | bizplan/services/에 전체 구현 |
| hwpx_submit.py | MIXED | CORE | 모든 import가 CORE 모듈 |
| notice_pipeline.py | MIXED | BIZPLAN | bizplan wrapper 존재 |
| pipeline_failure_ux.py | MIXED | BIZPLAN | source_pool_utils import로 decoupling |
| folder_analyzer.py | MIXED | BIZPLAN | bizplan wrapper 존재 |
| form_analyzer.py | MIXED | CORE | document_ingest + analysis만 사용 |
| cross_form_output_policy.py | MIXED | CORE | import 없음 |

## 3. 신규 CORE 모듈

| 모듈 | 추출 내용 | 크기 |
|------|----------|------|
| label_utils.py | SYNONYMS (24 클러스터, 324 엔트리), key, cluster_rep, is_obvious_placeholder | 176줄 |
| source_pool_utils.py | list_source_pool, rank_source_pool, SourcePickScore, SourcePickReport | 217줄 |
| psst_patterns.py | PSST_PROBLEM_RE, PSST_SOLUTION_RE, PSST_SCALE_RE, PSST_TEAM_RE | 19줄 |

## 4. Dependency 개선

```
이전: resume_extract → cross_form_autofill (MIXED)
이후: resume_extract → source_pool_utils (CORE)

이전: company_extract → cross_form_autofill (MIXED)
이후: company_extract → label_utils (CORE)

이전: hwp_com_fill → cross_form_autofill (MIXED)
이후: hwp_com_fill → label_utils (CORE)

이전: psst_check → project_service (대형 MIXED)
이후: psst_check → psst_patterns (CORE)
```

## 5. Tests

| 테스트 | 결과 |
|--------|------|
| 새 코드 회귀 | **0** |
| 아키텍처 경계 | 3 PASS |
| baseline 실패 | 6 (py -3.11 미설치, 분리 전과 동일) |
| skip | 10 (환경 의존, 분리 전과 동일) |

## 6. Commits

| SHA | 메시지 |
|-----|--------|
| 5926a32 | bizplan wrappers for remaining MIXED files |
| cd3a565 | extract source_pool_utils from cross_form_autofill |
| 1b93bb8 | decouple pipeline_failure_ux from cross_form_autofill |
