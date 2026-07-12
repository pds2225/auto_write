# HARNESS_TEAM_DESIGN — DOCX 품질 후처리 하네스 팀 설계

대상 프로젝트: `D:\auto_write` (한국 정부지원사업 문서 자동생성 + 완성 DOCX 품질 후처리)
실행 모드: **에이전트 팀(기본값)** — 2개 이상 협업이므로 서브 에이전트 단일 호출이 아닌 에이전트 팀으로 운영한다.
파이프라인 구현체: `app/auto_write/services/document_quality_orchestrator.py` 의 `DocumentQualityOrchestrator.run(...)`.

> 2026-06-07 슬림화: 기존 12개 에이전트를 책임·코드모듈 기준으로 **6개**에 병합했다. 코드 모듈·함수는 그대로이며, 한 에이전트가 여러 모듈을 묶어 담당한다.

---

## 목차

1. 6개 에이전트 역할표
2. 실행 모드 (에이전트 팀 기본)
3. 데이터 흐름
4. 파이프라인 순서
5. 병렬 가능 작업 / 순차 필수 작업
6. 에이전트 ↔ 코드 모듈 매핑표
7. 팀 크기 가이드
8. 안전 원칙 (절대 준수)

---

## 1. 6개 에이전트 역할표

| # | 에이전트 | 역할(명령형 요약) | 입력 | 출력 | AI 사용 | 구 에이전트 |
|---|----------|-------------------|------|------|---------|-------------|
| 1 | doc-architect | 파이프라인 전체 설계·단계 순서 확정·조율. 입력 DOCX와 옵션을 받아 실행 계획을 세우고 각 단계를 조율한다. | input_docx, 옵션 | 실행 계획(단계 목록) | 미사용 | document-architect |
| 2 | doc-safety-guard | 후처리 전 원본을 백업하고 실패 시 복원한다. Secret/API Key/.env 노출·원본 덮어쓰기 위험을 차단하는 보안 게이트도 겸한다. | input_docx / backup_dir / 전체 산출물 | backup_dir / bool / 통과·차단 | 미사용 | backup-rollback-agent + security-agent |
| 3 | doc-analyzer | (읽기 전용) 유형 9종 분류 + PSST 4영역 충족도 점검 + 인포그래픽 삽입 제안을 수행한다. 문서를 변형하지 않는다. | Document, text, filename | DocTypeResult / PSSTReport / InfographicReport | 모호 시에만 분류 보조 | document-type-classifier + psst-review-agent + infographic-suggestion-agent |
| 4 | doc-postprocessor | (DOCX 변형) 안내문구·빈 문단 제거, 글머리표·표 내부 공백·글자크기 정규화, 수치 포함 핵심 문장 강조를 일괄 수행한다. | Document | QualityOpsReport | 미사용 | template-cleanup-agent + formatting-normalizer + content-emphasis-agent |
| 5 | doc-quality-gate | 100점 9항목 배점으로 채점하고 게이트(90/85/70)를 판정한다. 출력 DOCX의 구조·재현성·기존 기능 회귀도 검수한다. | 후처리·분류·PSST·이미지 결과 / output_docx | QualityScore / 검증 결과 | 미사용 | quality-gate-agent + qa-document-agent |
| 6 | doc-writer | md+json 리포트로 전 단계 결과를 종합하고 사용법·HANDOFF를 문서화한다. | HarnessResult | 리포트 파일 | 미사용 | documentation-agent |

---

## 2. 실행 모드 (에이전트 팀 기본)

- 기본값은 **에이전트 팀**이다. doc-architect가 코디네이터, 나머지 5개가 작업 에이전트로 참여한다.
- 협업 조율은 SendMessage 기반 실시간 메시지로 단계 완료/실패를 전달한다.
- 단일 파일·단순 점검은 팀 없이 직접 처리 가능하나, 본 후처리 파이프라인은 다단계이므로 팀이 기본이다.
- 게이트·검수(doc-quality-gate)와 보안 게이트(doc-safety-guard)는 별도 패스로 실행한다. 작성 에이전트(doc-postprocessor)가 자기 산출물을 자기 컨텍스트에서 승인하지 않는다(doc-quality-gate가 승인 패스를 맡는다).

---

## 3. 데이터 흐름

```
doc-architect (설계·조율)
        │  실행 계획
        ▼
doc-safety-guard.backup_original(input)  ← 순차 필수(최우선)
        │  backup_dir
        ▼
doc-analyzer.classify_docx / classify_text  → DocTypeResult
        │
        ▼
[후처리 묶음] doc-postprocessor : doc_quality_ops.run_all(doc, ...)
   ├─ 안내문구·빈문단 제거       : remove_guide_paragraphs, remove_empty_paragraphs
   ├─ 글머리표·표·글자크기 정규화 : normalize_bullet_spacing, cleanup_table_whitespace, normalize_font_sizes
   └─ 핵심문장 강조             : emphasize_key_sentences
        │  QualityOpsReport
        ▼
doc-analyzer.check_psst(doc)           (business_plan / pitch_deck 한정) → PSSTReport
        │
        ▼
doc-analyzer.suggest_images(doc)       → InfographicReport
        │
        ▼
doc-quality-gate.score_document(...)  → QualityScore (passed = 총점>=85)
        │  미달 시 보완 루프(최대 10회, 수렴 시 조기종료) → 후처리 묶음으로 복귀
        ▼
출력 저장(output_docx)                  ← 순차 필수 (입력=출력 경로면 ValueError)
        │
        ▼
doc-quality-gate (검수: 구조·재현성·회귀) → doc-safety-guard (보안 최종 게이트) → doc-writer (md+json 리포트)
```

- 게이트 임계: **90↑ 우수 / 85↑ 통과 / 70↑ 보완필요 / 70미만 실패**, `passed = 총점>=85`.
- 보완 루프: doc-quality-gate 미달 시 doc-postprocessor 후처리 묶음을 재실행. 최대 10회, 점수 수렴(개선 없음) 시 조기종료.

---

## 4. 파이프라인 순서

`DocumentQualityOrchestrator.run(input_docx, output_docx=None, emphasize=True, underline=False, remove_guides=True, normalize_fonts=False, write_report=True)` 기준 단계 순서:

1. **백업** (doc-safety-guard) — `backup_original(input_path)` (원본 보존, 순차 필수)
2. **유형 분류** (doc-analyzer) — `classify_docx` / `classify_text` → `DocTypeResult`
3. **후처리** (doc-postprocessor) — `run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False)` → `QualityOpsReport`
4. **PSST 점검** (doc-analyzer) — `check_psst(doc)` (business_plan / pitch_deck 한정) → `PSSTReport`
5. **이미지 제안** (doc-analyzer) — `suggest_images(doc)` → `InfographicReport`
6. **채점** (doc-quality-gate) — `score_document(...)` → `QualityScore`
7. **게이트** (doc-quality-gate) — `passed = 총점>=85` 판정, 미달 시 보완 루프(최대 10회, 수렴 시 조기종료)
8. **출력 저장** — `output_docx` 저장 (순차 필수, 입력=출력이면 ValueError)
9. **리포트** (doc-writer) — md + json 생성(`write_report=True`)

---

## 5. 병렬 가능 작업 / 순차 필수 작업

### 병렬 가능
| 묶음 | 담당 에이전트 | 근거 |
|------|----------------|------|
| 후처리 정규화 (안내문구·서식·강조) | doc-postprocessor | 동일 Document 객체에 대한 독립 변환. `run_all` 내부에서 결정론적으로 순차 호출되지만 설계상 상호 독립 작업 |
| 분석 산출 (PSST·이미지 제안) | doc-analyzer | 둘 다 읽기 전용 분석, 서로 의존 없음 |

### 순차 필수 (반드시 직렬)
| 단계 | 담당 | 이유 |
|------|------|------|
| 백업(backup_original) | doc-safety-guard | 후처리 시작 전 반드시 선행. 백업 없이 원본 수정 금지 |
| 채점(score_document) | doc-quality-gate | 모든 후처리·분류·PSST·이미지 결과가 모여야 산출 가능 |
| 출력 저장 | doc-architect | 모든 변환 확정 후 1회. 입력=출력 경로면 ValueError |
| 테스트/검증 | doc-quality-gate | 출력 DOCX 확정 후 실행. `tests/test_document_quality_harness.py` |

---

## 6. 에이전트 ↔ 코드 모듈 매핑표

| 에이전트 | 모듈 (`app/auto_write/services/`) | 핵심 함수/클래스 | 반환 |
|----------|-----------------------------------|------------------|------|
| doc-architect | document_quality_orchestrator.py | `DocumentQualityOrchestrator.run(...)` | `HarnessResult` |
| doc-safety-guard | document_quality_orchestrator.py | `backup_original(input_path)`, `@staticmethod rollback(backup_dir, target_path)` + (보안 게이트 규칙: Secret/API Key/.env 비노출, 입력=출력 ValueError 확인) | `Path` / bool / 통과·차단 |
| doc-analyzer | document_type_classifier.py · psst_check.py · infographic_suggest.py | `classify_text(text, filename="")`, `classify_docx(path, openai_service=None)`, `check_psst(doc)`, `suggest_images(doc, max_suggestions=8)` | `DocTypeResult` / `PSSTReport` / `InfographicReport` |
| doc-postprocessor | doc_quality_ops.py | `run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False)` (구성: `remove_guide_paragraphs`, `remove_empty_paragraphs`, `normalize_bullet_spacing`, `cleanup_table_whitespace`, `normalize_font_sizes`, `emphasize_key_sentences`) | `QualityOpsReport` |
| doc-quality-gate | doc_quality_score.py · tests/test_document_quality_harness.py | `score_document(doc, doc_type, type_confidence, psst_ratio, image_suggestions, existing_images)`, `python -m pytest tests/test_document_quality_harness.py -q` | `QualityScore` / 통과·실패 |
| doc-writer | document_quality_orchestrator.py | `run(..., write_report=True)` → md+json | 리포트 파일 |

재사용 헬퍼(신규 작성 금지, docx_ops.py 검증본 사용): `_iter_body_paragraphs`, `_paragraph_text`, `GUIDE_MARKER_RE`.
psst_check 재사용 정규식: `project_service.PSST_PROBLEM_RE/PSST_SOLUTION_RE/PSST_SCALE_RE/PSST_TEAM_RE`.

### 채점 9항목 배점 (doc-quality-gate / doc_quality_score.py, 100점)
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

### 문서 유형 코드 (doc-analyzer / document_type_classifier)
`business_plan`(사업계획서), `rnd_plan`(R&D연구개발계획서), `pitch_deck`(발표평가), `consulting_report`(컨설팅), `policy_fund_report`(정책자금), `certification_report`(인증), `export_report`(수출컨설팅), `field_clinic_report`(현장클리닉), `generic_submission`(기타).

---

## 7. 팀 크기 가이드

| 작업 규모 | 권장 팀 구성 | 활성 에이전트 |
|-----------|--------------|----------------|
| 단일 문서 1회 후처리 | 최소(3) | doc-architect + doc-safety-guard + doc-quality-gate |
| 표준 후처리 | 표준(5) | + doc-analyzer, doc-postprocessor |
| 전체 파이프라인(보고서 포함) | 전체(6) | + doc-writer |
| 대량 배치 / 회귀 검증 | 전체(6) + 반복 | doc-quality-gate 보완 루프(최대 10회) + 회귀 테스트 강화 |

- 게이트·검수(doc-quality-gate)와 보안 게이트(doc-safety-guard)는 어떤 규모에서도 작성 에이전트(doc-postprocessor)와 **분리된 패스**로 둔다.
- doc-safety-guard의 보안 게이트는 항상 최종 단계로 1회 실행한다(생략 금지).

---

## 8. 안전 원칙 (절대 준수)

- 원본 DOCX 절대 덮어쓰기 금지 — 출력=입력 경로면 `ValueError`. 후처리 전 반드시 `backup_original`.
- AI 키 없이 전 단계 결정론적 동작 — 분류 보조만 선택적 AI.
- Secret/API Key/.env 내용 출력 금지. 기존 정상 기능 삭제 금지. 백업 없이 원본 수정 금지.
- 기존 서비스(docx_ops, qa_service, project_service, evaluation_service) 재사용 우선, 신규 헬퍼 중복 작성 금지.
- 검증 없이 완료로 보고 금지 — doc-quality-gate 통과 후에만 완료 처리.
