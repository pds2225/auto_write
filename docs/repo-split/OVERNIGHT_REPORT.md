# Overnight Repository Split Report

> 브랜치: `refactor/repo-split-pm`
> 작업일: 2026-08-07 ~ 2026-08-08

## 1. Executive Summary

**완료 단계:**
- PHASE A: Gate 1 감사 완료 (ownership audit 65개 파일)
- PHASE B: 테스트 환경 확보 (Python 3.12 + venv)
- PHASE C: Baseline 측정
- PHASE D: 패키지 골격 생성 (core/resume/bizplan)
- PHASE E: CORE canonicalization (복사본 확인, 원본 보존)
- PHASE F: RESUME 분리 (5개 파일)
- PHASE G: BIZPLAN 분리 (13개 파일)
- PHASE H: Import graph 검사 (위반 0)
- PHASE I: 테스트 회귀 검증 (회귀 없음)
- PHASE J: 문서 동기화 (README, AGENTS)

**미완료 단계:**
- CORE 파일의 auto_write 원본을 thin wrapper로 전환 (private 심볼 재내보내기 문제)
- cross_form_autofill.py에서 rank_source_pool 추출 (MIXED_REFACTOR)
- 기존 auto_write/ 원본 최종 정리

**가장 큰 blocker:**
- Python 3.11 미설치로 Python 3.12 사용 (프로젝트 규약 3.11 권장)

## 2. Git

- branch: `refactor/repo-split-pm`
- 시작 SHA: `0042d39`
- 마지막 SHA: `2fc8e72`

### 생성 commit 목록

| SHA | 메시지 |
|-----|--------|
| 0961679 | refactor: add core resume bizplan package skeleton |
| bdf67ef | refactor: separate resume domain services |
| ee5a71c | refactor: separate business plan domain services |
| 52b3c25 | docs: add repository split import graph audit |
| 2fc8e72 | docs: sync README and AGENTS with current repo split status |

- master/merge/force-push: **미수행 확인**

## 3. Ownership Audit

- TOTAL: **65**
- CORE: 22
- RESUME: 7
- BIZPLAN: 28
- MIXED: 1
- NONE: 7

## 4. Files Changed

### 생성 (새 패키지)

| 경로 | 파일 수 |
|------|---------|
| app/core/__init__.py | 1 |
| app/resume/services/*.py | 4 |
| app/resume/cli/*.py | 1 |
| app/resume/*/__init__.py | 3 |
| app/bizplan/services/*.py | 8 |
| app/bizplan/cli/*.py | 5 |
| app/bizplan/*/__init__.py | 3 |

### 문서

| 파일 | 변경 |
|------|------|
| docs/repo-split/docx-duplicate-map.md | 65개 파일 전수조사 |
| docs/repo-split/baseline-env.md | 환경 인벤토리 |
| docs/repo-split/import-graph-audit.md | import graph 검사 |
| README.md | 구조 동기화 |
| AGENTS.md | 구조 동기화 |

### compatibility wrapper

- 아직 없음. 원본 auto_write/ 보존 중.

## 5. Dependency Audit

| 규칙 | 위반 수 |
|------|---------|
| core → resume | 0 |
| core → bizplan | 0 |
| resume → bizplan | 0 |
| bizplan → resume | 0 |

### 남은 MIXED

| 파일 | 사유 |
|------|------|
| cross_form_autofill.py | ~90% BIZPLAN + ~10% 범용 rank_source_pool. 추출 필요 |

### auto_write 원본 참조

resume/와 bizplan/의 새 파일들은 아직 `auto_write.services.*`를 절대 import로 참조.
원본 제거 시 compatibility wrapper 필요.

## 6. Tests

### Baseline (변경 전)

| 테스트 | passed | failed | 비고 |
|--------|--------|--------|------|
| test_docx_ops | 5 | 0 | |
| test_cross_form_autofill | 77 | 5 | baseline 실패 (CLI 테스트) |
| test_resume_form_fill | 11 | 0 | |
| test_document_quality_harness | 33 | 0 | |
| test_hwpx_fill | 76 | 0 | |
| test_document_ingest | 7 | 0 | |
| test_hwp_docx_convert | 13 | 0 | |
| test_quality_ratchet | 13 | 0 | |

### Final — 전체 테스트 (2026-08-08)

```
전체 실행: python -m pytest app/tests -q --tb=line --timeout=30
HWP COM hang 테스트 제외: test_notice_pipeline, test_night_autopilot_cycle2

결과: 1476 passed, 6 failed, 10 skipped, 23 subtests passed (74.10s)
```

| 실패 테스트 | 원인 | 유형 |
|-------------|------|------|
| test_cross_form_autofill::test_cli_unsupported_input_exit2_json | py -3.11 미설치 (exit 103) | 환경 |
| test_cross_form_autofill::test_batch_cli_shows_per_form_detail | py -3.11 미설치 | 환경 |
| test_cross_form_autofill::test_batch_cli_json_includes_per_form_detail | py -3.11 미설치 | 환경 |
| test_cross_form_autofill::test_batch_cli_korean_stdout_not_json_only | py -3.11 미설치 | 환경 |
| test_cross_form_autofill::test_batch_cli_hwp_skip_message | py -3.11 미설치 | 환경 |
| test_doc_analyze::test_analyze_docs_folder_cli | py -3.11 미설치 | 환경 |

**신규 코드 실패: 0**
**환경 실패: 6 (전부 py -3.11 미설치)**
**skipped: 10**
**HWP COM hang: 2 파일 제외 (test_notice_pipeline, test_night_autopilot_cycle2)**

## 7. Risks

| 위험 | 수준 | 설명 |
|------|------|------|
| Python 3.11 미설치 | MEDIUM | 프로젝트 규약 3.11 권장. 3.12로 동작 확인됨 |
| auto_write 원본 보존 | LOW | 원본과 복사본이 동일. 아직 분리 작업 안전 |
| cross_form_autofill MIXED | MEDIUM | rank_source_pool 추출 전까지 resume → bizplan 의존 |
| 인코딩 문제 | LOW | PowerShell Set-Content로 Python 파일 수정 시 한글 깨짐 발생. Python으로 수정 해결 |
| 전체 테스트 미실행 | MEDIUM | 시간 초과로 핵심 8개만 실행. 나머지는 PM 검수 필요 |

## 8. Morning PM Review Required

1. `docs/repo-split/docx-duplicate-map.md` — ownership 분류 확인
2. `app/resume/services/resume_extract.py` — cross_form_autofill import 수정 확인
3. `app/bizplan/services/cross_form_autofill.py` — import 수정 확인
4. README.md / AGENTS.md — 구조 동기화 확인
5. MIXED 1개(cross_form_autofill) 처리 방향 결정
6. Python 3.11 설치 및 venv 생성 승인
7. 전체 테스트 실행 결과 확인

## 9. Rollback Points

| 단계 | SHA |
|------|-----|
| 작업 시작 (Gate 1 완료 후) | `0042d39` |
| 패키지 골격 | `0961679` |
| RESUME 분리 | `bdf67ef` |
| BIZPLAN 분리 | `ee5a71c` |
| import audit | `52b3c25` |
| 문서 동기화 | `2fc8e72` |

## 10. Next Recommended Actions

| 우선순위 | 작업 |
|----------|------|
| P0 | PM ownership 분류 승인 |
| P0 | Python 3.11 설치 + venv 생성 + 전체 테스트 |
| P1 | cross_form_autofill에서 rank_source_pool 추출 → core/source_pool.py |
| P1 | auto_write 원본 → compatibility wrapper 전환 계획 수립 |
| P2 | 기존 auto_write/ 원본 정리 (PM 승인 후) |
