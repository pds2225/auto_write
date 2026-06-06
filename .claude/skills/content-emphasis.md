---
name: content-emphasis
description: >
  완성된 DOCX의 핵심 성과 문장(매출·영업이익·고용·수출·특허·인증·R&D·KPI 등 정량지표 + 수치)에
  Bold(필요 시 Underline) 강조를 결정론적으로 적용하는 스킬. emphasize_key_sentences 를 호출한다.
  다음 요청 시 적극적으로 사용하라: "핵심 문장 강조", "성과 문장 굵게", "매출/고용/수출/특허 강조",
  "KPI 강조", "중요 문장 볼드 처리", "강조 다시 해줘", "강조 재실행", "강조 수정/보완",
  "밑줄 강조 추가", "과잉 강조 풀어줘", "강조만 다시 돌려줘", "auto_write 문서 강조".
  강조 단계만 부분 재실행·보완하거나, 품질점수의 '주요문장 강조(10점)' 항목을 끌어올릴 때 사용한다.
---

## 목적

완성된 정부지원사업 문서(사업계획서·R&D계획서·컨설팅/정책자금/인증/수출/현장클리닉 보고서)에서
평가자가 즉시 확인해야 할 **정량 성과 문장**을 굵게(Bold) 강조해 가독성과 설득력을 높인다.
쉽게 말하면, "매출 30억 달성", "신규 고용 12명", "수출 200만 달러" 같은 숫자가 들어간 성과 문장만
자동으로 진하게 만들어 눈에 띄게 한다. 과잉 강조는 오히려 가독성을 해치므로 **엄격히 제한**한다.

## 적용 대상

- 대상 파일: 완성된 `.docx` (양식 분석 후 AI 작성·렌더링까지 끝난 산출물).
- 대상 단락: **본문(body) 직계 단락만**. 표 셀 안 단락은 강조하지 않는다(표는 데이터라 강조 의미가 적음).
- 대상 문서 유형: 전 유형 공통(business_plan / rnd_plan / pitch_deck / consulting_report /
  policy_fund_report / certification_report / export_report / field_clinic_report / generic_submission).
- 비대상: 원본 양식 DOCX, 표 내부 텍스트, 4자 미만 짧은 제목/기호 단락.

## 탐지 규칙

`app/auto_write/services/doc_quality_ops.py` 의 `emphasize_key_sentences` 실제 동작과 정확히 일치한다.
단락이 **아래 조건을 모두** 만족할 때만 강조 후보가 된다.

1. **본문 직계 단락**일 것 (`_iter_body_paragraphs(doc)` 순회 대상 — 표 셀 제외).
2. 단락 전체 텍스트 길이가 **4자 이상**일 것 (`len(text) < 4` 이면 제외 → 제목/기호 단락 방지).
3. 핵심 키워드가 **하나 이상 포함**될 것. 키워드 목록(`_EMPHASIS_KEYWORDS`):
   `매출, 영업이익, 순이익, 고용, 채용, 수출, 특허, 인증, R&D, 연구개발, KPI, 목표, 기대효과,`
   `투자유치, 점유율, 성장률, ROI, 매출액, 거래액, MAU, 전환율, 원가절감`.
4. **수치 동반**일 것 (`require_numeric=True` 기본값). `_NUMERIC_RE` 패턴 중 하나가 포함되어야 한다:
   숫자(`\d`), `％`, `%`, `억`, `만원`, `천원`, `배`, `건`, `명`, `개사`, `개`, `회`, `점`, `위`, `차`.
   → "키워드 + 수치" 동반 시에만 강조해 **과잉 강조를 방지**한다.
5. 강조 누적 단락 수가 **`max_emphasis`(기본 60)** 미만일 것. 60개에 도달하면 즉시 중단.

## 수정 규칙

- 조건을 만족한 단락의 **텍스트가 있는 모든 런(run)** 에 Bold 를 적용한다.
  - 런의 `w:rPr` 가 없으면 새로 만들고, `w:b`(Bold) 요소가 없을 때만 추가한다(중복 적용 안 함).
  - `underline=True` 인 경우에만 `w:u`(`val="single"`) 밑줄을 추가한다(기본 off).
- 런 구조·텍스트 내용은 보존한다. **글자 자체를 바꾸지 않고 서식 속성만 추가**한다.
- 함수 반환값은 강조한 단락 수(int)이며, `QualityOpsReport.paragraphs_emphasized` 에 집계된다.
- 통합 실행 `run_all(doc, emphasize=True, underline=False)` 순서상 **마지막에 가까운 단계**에서 적용된다
  (안내삭제 → 글머리표공백 → 표공백 → 빈단락 → **강조** → 폰트).

## 예외 규칙

- **표 셀 내부 단락**은 강조하지 않는다(`_iter_body_paragraphs` 가 본문 직계만 반환).
- **4자 미만 단락**은 제외(제목·번호·기호만 있는 단락 보호).
- **키워드만 있고 수치가 없는 단락**은 제외(`require_numeric=True`). 예: "매출 증대를 목표로 한다"(숫자 없음) → 강조 안 함.
- **수치만 있고 키워드가 없는 단락**도 제외.
- 60개 초과 단락은 강조하지 않는다(`max_emphasis=60`) — 문서 전체가 굵어지는 과잉 강조 방지.
- 이미 Bold 가 적용된 런에는 다시 추가하지 않는다(`w:b` 존재 시 skip).
- 원본 DOCX 는 절대 덮어쓰지 않는다. 후처리는 백업 후 출력 경로에만 저장(출력=입력이면 ValueError).
- AI 키를 사용하지 않는다(완전 결정론적).

## 테스트 방법 (실제 PowerShell 명령)

```powershell
cd D:\auto_write\app

# 1) 강조 포함 전체 후처리 1회 (Bold만)
python document_quality_orchestrator.py "C:\경로\문서.docx" -o 결과.docx

# 2) 밑줄까지 강조
python document_quality_orchestrator.py "C:\경로\문서.docx" -o 결과_underline.docx --underline

# 3) 강조 결과 확인 (문단/표 덤프로 굵기·텍스트 확인)
python _build_chochang.py inspect "결과.docx"

# 4) 단위 테스트
python -m pytest tests/test_document_quality_harness.py -q

# 5) 강조 함수만 단독 검증 (강조된 단락 수 출력)
python -c "import sys; sys.path.insert(0, '.'); from docx import Document; from auto_write.services.doc_quality_ops import emphasize_key_sentences; d=Document(r'C:\경로\문서.docx'); print('emphasized:', emphasize_key_sentences(d))"
```

## 실패 시 롤백 기준

- 강조가 과도하거나(문단 다수가 의도와 다르게 굵어짐) 서식이 깨지면 백업본으로 복구한다.
- 복구 명령: `python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx`
- 백업 위치: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` (후처리 전 자동 백업).
- 강조만 끄고 재실행하려면 오케스트레이터에서 `--no-emphasis` 로 다시 돌린다.
- 원본이 손상된 정황이면 즉시 중단하고 백업본 무결성부터 확인한다(원본 절대 덮어쓰기 금지).

## 품질 점수 반영

- 영향 배점 항목: **주요문장 강조 (10점)** — `doc_quality_score.score_document` 의 강조 항목.
- 강조된 단락 수(`paragraphs_emphasized`)가 0이면 해당 항목 감점, 적정 강조 시 만점에 근접.
- 과잉 강조(60개 상한 도달 등)는 가독성 저해로 간주될 수 있으므로 무분별한 강조를 피한다.
- 게이트: 총점 90 우수 / 85 통과(passed=총점>=85) / 70 보완필요 / 70 미만 실패.

## 연결 코드·CLI (실제 함수/명령)

- 핵심 함수: `app/auto_write/services/doc_quality_ops.py`
  - `emphasize_key_sentences(doc, *, keywords=_EMPHASIS_KEYWORDS, underline=False, require_numeric=True, max_emphasis=60) -> int`
  - 통합 실행: `run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False) -> QualityOpsReport`
  - 재사용 헬퍼: `_iter_body_paragraphs`, `_paragraph_text`(docx_ops.py)
- 오케스트레이터: `app/auto_write/services/document_quality_orchestrator.py`
  - `DocumentQualityOrchestrator(results_root, openai_service=None).run(input_docx, output_docx=None, emphasize=True, underline=False, ...)`
- 진입점 CLI: `app/document_quality_orchestrator.py`
  - 관련 인자: `--underline`(밑줄 추가), `--no-emphasis`(강조 끔), `-o/--output`, `--rollback BACKUP_DIR TARGET`
- 래퍼: `scripts/run_document_quality_harness.py`
- 진단: `app/_build_chochang.py inspect <docx>`
