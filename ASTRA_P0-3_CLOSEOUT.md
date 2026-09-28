# Astra 인수 — Target Form Analyzer P0-3 종료

작성: 2026-09-27. 이 파일이 이번 구간의 정본이다.
P0-2 정본은 `ASTRA_P0-2_CLOSEOUT.md`다. 그 계약은 유지한다.

## 결과

```
P0-3_RESULT = PASS
EXACT_TARGET_ONLY = YES
PRECONDITION_GUARD = PASS
PARTIAL_WRITE_BLOCKED = YES
OUT_OF_SCOPE_XML_CHANGES = 0
SOURCE_SHA_GUARD = PASS
EXPECTED_TEXT_GUARD = PASS
LEGACY_WRITER_REGRESSION = 없음
AUTO_WRITE_ALLOWED = false
REMAINING_BLOCKERS = 없음
P1_T02_READY = YES
```

P0-3는 필드를 고르지 않았다. 좌표를 직접 지정한 fixture로, 기존 `commit_exact_text_writes()`가 그 hp:t만 바꾸는지 증명했다. Target Form Analyzer를 writer에 연결하지 않았다. T02 자동작성도 시작하지 않았다.

## 검증

이 PC에는 Python 3.11이 없다. Python 3.12로 실행했다.

```
C:\Users\ekth3\AppData\Local\Programs\Python\Python312\python.exe -m pytest ^
  app/tests/test_hwpx_p03_exact_scope.py ^
  app/tests/test_hwpx_exact_write.py ^
  app/tests/test_hwpx_fill.py ^
  app/tests/test_hwpx_t02_auto.py ^
  app/core/docx/tests/test_f01_write_map.py -q
```

결과: 103 passed.

| 테스트 | 내용 |
|---|---|
| A, B, C, D, J | 지정 hp:t만 변경. 같은 칸의 안내문, 같은 문단의 라벨, 중첩표, header, 다른 section, 바닥글 유지 |
| H | `중복문구`가 두 곳이어도 지정 좌표만 변경 |
| E | SHA 불일치 → 출력 파일 없음 |
| F | expected raw text 불일치 → 출력 파일 없음 |
| G | 잘못된 table/cell 좌표 → `COORDINATE_MISMATCH`, 출력 파일 없음 |
| I | target 여러 개 중 하나 precondition 실패 → 전체 mutation 0 |
| K | F01 `apply_f01_field_writes` / `submit_hwpx` 기존 테스트 통과 |
| L | `fill_hwpx`, exact write, `commit_t02_label_writes` 기존 테스트 통과 |

증명 테스트: `app/tests/test_hwpx_p03_exact_scope.py`.

## exact 명령의 안전장치

함수: `app/core/docx/services/hwpx_fill.py` `commit_exact_text_writes`.

mutation 전에 전부 검사한다. 하나라도 실패하면 파일을 쓰지 않는다.

- source SHA-256
- section / paragraph / run / hp:t 존재
- expected raw text. 비어 있지 않은 글자는 `EXISTING_VALUE`로 거부
- 안내문, 서명, 날짜 scaffold, 선택기호가 들어 있는 글자 거부
- `table_index`/`row`/`col`이 오면 P0-1 인덱스의 cellAddr 소유와 대조
- 같은 좌표 중복 거부

검사 통과 후에만 그 hp:t의 텍스트만 바꾼다. 셀, 문단, run 전체를 갈아끼우지 않는다. charPrIDRef, paraPrIDRef, 중첩표, header, 다른 section은 그대로다.

저장 후 `compare_hwpx_xml_scope()`로 승인 노드 밖 XML 변경이 있으면 출력 파일을 삭제하고 `OUT_OF_SCOPE_XML_CHANGE`로 실패한다. ZIP 안에서 바이트가 같은 멤버는 변경으로 세지 않는다.

## 기존에 더 넓게 고치는 경로

이건 exact 명령이 아니다. P0-3에서 끄지 않았다. F01과 `fill_hwpx` 회귀를 지키기 위해서다.

| 함수 | 파일 | 위험 | 조치 |
|---|---|---|---|
| `_set_cell_text` | `hwpx_fill.py` | 칸의 첫 hp:t에 쓰고 나머지 hp:t를 비운다. charPr를 바꿀 수 있고 그 칸의 linesegarray를 지운다 | `fill_hwpx` 라벨 채움 전용. exact 명령은 호출하지 않음 |
| `_apply_line_edits` | `hwpx_fill.py` | `set`은 문단 텍스트를 통째로 교체. `nth`/`all`은 부분문자열로 문단을 고른다 | 사람이 앵커를 명시한 legacy 편집. exact 명령과 분리 |
| `_fill_inline_fields_in_p` | `hwpx_fill.py` | 한 문단 안에서 라벨을 찾아 빈칸만 교체. 두 hp:t에 걸치면 False | legacy fill 전용 |
| `fill_hwpx` | `hwpx_fill.py` | 맞은 항목만 저장할 수 있다 | exact 계획의 부분성공 차단과 별도 경로 |

## 유지되는 P0-2 계약

`assess_fields()`의 T02는 후보다.

- `eligible=True`
- `decision="REVIEW_REQUIRED"`
- `review_reason=("AUTHORIZATION_PENDING",)`
- `auto_write_allowed=False`
- `write_target=None`

`find_t02_auto_targets()`의 반환은 작성 허가가 아니다.

## Astra가 하지 말 것

- P0-2 판정에서 `auto_write_allowed=True` 또는 `decision="AUTO"`를 다시 넣지 말 것
- 이번 단계에서 analyzer가 `commit_exact_text_writes`를 호출하게 잇지 말 것
- `_set_cell_text` / `line_edits` / `fill_hwpx`를 exact 명령의 안전 경로로 쓰지 말 것
- F01과 `fill_hwpx`를 전역으로 끄지 말 것
- `data/holdout_validation_results.json`, `data/dry_run_367_summary.json`을 덮어쓰지 말 것

## 다음

P1에서 T02 후보를 이 exact 명령에 연결할 수 있다. 연결 시 허가는 `commit_exact_text_writes`의 precondition과 작성 후 XML diff를 통과한 뒤에만 연다. `_set_cell_text`와 `line_edits`로는 연결하지 않는다.
