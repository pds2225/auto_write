---
name: docx-template-cleanup
description: >-
  DOCX 양식 안내문구·작성요령·예시·플레이스홀더 단락과 노란/주황 음영 placeholder,
  안내용 글자색을 삭제·정규화한다. 다음 요청 시 적극적으로 사용하라 —
  "양식 안내문구 삭제", "작성요령 지워줘", "예시 문구 제거", "노란 음영 placeholder 정리",
  "회색/노란 칸 색 빼줘", "<...> 괄호 안내 지워줘", "OOO·○○○ 플레이스홀더 정리",
  "제출 전 양식 흔적 제거", "템플릿 안내 단락 청소".
  후속작업 키워드도 이 스킬로 처리: "다시 정리해줘", "재실행", "안내문구만 다시 수정",
  "음영 보완", "남은 안내문구 더 지워줘", "부분 재실행(안내문구 단계만)".
  품질점수 '안내문구 제거(15점)' 항목을 직접 끌어올린다.
---

# docx-template-cleanup

## 목적

완성된 정부지원사업 DOCX에 남아 있는 **양식 자체의 흔적**을 제거해 제출용 본문만 남긴다.
대상은 두 가지다.

1. **양식 안내 단락** — "작성요령/작성방법/예시/유의사항/기재" 같은 안내 문구로만 이뤄진 단락.
2. **placeholder 음영·안내 글자색** — 노란/주황 계열 강조 음영, 형광펜(highlight),
   안내용 글자색으로 칠해진 빈칸·예시 텍스트.

쉽게 말하면, "여기에 ○○○를 적으세요" 같은 양식 안내와 노란 칠을 지워 깔끔한 제출본을 만드는 단계다.
AI를 쓰지 않고 규칙 기반으로만 동작하며, 오삭제를 막기 위해 매우 보수적으로 판단한다.

## 적용 대상

- 입력: 완성 DOCX 1개(사업계획서·R&D계획서·발표평가·컨설팅·정책자금·인증·수출·현장클리닉 보고서 등 전 유형).
- 처리 코드:
  - `auto_write/services/doc_quality_ops.py` 의 `remove_guide_paragraphs(doc, *, max_len=120) -> int`
    (반환값 = 삭제된 안내 단락 수).
  - `auto_write/services/docx_ops.py` 의 음영·색상 정규화 헬퍼
    (`GUIDE_MARKER_RE`, placeholder 음영 fill 제거, highlight 제거, 안내 글자색 → 검정 정규화).
- 호출 경로: 오케스트레이터 `document_quality_orchestrator.DocumentQualityOrchestrator.run()` 의
  `run_all(doc, remove_guides=True, ...)` 1단계에서 `remove_guide_paragraphs` 가 실행된다.

## 탐지 규칙

`remove_guide_paragraphs` 의 실제 동작과 정확히 일치시킨다.

- **body 직계 단락만** 대상. 표(table) 셀 안의 단락은 삭제 대상이 아니다(표는 음영 정규화로 처리).
- 단락 텍스트가 `_PURE_GUIDE_RE` 패턴으로 **시작**하는 경우에만 안내 단락으로 본다
  (부분 포함은 제외 — 본문 중간에 안내성 단어가 섞인 것은 건드리지 않는다).
- 안내 키워드 계열: "작성요령", "작성방법", "예시", "유의사항", "기재", `※`, `<...>` 꺾쇠 안내,
  `OOO`, `○○○` 등(코드의 `GUIDE_MARKER_RE = re.compile(r"(※|<[^>]+>|기재|작성요령|작성방법|예시|OOO|○○○)")` 와 동일 계열).
- 음영·색상 탐지(`docx_ops.py`):
  - placeholder 음영 fill 집합 `_PLACEHOLDER_SHADE_FILLS = {"ffff00","fff2cc","ffeb9c","ffe699","ffd966"}`
    (노란·연노랑·주황 계열)에 해당하는 `w:shd` 음영을 placeholder로 본다.
  - run 의 `w:highlight`(형광펜)는 안내 강조로 본다.
  - 보존 색 `_PRESERVE_COLORS = {"ffffff","fffffe","f2f2f2"}`(흰색·거의 흰색·옅은 회색)는 정상 서식으로 보고 건드리지 않는다.

## 수정 규칙

- 안내 단락: 탐지된 단락을 body에서 **제거**한다(`body.remove(para)`). 삭제 수를 정수로 반환.
- placeholder 음영: `_PLACEHOLDER_SHADE_FILLS` 에 속하는 `w:shd` 를 제거한다.
  표 셀(`w:tcPr` 하위 `w:shd`)의 placeholder fill도 동일하게 제거한다.
- 형광펜: run 의 `w:highlight` 요소를 제거한다.
- 안내 글자색: `_PRESERVE_COLORS` 에 속하지 않는 안내 글자색은 검정(`000000`)으로 정규화한다.
  (`w:color` 가 없으면 검정 color 요소를 추가, 있으면 보존색이 아닐 때만 검정으로 교체.)
- 처리 순서는 오케스트레이터의 `run_all` 순서를 따른다: **안내삭제 → 글머리표공백 → 표공백 → 빈단락 → 강조 → (옵션)폰트.**
  안내 삭제는 가장 먼저 수행한다.

## 예외 규칙 (오삭제 방지)

- **표 셀 단락은 절대 삭제하지 않는다.** 표 내용은 본문 데이터이므로 음영 정규화만 적용한다.
- 텍스트 길이가 `max_len`(기본 120자) 를 **초과**하면 실제 작성 내용일 수 있어 삭제하지 않는다.
- 이미지/도형(drawing)을 포함한 단락은 삭제하지 않는다.
- 문서의 **맨 끝 단락**(`body[-1]`)은 구조 안정성을 위해 보존한다.
- 패턴이 단락 중간에만 등장하면(시작이 아니면) 삭제하지 않는다.
- 보존색(`ffffff`·`fffffe`·`f2f2f2`)과 placeholder 집합 밖의 음영/색상은 임의로 바꾸지 않는다.
- 표/이미지 등 원본 데이터는 보존한다. 원본 DOCX는 절대 덮어쓰지 않고, 후처리 전 반드시 백업한다.

## 테스트 방법 (실제 PowerShell 명령)

```powershell
# 1) 전체 파이프라인 실행(안내삭제 포함) — 결과 DOCX + 리포트 생성
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx" --output "결과.docx"

# 2) 안내문구/음영이 실제로 빠졌는지 본문 덤프로 확인
python _build_chochang.py inspect "결과.docx"

# 3) 단위 테스트(하네스 회귀 검증)
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q

# 4) 안내삭제 단계만 빠르게 확인(파이썬 인라인) — 삭제된 단락 수 출력
cd D:\auto_write\app
python -c "from docx import Document; from auto_write.services.doc_quality_ops import remove_guide_paragraphs; d=Document(r'C:\경로\문서.docx'); print('removed=', remove_guide_paragraphs(d))"
```

## 실패 시 롤백 기준

- 본문이 과하게 삭제된 경우(예: 정상 문장이 사라짐), 백업본으로 즉시 복구한다.
- 백업 위치: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\`.
- 복구 명령:

```powershell
cd D:\auto_write\app
python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" "결과.docx"
```

- 코드 경로: `DocumentQualityOrchestrator.backup_original(path)` 로 백업,
  `DocumentQualityOrchestrator.rollback(backup_dir, target)`(staticmethod)로 복구.
- 롤백 후에는 `max_len` 축소나 표 셀 보존 조건을 재확인하고, 안내삭제를 보수적으로 재시도한다.

## 품질 점수 반영

- 직접 영향 항목: **안내문구 제거(15점)**.
  `doc_quality_score.score_document(...)` 의 안내문구 배점이 이 단계 결과로 채워진다.
- 안내 단락·placeholder 음영이 남아 있으면 해당 15점에서 감점되어 게이트(85점 통과)에 미달할 수 있다.
- 미달 시 오케스트레이터 보완 루프(최대 10회, 수렴 시 조기종료)에서 안내삭제를 재적용한다.

## 연결 코드·CLI (실제 함수/명령)

- 핵심 함수:
  - `auto_write/services/doc_quality_ops.py` : `remove_guide_paragraphs(doc, *, max_len=120) -> int`,
    `run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False) -> QualityOpsReport`.
  - `auto_write/services/docx_ops.py` : `GUIDE_MARKER_RE`, `_PLACEHOLDER_SHADE_FILLS`, `_PRESERVE_COLORS`,
    `_iter_body_paragraphs`, `_paragraph_text` (음영·highlight·글자색 정규화 헬퍼 재사용).
- 오케스트레이터: `auto_write/services/document_quality_orchestrator.py` →
  `DocumentQualityOrchestrator(results_root, openai_service=None).run(input_docx, output_docx=None, ..., remove_guides=True)`.
- 진입점 CLI:
  - `app/document_quality_orchestrator.py` (main) — `python document_quality_orchestrator.py <input> [--keep-guides] [--rollback BACKUP_DIR TARGET]`
    (`--keep-guides` 지정 시 안내삭제를 끈다 = `remove_guides=False`).
  - `scripts/run_document_quality_harness.py` (app sys.path 추가 래퍼).
  - 진단: `app/_build_chochang.py inspect <docx>`.
