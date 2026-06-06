---
name: document-quality-harness
description: 완성 DOCX 품질 개선 17단계 워크플로우 — 백업·유형분류·후처리·PSST·이미지제안·점수·게이트·리포트. DocumentQualityOrchestrator.run()으로 4~16단계를 단일 호출 수행.
---

# 문서 품질 하네스 워크플로우 (document-quality-harness)

대상: D:\auto_write — 완성 DOCX의 품질을 결정론적으로 후처리하고 점수화한다.
핵심 진입점: `app/auto_write/services/document_quality_orchestrator.py` 의 `DocumentQualityOrchestrator.run()`.

## 핵심 원칙 (먼저 읽어라)
- 원본 DOCX를 절대 덮어쓰지 마라. 출력 경로가 입력 경로와 같으면 `run()`이 `ValueError`를 던진다.
- 후처리 전 반드시 백업한다(`backup_original`). 백업 없이 원본을 수정하지 마라.
- AI 키 없이 전 단계 결정론적으로 동작한다. 유형 분류 보조만 선택적으로 `openai_service`를 사용한다.
- Secret/API Key/.env 내용을 출력하지 마라. 기존 정상 기능을 삭제하지 마라.
- 4~16단계(후처리~보완루프)는 `DocumentQualityOrchestrator.run()` **단일 호출**로 모두 수행된다. 아래 단계 분해는 내부 동작 설명이며, 운영자는 1·2단계 확인 후 `run()`을 호출하면 된다.

## 17단계 순서

### 1단계 — 입력확인 (순차 필수)
- 담당: executor
- 입력 DOCX가 존재하고 읽기 가능한지, 출력 경로가 입력과 다른지 확인한다.
- 실행:
  ```powershell
  cd D:\auto_write\app
  python _build_chochang.py inspect "C:\경로\문서.docx"
  ```

### 2단계 — 백업 (순차 필수)
- 담당: executor
- 후처리 전 원본을 타임스탬프 폴더로 복사한다. `run()` 내부에서 `backup_original(input_docx)` 호출.
- 백업 경로: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\`
- 함수: `DocumentQualityOrchestrator.backup_original(path) -> backup_dir`

### 3단계 — 유형분류 (순차)
- 담당: executor
- 함수: `document_type_classifier.classify_docx(path, openai_service=None) -> DocTypeResult`
- 유형코드: business_plan / rnd_plan / pitch_deck / consulting_report / policy_fund_report / certification_report / export_report / field_clinic_report / generic_submission
- 규칙기반 키워드 가중점수. 모호할 때만 openai 보조(선택).

### 4단계 — 안내문구삭제 (병렬 가능)
- 담당: executor
- 함수: `doc_quality_ops.remove_guide_paragraphs(doc) -> int`
- `docx_ops.GUIDE_MARKER_RE` 재사용.

### 5단계 — 글머리표공백 (병렬 가능)
- 담당: executor
- 함수: `doc_quality_ops.normalize_bullet_spacing(doc) -> int`

### 6단계 — 표공백 (병렬 가능)
- 담당: executor
- 함수: `doc_quality_ops.cleanup_table_whitespace(doc) -> int`

### 7단계 — 빈문단 (순차, 위 단계 결과 위에서 정리)
- 담당: executor
- 함수: `doc_quality_ops.remove_empty_paragraphs(doc) -> int`

### 8단계 — 글자크기 (기본 비활성)
- 담당: executor
- 함수: `doc_quality_ops.normalize_font_sizes(doc, enable=False) -> int`
- 기본 비활성. `--normalize-fonts` 플래그로만 활성화.

### 9단계 — 핵심문장강조 (병렬 가능)
- 담당: executor
- 함수: `doc_quality_ops.emphasize_key_sentences(doc, underline=False, require_numeric=True) -> int`
- 위 4~9단계는 `doc_quality_ops.run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False) -> QualityOpsReport` 로 일괄 수행된다.

### 10단계 — PSST/유형별구조검사 (병렬 가능)
- 담당: verifier
- 함수: `psst_check.check_psst(doc) -> PSSTReport`
- business_plan / pitch_deck 유형에서만 수행. 4영역(problem/solution/scale/team) × 4하위항목, 등급 누락/미흡/적정/우수.
- `project_service.ProjectService.PSST_PROBLEM_RE/PSST_SOLUTION_RE/PSST_SCALE_RE/PSST_TEAM_RE` 재사용.

### 11단계 — 이미지제안 (병렬 가능)
- 담당: designer
- 함수: `infographic_suggest.suggest_images(doc) -> InfographicReport`
- 키워드→시각화유형(막대/타임라인/조직도/플로우/포지셔닝맵), 캡션+생성프롬프트 제안. 실제 삽입은 안 함.

### 12단계 — 품질점수 (순차 필수)
- 담당: verifier
- 함수: `doc_quality_score.score_document(doc, doc_type, type_confidence, psst_ratio, image_suggestions, existing_images) -> QualityScore`
- 100점 9항목: 안내문구제거15 / 글머리표공백10 / 문단공백정리10 / 글자크기일관성15 / 표내부품질10 / 주요문장강조10 / 유형구조적합15 / PSST·보고서구조10 / 이미지제안5.

### 13단계 — 품질검사 게이트 (순차 필수)
- 담당: verifier
- 게이트: 90↑우수 / 85↑통과 / 70↑보완필요 / 70미만실패. `passed = 총점 >= 85`.

### 14단계 — 85미만시보완루프 (순차)
- 담당: executor
- `passed`가 아니면 후처리를 다시 적용한다. 최대 10회 반복, 점수 수렴 시 조기종료.

### 15단계 — 최종저장 (순차 필수)
- 담당: executor
- 보정된 doc을 출력 경로에 저장한다. 출력=입력이면 `ValueError`(원본 보호).

### 16단계 — 리포트생성 (순차)
- 담당: writer
- md + json 리포트를 `results_root`(D:\auto_write\results) 아래에 기록한다(`write_report=True`).

### 17단계 — Git상태확인 (순차 필수, 맨 마지막)
- 담당: executor
- 변경/생성 파일을 확인한다. main 직접 push 금지.
- 실행:
  ```powershell
  cd D:\auto_write
  git status
  ```

## 병렬 가능 작업 vs 순차 필수 작업
- 병렬 가능(읽기/탐지 중심, 서로 독립): 안내문구탐지(4) · 글머리표공백(5) · 표공백(6) · 핵심문장강조(9) · PSST검사(10) · 이미지제안(11).
- 순차 필수(상태 변경·집계·검증): 백업(2) → 빈문단정리(7) → 실제저장(15) → 품질점수(12) → 테스트 → Git(17).
  - 빈문단정리는 앞 후처리 결과 위에서 동작하므로 순차.
  - 품질점수·게이트·보완루프·저장은 누적 상태에 의존하므로 순차.

## 표준 실행 명령 (PowerShell)
```powershell
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx"
python document_quality_orchestrator.py 문서.docx --output 결과.docx --underline
python document_quality_orchestrator.py --rollback "..\results\backup\<ts>" 결과.docx
python _build_chochang.py inspect "결과.docx"
```
래퍼: `python scripts\run_document_quality_harness.py "C:\경로\문서.docx"`

CLI 인자: `input [--output/-o] [--no-emphasis] [--underline] [--keep-guides] [--normalize-fonts] [--no-report] [--json] [--rollback BACKUP_DIR TARGET]`

## 단일 호출 요약 (운영자용)
4~16단계는 아래 한 호출로 끝난다.
```python
DocumentQualityOrchestrator(results_root, openai_service=None).run(
    input_docx, output_docx=None,
    emphasize=True, underline=False, remove_guides=True,
    normalize_fonts=False, write_report=True,
) -> HarnessResult
```
파이프라인: 백업 → 유형분류 → run_all 후처리 → PSST(business_plan/pitch_deck만) → 이미지제안 → 점수 → 게이트 → (미달 시 최대 10회 보완루프, 수렴 시 조기종료) → 출력저장 → 리포트(md+json).
롤백: `DocumentQualityOrchestrator.rollback(backup_dir, target) -> bool` (staticmethod).

## 테스트
```powershell
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q
```
