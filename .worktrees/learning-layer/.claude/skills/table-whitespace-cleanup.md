---
name: table-whitespace-cleanup
description: >-
  DOCX 표(table) 셀 내부의 앞뒤 공백과 다중 공백을 정리하는 스킬. 표 셀에
  "○○○   ☐☐☐ " 처럼 여러 칸 공백·셀 경계 공백이 남아 너저분할 때 사용한다.
  다음 요청 시 적극적으로 발동하라 — "표 공백 정리", "표 셀 정리", "표 내부 정리",
  "표 정렬 깨짐", "셀 공백 제거", "표가 지저분해", "표 서식 다듬어줘",
  "표 내부 품질 점수 올려줘". 재실행·다시 정리·수정·보완·부분 재실행(표만)·
  회귀 검수 요청도 동일하게 이 스킬로 처리한다. 런(run) 구조와 이미지 셀은
  보존하므로 안전하다.
---

## 목적

완성된 정부지원사업 문서(사업계획서·R&D계획서·컨설팅/정책자금/인증/수출/현장클리닉 보고서)의
**표 셀 내부 공백**을 결정론적으로 정리한다. 표 셀에 남은 셀 경계 공백(앞뒤)과 내부 다중 공백을
1칸으로 줄여, 표가 깔끔하게 보이도록 한다.

- AI를 쓰지 않는다. 규칙 기반으로만 동작한다.
- 런(run, `w:t` 노드) 구조와 셀 내 서식을 보존한다. 텍스트를 합치거나 재배치하지 않는다.
- 이미지/도형이 든 셀은 절대 건드리지 않는다.

연결 함수: `cleanup_table_whitespace(doc) -> int` (정리된 셀 수 반환).
영향 점수 항목: **표 내부 품질(10점)**.

## 적용 대상

- 표(table)가 1개 이상 포함된 `.docx` 문서.
- 셀 텍스트에 다음이 있는 경우가 핵심 대상:
  - 셀 첫 글자 앞 공백(왼쪽 여백), 셀 마지막 글자 뒤 공백(오른쪽 여백)
  - 셀 텍스트 내부의 2칸 이상 연속 공백(반각 ` `, 전각 `　`)

처리 단위는 **셀**이며, 표 안의 모든 행·모든 셀을 순회한다.

## 탐지 규칙

`cleanup_table_whitespace`는 `doc.tables` → `table.rows` → `row.cells` 순으로 모든 셀을 돈다.
각 셀(`cell._tc`)에서:

1. **이미지 셀 제외** — `_element_has_drawing(tc)` 가 참(셀 안에 `w:drawing` 또는 `w:pict` 존재)이면
   해당 셀은 건너뛴다(이미지/도형 보존).
2. **텍스트 노드 수집** — `_text_nodes(tc)` 로 셀 내부 모든 `w:t` 노드를 모은 뒤,
   빈 노드(`n.text` 가 비어있는 것)는 제외한다. 남은 노드가 없으면 그 셀은 건너뛴다.
3. **결함 판정 기준**(어느 하나라도 해당하면 정리 대상):
   - 노드 텍스트 내부에 2칸 이상 연속 공백이 있다(`_MULTI_SPACE_RE = r"[  　]{2,}"`, 반각/전각 모두).
   - 셀의 첫 노드 왼쪽 또는 마지막 노드 오른쪽에 공백(반각 ` `, 전각 `　`, 탭 `\t`)이 있다.

품질 점수 산정의 결함 카운트(`_scan_table_ws`)는 별도로, 각 셀 텍스트 `t` 에 대해
`t != t.strip()` 이거나 `_MULTI_SPACE_RE.search(t)` 가 걸리면 결함 1로 집계한다.

## 수정 규칙

정리 대상 셀에 대해 다음을 **순서대로** 적용한다(런 구조 보존):

1. **내부 다중 공백 축소** — 셀의 모든 텍스트 노드에 대해
   `n.text = _MULTI_SPACE_RE.sub(" ", n.text)` (2칸 이상 → 1칸).
2. **셀 경계 trim** —
   - 첫 노드: `nodes[0].text = nodes[0].text.lstrip("  　\t")` (왼쪽 공백 제거)
   - 마지막 노드: `nodes[-1].text = nodes[-1].text.rstrip("  　\t")` (오른쪽 공백 제거)
3. **변경 집계** — 정리 전후 노드 텍스트 목록이 달라진 셀만 반환값(`cleaned`)에 +1.

핵심: 텍스트 노드를 **그 자리에서 in-place 수정**할 뿐, 노드를 삭제·병합·생성하지 않는다.
따라서 굵게/색상 등 런 단위 서식이 그대로 유지된다.

## 예외 규칙

- **이미지/도형 셀 제외** — `w:drawing`/`w:pict` 포함 셀은 정리하지 않는다(시각 자료 보존).
- **빈 노드 무시** — 텍스트 없는 `w:t` 노드는 경계 trim/축소 대상에서 빠진다.
- **셀 사이 단어 공백(1칸)** 은 보존한다. 1칸 공백은 다중 공백이 아니므로 손대지 않는다.
- **표 밖 본문 공백**은 이 스킬 대상이 아니다(글머리표/문단 공백은 별도 스킬).
- 셀 한가운데(첫·마지막 노드가 아닌) 노드의 양끝 공백은 trim하지 않는다. 경계 trim은
  셀의 맨 앞·맨 뒤 노드에만 적용된다(중간 단어 사이 의도된 공백 보호).

## 테스트 방법 (실제 PowerShell 명령)

```powershell
# 1) 전체 하네스 1회 실행(백업→후처리→점수). 표 공백 정리는 run_all 안에 포함됨
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx"

# 2) 표 공백만 단독 검증(파이썬 인라인)
cd D:\auto_write\app
python -c "from docx import Document; from auto_write.services.doc_quality_ops import cleanup_table_whitespace; d=Document(r'C:\경로\문서.docx'); print('정리된 셀 수:', cleanup_table_whitespace(d)); d.save(r'C:\경로\문서_표정리.docx')"

# 3) 정리 결과 표 내용 눈으로 확인(진단 CLI)
cd D:\auto_write\app
python _build_chochang.py inspect "C:\경로\문서_표정리.docx"

# 4) 회귀 테스트(전체 하네스 단위테스트)
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q
```

검증 포인트: 반환값(정리된 셀 수)이 0보다 크면 정리가 일어난 것이며, 재실행 시 0이 나오면
더 정리할 공백이 없는 수렴 상태다(멱등성 확인).

## 실패 시 롤백 기준

- 후처리는 항상 백업 후 진행된다. 원본은 `results\backup\<YYYYMMDD_HHMMSS>\` 에 보관된다.
- 표 정렬·서식이 의도와 다르게 보이면 즉시 롤백한다.

```powershell
cd D:\auto_write\app
python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" "결과.docx"
```

- 롤백 트리거: 셀 내용이 깨졌다 / 의도한 다중 공백(정렬용 들여쓰기)이 사라졌다 /
  이미지 셀이 변형됐다(정상이라면 발생하지 않음). 원본 덮어쓰기는 절대 금지(출력=입력 경로면 ValueError).

## 품질 점수 반영

- 영향 항목: **표 내부 품질 (10점)** — `doc_quality_score.py`의 `table_quality` 항목.
- 산식: 결함 셀 수 `tw = _scan_table_ws(doc)` 에 대해 `s5 = max(0.0, 10.0 - tw * 1.0)`.
  즉 결함 셀 1개당 1점 감점, 결함 0이면 만점 10점.
- 이 스킬로 표 공백을 정리하면 `_scan_table_ws` 결함 카운트가 줄어 `table_quality` 점수가 오른다.
- 게이트(총점 기준): 90↑ 우수 / 85↑ 통과 / 70↑ 보완필요 / 70 미만 실패.

## 연결 코드·CLI (실제 함수/명령)

- 핵심 함수: `app/auto_write/services/doc_quality_ops.py`
  - `cleanup_table_whitespace(doc) -> int`
  - 재사용 헬퍼: `_text_nodes(element)`, `_element_has_drawing(element)`, 상수 `_MULTI_SPACE_RE`
  - 통합 실행: `run_all(doc, remove_guides=True, emphasize=True, underline=False, normalize_fonts=False) -> QualityOpsReport`
    (내부에서 `cleanup_table_whitespace` 호출)
- 점수 산정: `app/auto_write/services/doc_quality_score.py`
  - `_scan_table_ws(doc) -> int`, `score_document(...) -> QualityScore`의 `table_quality` 항목
- 오케스트레이터: `app/auto_write/services/document_quality_orchestrator.py`
  - `DocumentQualityOrchestrator(results_root, openai_service=None).run(input_docx, output_docx=None, ...) -> HarnessResult`
- 진입 CLI: `app/document_quality_orchestrator.py`,
  래퍼 `scripts/run_document_quality_harness.py`, 진단 `app/_build_chochang.py inspect <docx>`
