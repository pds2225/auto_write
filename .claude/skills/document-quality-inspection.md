---
name: document-quality-inspection
description: >-
  완성된 결과 DOCX를 검수(inspection)한다. _build_chochang.py inspect 로 문단·표를 덤프하고,
  남은 가이드 문구(※/<...>/작성요령/예시/OOO)·placeholder 빈칸(○○○)·필수입력 누락을
  찾아내며, 품질점수를 재산정해 회귀(이전 대비 악화)를 확인한다.
  다음 요청 시 적극적으로 이 스킬을 사용하라: "결과 문서 검수", "DOCX 검수해줘",
  "가이드 문구 남았는지 확인", "빈칸/placeholder 점검", "필수 입력 누락 확인",
  "품질점수 다시 매겨줘", "회귀 검사", "후처리 결과 점검", "최종 제출 전 점검".
  재실행·재검수·다시 확인·수정 후 재점검·보완 후 회귀 확인 요청도 모두 이 스킬로 처리하라.
---

## 목적

완성(또는 후처리 완료)된 결과 DOCX가 실제로 제출 가능한 상태인지 검수한다.
세 가지를 한 번에 수행한다.

1. 문단·표 구조 덤프로 눈으로 내용 확인(`_build_chochang.py inspect`).
2. 잔존 결함 탐지: 가이드 문구, placeholder 빈칸, 필수입력 누락(`qa_service.build_report`).
3. 품질점수 재산정(`doc_quality_score.score_document`)으로 이전 결과 대비 회귀(점수 하락) 확인.

이 스킬은 검수·진단 전용이다. DOCX를 수정하지 않는다.
수정이 필요하면 후처리 스킬(`document-quality-orchestrator` 또는 세부 스킬)로 넘긴다.

## 적용 대상

- 후처리를 끝낸 결과 DOCX(`results\` 출력물) 또는 외부에서 받은 완성 DOCX.
- 유형: business_plan / rnd_plan / pitch_deck / consulting_report / policy_fund_report /
  certification_report / export_report / field_clinic_report / generic_submission.
- 원본 양식 DOCX는 검수 대상이 아니다(가이드 문구가 정상적으로 가득하므로 검수 의미 없음).

## 탐지 규칙

검수에서 잡아내는 항목은 실제 코드 동작과 정확히 일치한다.

- 가이드 문구 잔존: `qa_service.GUIDE_MARKER_RE` = `(※|<[^>]+>|기재|작성요령|작성방법|예시|OOO|○○○)`.
  - `qa_service.CRITICAL_GUIDE_MARKER_RE`에 걸리면 errors(치명), 아니면 warnings(경고)로 분류.
  - `qa_service._collect_guide_markers(document, limit=12)`가 최대 12개 수집, 앞 6개를 보고.
- placeholder 빈칸: `qa_service._collect_placeholder_pages(document, limit=8)`가 `○○○` 류 빈칸이 남은
  페이지 번호를 최대 8개 수집 → "N번째 페이지에 빈 칸이 남아있습니다" warnings.
- 필수입력 누락: `qa_service.build_report`가 `profile.questions` 중 `required=True` 항목을 검사.
  target 종류(project_meta / organization_profile / section / table_cell / 기타)별로
  결과 문서의 앵커 뒤 내용·표 셀 텍스트가 비어 있으면 "필수입력" errors.
- 산출물 부재: 출력 DOCX가 존재하지 않으면 "산출물" errors.
- 구조 덤프: `inspect`는 비어있지 않은 문단(인덱스+앞 130자)과 모든 표(행x열, 셀 앞 22자)를 출력.
- 점수 재산정: `doc_quality_score.score_document(doc, doc_type, type_confidence, psst_ratio,
  image_suggestions, existing_images)` → `QualityScore`. 게이트: 90 우수 / 85 통과 / 70 보완 / 미만 실패.
  `passed = 총점 >= 85`.

## 수정 규칙

이 스킬은 DOCX를 절대 수정하지 않는다(읽기·점수 산정만).

- 검수 결과 errors가 있으면: 어떤 항목인지 보고하고, 수정은 후처리 스킬로 위임한다.
  - 가이드 문구 잔존 → `docx-template-cleanup` / `doc_quality_ops.remove_guide_paragraphs`.
  - 점수 하락·구조 미흡 → `document-quality-orchestrator` 재실행으로 보완 루프 가동.
- 회귀(이전 검수 대비 총점 하락 또는 errors 증가)가 확인되면: 직전 백업
  `results\backup\<YYYYMMDD_HHMMSS>\` 로 롤백을 권고한다(이 스킬은 롤백을 직접 실행하지 않음).

## 예외 규칙

- 원본 양식/템플릿 DOCX는 검수하지 않는다(가이드 문구가 정상이므로 거짓 결함 폭증).
- `qa_service._is_non_business_label`에 걸리는 비사업 라벨 질문/이미지 슬롯은 필수입력 검사에서 제외(코드 기본 동작).
- `qa_service.build_report`는 단독 DOCX만으로는 호출 불가하다. profile·project_input·render_result·images·evidence가
  필요하므로, 그 객체들이 없는 외부 완성 DOCX는 inspect 덤프 + 점수 재산정 + 가이드/빈칸 정규식 점검까지만 수행한다.
- AI 키 없이 전 과정 동작한다(점수·정규식 검사 모두 결정론적). 분류 보조만 선택적 AI.

## 테스트 방법 (실제 PowerShell 명령)

```powershell
# 1) 결과 DOCX 구조 덤프(문단·표 눈으로 확인)
cd D:\auto_write\app
python _build_chochang.py inspect "결과.docx"

# 2) 후처리 + 점수 재산정 전체 파이프라인(검수 점수까지 한 번에)
python document_quality_orchestrator.py "결과.docx" -o "검수출력.docx" --no-report
#   --json 을 붙이면 점수·게이트 결과를 JSON 으로 받아 회귀 비교에 쓴다.
python document_quality_orchestrator.py "결과.docx" -o "검수출력.docx" --json

# 3) 회귀 확인용 하네스 테스트
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q
```

가이드/빈칸 잔존 여부는 위 1)의 inspect 덤프에서 `※`, `<...>`, `작성요령`, `예시`, `○○○`,
`OOO` 문자열이 보이는지로 즉시 확인한다.

## 실패 시 롤백 기준

- 검수 결과가 직전보다 나빠진 경우(총점 하락 또는 errors 신규 발생) = 회귀로 판정.
- 회귀 판정 시: 후처리 직전 백업으로 복구한다.

```powershell
cd D:\auto_write\app
python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" "결과.docx"
```

- 롤백은 `DocumentQualityOrchestrator.rollback(backup_dir, target)` 정적 메서드를 호출한다.
- 원본 DOCX는 절대 덮어쓰지 않는다(출력=입력 경로면 ValueError). 백업 없이 수정하지 않는다.

## 품질 점수 반영 (어느 배점 항목에 영향)

이 스킬의 검수는 `doc_quality_score.score_document`의 100점 배점을 재확인·재산정한다.
검수에서 결함이 잡히면 직접적으로 아래 배점이 깎인다.

- 안내문구 제거 15점 ← 가이드 문구(`GUIDE_MARKER_RE`) 잔존 시 감점.
- 유형 구조 적합 15점 ← 필수입력 누락·구조 미흡 시 감점.
- 글머리표 공백 10 / 문단 공백 정리 10 / 표 내부 품질 10 / 주요 문장 강조 10 ← 후처리 결과 반영.
- PSST·보고서 구조 10 ← business_plan/pitch_deck 한정 PSST 비율 반영.
- 이미지 제안 5 ← 인포그래픽 제안 반영.
- 게이트: 총점 90 우수 / 85 통과(passed) / 70 보완필요 / 70 미만 실패.

## 연결 코드·CLI (실제 함수/명령)

- 구조 덤프: `app/_build_chochang.py` → `inspect <docx>` (문단·표 덤프; `analyze/generate/finalize/struct/heads`도 동일 CLI).
- 잔존 결함 검수: `app/auto_write/services/qa_service.py`
  - `QAService.build_report(profile, project_input, render_result, images, evidence, preview_result=None) -> dict`
  - `GUIDE_MARKER_RE`, `CRITICAL_GUIDE_MARKER_RE`, `_collect_guide_markers(document, limit=12)`,
    `_collect_placeholder_pages(document, limit=8)` 재사용.
- 유형 분류: `app/auto_write/services/document_type_classifier.py` → `classify_docx(path, openai_service=None) -> DocTypeResult`.
- PSST(해당 유형만): `app/auto_write/services/psst_check.py` → `check_psst(doc) -> PSSTReport`.
- 이미지 제안: `app/auto_write/services/infographic_suggest.py` → `suggest_images(doc) -> InfographicReport`.
- 점수 재산정: `app/auto_write/services/doc_quality_score.py`
  → `score_document(doc, doc_type, type_confidence, psst_ratio, image_suggestions, existing_images) -> QualityScore`.
- 통합 실행/롤백: `app/auto_write/services/document_quality_orchestrator.py`
  → `DocumentQualityOrchestrator(results_root, openai_service=None).run(...)`,
    `backup_original(path)`, `@staticmethod rollback(backup_dir, target)`.
- 진입점 CLI: `app/document_quality_orchestrator.py`(`--json`/`--no-report`/`--rollback` 지원),
  래퍼 `scripts/run_document_quality_harness.py`.
- 테스트: `app/tests/test_document_quality_harness.py` (`python -m pytest tests/test_document_quality_harness.py -q`).
