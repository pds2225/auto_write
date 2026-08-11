# Import Graph Audit

> 브랜치: `refactor/repo-split-pm`
> 조사일: 2026-08-07
> 기준: `app/core/`, `app/resume/`, `app/bizplan/` 새 패키지

## 금지 dependency 검사

| 규칙 | 위반 수 | 비고 |
|------|---------|------|
| core → resume | 0 | - |
| core → bizplan | 0 | - |
| resume → bizplan | 0 | - |
| bizplan → resume | 0 | - |

## 허용 dependency (확인됨)

| 경로 | 대상 | 비고 |
|------|------|------|
| resume → core | `auto_write.services.*` | compatibility import (원본 아직 존재) |
| resume → auto_write.services | hwpx_fill, doc_text_extract, cross_form_autofill, hwpx_resume_supplement, hwpx_layout_fix | 원본 모듈 참조 |
| bizplan → core | `auto_write.services.*` | compatibility import (원본 아직 존재) |
| bizplan → auto_write.services | docx_ops, hwp_docx_convert, hwpx_fill, psst_check, usage_acceptance, submittable_filler, conversion_fidelity | 원본 모듈 참조 |
| bizplan → auto_write | models, utils | 분석 모듈 참조 |

## 오류 (없음)

- `core/docx/tests/test_resume_form_fill.py:187` — `from resume_fill import main`은 `resume` 도메인이 아닌 `app/resume_fill.py` CLI 스크립트를 참조. 위반 아님.

## 남은 MIXED 파일

| 파일 | 사유 |
|------|------|
| cross_form_autofill.py | ~90% BIZPLAN + ~10% 범용 rank_source_pool. 추출 필요 |

## 호환 wrapper 필요성

현재 phase에서는 auto_write 원본을 보존하고 있어 compatibility wrapper 불필요.
추후 원본 제거 시 `auto_write.services.docx_ops` → `core.docx.services.docx_ops` re-export wrapper 필요.
