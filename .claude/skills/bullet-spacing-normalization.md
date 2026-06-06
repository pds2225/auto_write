---
name: bullet-spacing-normalization
description: >-
  완성 DOCX(사업계획서·R&D계획서·정책자금/인증/수출/현장클리닉 보고서 등)에서
  글머리표(○ ㅇ · • - 등) 뒤 과다 공백과 단락 내부 다중 공백(2칸 이상)을 1칸으로
  정리한다. 다음 상황에서 적극적으로 이 스킬을 사용하라: (1) DOCX를 열어보니 글머리표
  기호 뒤에 공백이 2칸 이상 벌어져 있을 때, (2) 문장 중간에 공백이 여러 칸 들어가 줄
  간격/정렬이 들쭉날쭉할 때, (3) 품질 점수의 '글머리표 공백(10점)' 항목이 깎였을 때,
  (4) 후처리 후 공백이 여전히 남아 "다시/재실행/수정/보완" 요청이 들어올 때.
  normalize_bullet_spacing 함수를 호출해 결정론적으로 처리한다(AI 미사용, 서식 보존).
---

## 목적

완성된 DOCX 문서의 글머리표 뒤 과다 공백과 단락 내부 다중 공백을 1칸으로 정리한다.
쉽게 말하면, "○      항목" 처럼 글머리표 뒤가 너무 벌어졌거나 문장 중간에 공백이 여러
칸 들어간 것을 "○ 항목" 처럼 깔끔하게 1칸으로 맞춘다.

- 담당 함수: `auto_write.services.doc_quality_ops.normalize_bullet_spacing(doc) -> int`
- 반환값: 정리된 단락 수(정수). 오케스트레이터가 품질 리포트에 집계한다.
- AI 키 없이 동작하는 결정론적 규칙 기반 처리다.

## 적용 대상

- 본문(표 밖) 단락 전체.
- 표(`doc.tables`) 셀 안의 단락 전체.
  (함수는 `doc.paragraphs` 에 모든 표 셀의 `cell.paragraphs` 를 더해 함께 순회한다.)
- 대상 문서 유형: business_plan, rnd_plan, pitch_deck, consulting_report,
  policy_fund_report, certification_report, export_report, field_clinic_report,
  generic_submission (전 유형 공통 적용).

## 탐지 규칙

코드의 실제 정규식과 일치한다.

1. 글머리표 기호 집합(`_BULLET_SYMBOLS`):
   `○ ● ◦ ◌ ∙ · • ‣ ▪ ▫ ■ □ ◇ ◆ ▶ ▷ ► ▸ - – — * ㅇ ㅁ`
2. 접두 글머리표 공백(`_BULLET_PREFIX_RE`):
   줄 맨 앞 `(선행 공백*)(글머리표 기호 1개 이상)(공백 2칸 이상)` 패턴을 탐지한다.
   - 선행 공백·기호 뒤 공백은 일반 공백, 탭, 전각 공백(`　`)을 모두 인식한다.
   - 단락의 **첫 번째 비어있지 않은 텍스트 노드**에 대해서만, 그리고 **1회만** 탐지한다.
3. 내부 다중 공백(`_MULTI_SPACE_RE`):
   일반 공백·전각 공백(`　`)이 **2칸 이상** 연속된 구간을 탐지한다(줄바꿈·탭은 대상 아님).
   단락의 **모든** 텍스트 노드를 대상으로 한다.

## 수정 규칙

런(run)/단락 구조는 보존하고 텍스트 노드(`w:t`) 단위로만 수정한다(서식 유지).

1. 접두 글머리표 공백 → `(선행 공백)(기호) ` 형태로, 기호 뒤 공백을 **1칸**으로 축소.
2. 내부 다중 공백 2칸 이상 → **1칸**으로 축소.
3. 한 단락에서 위 (1)·(2) 중 하나라도 실제로 바뀌면 정리 카운트를 1 증가시킨다.
4. 표 안/밖 단락 모두 동일하게 적용한다.

## 예외 규칙

- 텍스트 노드가 전혀 없는 단락은 건너뛴다.
- 텍스트가 비어 있거나 `None` 인 노드는 건너뛴다.
- 줄바꿈·탭은 다중 공백 축소 대상이 아니다(일반/전각 공백만 1칸으로 줄임).
- 접두 패턴은 첫 텍스트 노드에서 1회만 적용한다(같은 줄의 다른 위치는 내부 다중 공백
  규칙으로 처리됨).
- 셀 경계 trim(앞뒤 공백 제거)이나 빈 단락 삭제는 이 함수의 책임이 아니다
  (각각 `cleanup_table_whitespace`, `remove_empty_paragraphs` 담당).

## 테스트 방법 (실제 PowerShell 명령)

전체 파이프라인으로 실행(권장):

```
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx" --output 결과.docx
```

정리 전후 단락/공백 상태 확인:

```
cd D:\auto_write\app
python _build_chochang.py inspect "결과.docx"
```

자동화 테스트:

```
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q
```

함수 단독 확인(파이썬 인터프리터):

```
cd D:\auto_write\app
python -c "from docx import Document; from auto_write.services.doc_quality_ops import normalize_bullet_spacing; d=Document(r'결과.docx'); print('fixed=', normalize_bullet_spacing(d))"
```

## 실패 시 롤백 기준

- 오케스트레이터는 후처리 전 항상 원본을 백업한다:
  `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\`
- 결과가 의도와 다르거나 서식이 깨지면 백업으로 복원한다:

```
cd D:\auto_write\app
python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx
```

- 복원 함수: `DocumentQualityOrchestrator.rollback(backup_dir, target) -> bool`
- 원본 DOCX는 절대 덮어쓰지 않는다(출력=입력 경로면 ValueError). 백업 없이 원본 수정 금지.

## 품질 점수 반영

- 영향 배점: **글머리표 공백(10점)** (`doc_quality_score.score_document` 9항목 중 1개).
- 글머리표 뒤 과다 공백·내부 다중 공백이 남아 있으면 이 항목 점수가 깎인다.
- 게이트: 총점 85점 이상이면 통과(`passed`). 미달 시 오케스트레이터가 최대 10회 보완
  루프를 돌며 이 항목을 포함해 재정리한다.

## 연결 코드·CLI (실제 함수/명령)

- 핵심 함수: `auto_write.services.doc_quality_ops.normalize_bullet_spacing(doc) -> int`
- 통합 실행기: `doc_quality_ops.run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False) -> QualityOpsReport`
  (실행 순서: 안내삭제 → **글머리표공백** → 표공백 → 빈단락 → 강조 → 폰트)
- 재사용 헬퍼(`docx_ops.py`): `_iter_body_paragraphs`, `_paragraph_text`, `GUIDE_MARKER_RE`
- 점수 계산: `auto_write.services.doc_quality_score.score_document(...)`
- 오케스트레이터: `auto_write.services.document_quality_orchestrator.DocumentQualityOrchestrator.run(...)`
- 진입점 CLI: `app/document_quality_orchestrator.py`,
  래퍼: `scripts/run_document_quality_harness.py`
