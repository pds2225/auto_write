# HARNESS_TEAM_DESIGN — DOCX 품질 후처리 하네스 팀 설계

대상 프로젝트: `D:\auto_write` (한국 정부지원사업 문서 자동생성 + 완성 DOCX 품질 후처리)
실행 모드: **에이전트 팀(기본값)** — 2개 이상 협업이므로 서브 에이전트 단일 호출이 아닌 에이전트 팀으로 운영한다.
파이프라인 구현체: `app/auto_write/services/document_quality_orchestrator.py` 의 `DocumentQualityOrchestrator.run(...)`.

---

## 목차

1. 12개 에이전트 역할표
2. 실행 모드 (에이전트 팀 기본)
3. 데이터 흐름
4. 파이프라인 순서
5. 병렬 가능 작업 / 순차 필수 작업
6. 에이전트 ↔ 코드 모듈 1:1 매핑표
7. 팀 크기 가이드
8. 안전 원칙 (절대 준수)

---

## 1. 12개 에이전트 역할표

| # | 에이전트 | 역할(명령형 요약) | 입력 | 출력 | AI 사용 |
|---|----------|-------------------|------|------|---------|
| 1 | document-architect | 파이프라인 전체 설계·단계 순서 확정. 입력 DOCX와 옵션을 받아 실행 계획을 세운다. | input_docx, 옵션 | 실행 계획(단계 목록) | 미사용 |
| 2 | template-cleanup | 안내문구·빈 문단 제거로 템플릿 잔여물을 정리한다. | Document | 제거 건수 | 미사용 |
| 3 | formatting-normalizer | 글머리표 공백·표 내부 공백·글자크기를 정규화한다. | Document | 정규화 건수 | 미사용 |
| 4 | content-emphasis | 수치 포함 핵심 문장을 굵게/밑줄로 강조한다. | Document | 강조 건수 | 미사용 |
| 5 | document-type-classifier | 본문·파일명을 규칙기반 키워드 가중점수로 9개 유형 분류한다. | text, filename | DocTypeResult | 모호 시에만 선택적 보조 |
| 6 | psst-review | PSST 4영역×4항목 충족도를 점검한다(business_plan/pitch_deck 한정). | Document | PSSTReport | 미사용 |
| 7 | infographic-suggestion | 키워드→시각화유형 매핑으로 이미지 삽입을 제안한다(실제 삽입 안 함). | Document | InfographicReport | 미사용 |
| 8 | quality-gate | 100점 9항목 배점으로 채점하고 게이트(90/85/70)를 판정한다. | 후처리·분류·PSST·이미지 결과 | QualityScore | 미사용 |
| 9 | backup-rollback | 후처리 전 원본을 백업하고, 실패 시 복원한다. | input_docx / backup_dir | backup_dir / bool | 미사용 |
| 10 | qa-document | 출력 DOCX를 검증한다(구조·재현성·기존 기능 회귀). | output_docx | 검증 결과 | 미사용 |
| 11 | security | Secret/API Key/.env 노출, 원본 덮어쓰기 위험을 차단하는 최종 게이트. | 전체 산출물 | 통과/차단 | 미사용 |
| 12 | documentation | md+json 리포트로 전 단계 결과를 종합한다. | HarnessResult | 리포트 파일 | 미사용 |

---

## 2. 실행 모드 (에이전트 팀 기본)

- 기본값은 **에이전트 팀**이다. document-architect가 코디네이터, 나머지 11개가 작업 에이전트로 참여한다.
- 협업 조율은 SendMessage 기반 실시간 메시지로 단계 완료/실패를 전달한다.
- 단일 파일·단순 점검은 팀 없이 직접 처리 가능하나, 본 후처리 파이프라인은 다단계이므로 팀이 기본이다.
- 모든 게이트(quality-gate, security)는 별도 패스로 실행한다. 작성 에이전트가 자기 산출물을 자기 컨텍스트에서 승인하지 않는다(qa-document/security가 승인 패스를 맡는다).

---

## 3. 데이터 흐름

```
document-architect (설계)
        │  실행 계획
        ▼
backup-rollback.backup_original(input)  ← 순차 필수(최우선)
        │  backup_dir
        ▼
document-type-classifier.classify_docx / classify_text  → DocTypeResult
        │
        ▼
[후처리 묶음] doc_quality_ops.run_all(doc, ...)
   ├─ template-cleanup        : remove_guide_paragraphs, remove_empty_paragraphs
   ├─ formatting-normalizer   : normalize_bullet_spacing, cleanup_table_whitespace, normalize_font_sizes
   └─ content-emphasis        : emphasize_key_sentences
        │  QualityOpsReport
        ▼
psst-review.check_psst(doc)            (business_plan / pitch_deck 한정) → PSSTReport
        │
        ▼
infographic-suggestion.suggest_images(doc) → InfographicReport
        │
        ▼
quality-gate.score_document(...)  → QualityScore (passed = 총점>=85)
        │  미달 시 보완 루프(최대 10회, 수렴 시 조기종료) → 후처리 묶음으로 복귀
        ▼
출력 저장(output_docx)                  ← 순차 필수 (입력=출력 경로면 ValueError)
        │
        ▼
qa-document (검증) → security (최종 게이트) → documentation (md+json 리포트)
```

- 게이트 임계: **90↑ 우수 / 85↑ 통과 / 70↑ 보완필요 / 70미만 실패**, `passed = 총점>=85`.
- 보완 루프: quality-gate 미달 시 후처리 묶음을 재실행. 최대 10회, 점수 수렴(개선 없음) 시 조기종료.

---

## 4. 파이프라인 순서

`DocumentQualityOrchestrator.run(input_docx, output_docx=None, emphasize=True, underline=False, remove_guides=True, normalize_fonts=False, write_report=True)` 기준 단계 순서:

1. **백업** — `backup_original(input_path)` (원본 보존, 순차 필수)
2. **유형 분류** — `classify_docx` / `classify_text` → `DocTypeResult`
3. **후처리** — `run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False)` → `QualityOpsReport`
4. **PSST 점검** — `check_psst(doc)` (business_plan / pitch_deck 한정) → `PSSTReport`
5. **이미지 제안** — `suggest_images(doc)` → `InfographicReport`
6. **채점** — `score_document(...)` → `QualityScore`
7. **게이트** — `passed = 총점>=85` 판정, 미달 시 보완 루프(최대 10회, 수렴 시 조기종료)
8. **출력 저장** — `output_docx` 저장 (순차 필수, 입력=출력이면 ValueError)
9. **리포트** — md + json 생성(`write_report=True`)

---

## 5. 병렬 가능 작업 / 순차 필수 작업

### 병렬 가능
| 묶음 | 에이전트 | 근거 |
|------|----------|------|
| 후처리 정규화 | template-cleanup, formatting-normalizer, content-emphasis | 동일 Document 객체에 대한 독립 변환. `run_all` 내부에서 결정론적으로 순차 호출되지만 설계상 상호 독립 작업 |
| 분석 산출 | psst-review, infographic-suggestion | 둘 다 읽기 전용 분석, 서로 의존 없음 |

### 순차 필수 (반드시 직렬)
| 단계 | 이유 |
|------|------|
| 백업(backup_original) | 후처리 시작 전 반드시 선행. 백업 없이 원본 수정 금지 |
| 채점(score_document) | 모든 후처리·분류·PSST·이미지 결과가 모여야 산출 가능 |
| 출력 저장 | 모든 변환 확정 후 1회. 입력=출력 경로면 ValueError |
| 테스트/검증(qa-document) | 출력 DOCX 확정 후 실행. `tests/test_document_quality_harness.py` |

---

## 6. 에이전트 ↔ 코드 모듈 1:1 매핑표

| 에이전트 | 모듈 (`app/auto_write/services/`) | 핵심 함수/클래스 | 반환 |
|----------|-----------------------------------|------------------|------|
| document-architect | document_quality_orchestrator.py | `DocumentQualityOrchestrator.run(...)` | `HarnessResult` |
| template-cleanup | doc_quality_ops.py | `remove_guide_paragraphs(doc, max_len=120)`, `remove_empty_paragraphs(doc, keep_single=True)` | int |
| formatting-normalizer | doc_quality_ops.py | `normalize_bullet_spacing(doc)`, `cleanup_table_whitespace(doc)`, `normalize_font_sizes(doc, enable=False)` | int |
| content-emphasis | doc_quality_ops.py | `emphasize_key_sentences(doc, underline=False, require_numeric=True)` | int |
| (후처리 통합) | doc_quality_ops.py | `run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False)` | `QualityOpsReport` |
| document-type-classifier | document_type_classifier.py | `classify_text(text, filename="")`, `classify_docx(path, openai_service=None)` | `DocTypeResult` |
| psst-review | psst_check.py | `check_psst(doc)` (재사용: `project_service.PSST_PROBLEM_RE/PSST_SOLUTION_RE/PSST_SCALE_RE/PSST_TEAM_RE`) | `PSSTReport` |
| infographic-suggestion | infographic_suggest.py | `suggest_images(doc, max_suggestions=8)` | `InfographicReport` |
| quality-gate | doc_quality_score.py | `score_document(doc, doc_type, type_confidence, psst_ratio, image_suggestions, existing_images)` | `QualityScore` |
| backup-rollback | document_quality_orchestrator.py | `backup_original(input_path)`, `@staticmethod rollback(backup_dir, target_path)` | `Path` / bool |
| qa-document | tests/test_document_quality_harness.py | `python -m pytest tests/test_document_quality_harness.py -q` | 통과/실패 |
| security | (게이트 규칙) | Secret/API Key/.env 비노출, 원본 비덮어쓰기(입력=출력 ValueError) 확인 | 통과/차단 |
| documentation | document_quality_orchestrator.py | `run(..., write_report=True)` → md+json | 리포트 파일 |

재사용 헬퍼(신규 작성 금지, docx_ops.py 검증본 사용): `_iter_body_paragraphs`, `_paragraph_text`, `GUIDE_MARKER_RE`.

### 채점 9항목 배점 (quality-gate / doc_quality_score.py, 100점)
| 항목 | 배점 |
|------|------|
| 안내문구 제거 | 15 |
| 글머리표 공백 | 10 |
| 문단 공백 정리 | 10 |
| 글자크기 일관성 | 15 |
| 표 내부 품질 | 10 |
| 주요 문장 강조 | 10 |
| 유형 구조 적합 | 15 |
| PSST·보고서 구조 | 10 |
| 이미지 제안 | 5 |

### 문서 유형 코드 (document-type-classifier)
`business_plan`(사업계획서), `rnd_plan`(R&D연구개발계획서), `pitch_deck`(발표평가), `consulting_report`(컨설팅), `policy_fund_report`(정책자금), `certification_report`(인증), `export_report`(수출컨설팅), `field_clinic_report`(현장클리닉), `generic_submission`(기타).

---

## 7. 팀 크기 가이드

| 작업 규모 | 권장 팀 구성 | 활성 에이전트 |
|-----------|--------------|----------------|
| 단일 문서 1회 후처리 | 최소(3) | document-architect + backup-rollback + quality-gate |
| 표준 후처리 | 표준(7) | + template-cleanup, formatting-normalizer, content-emphasis, document-type-classifier |
| 전체 파이프라인(보고서 포함) | 전체(12) | 전 에이전트 (psst-review, infographic-suggestion, qa-document, security, documentation 추가) |
| 대량 배치 / 회귀 검증 | 전체(12) + 반복 | quality-gate 보완 루프(최대 10회) + qa-document 회귀 테스트 강화 |

- 게이트(quality-gate, security)와 검증(qa-document)은 어떤 규모에서도 작성 에이전트와 **분리된 패스**로 둔다.
- security는 항상 최종 단계로 1회 실행한다(생략 금지).

---

## 8. 안전 원칙 (절대 준수)

- 원본 DOCX 절대 덮어쓰기 금지 — 출력=입력 경로면 `ValueError`. 후처리 전 반드시 `backup_original`.
- AI 키 없이 전 단계 결정론적 동작 — 분류 보조만 선택적 AI.
- Secret/API Key/.env 내용 출력 금지. 기존 정상 기능 삭제 금지. 백업 없이 원본 수정 금지.
- 기존 서비스(docx_ops, qa_service, project_service, evaluation_service) 재사용 우선, 신규 헬퍼 중복 작성 금지.
- 검증 없이 완료로 보고 금지 — qa-document 통과 후에만 완료 처리.
