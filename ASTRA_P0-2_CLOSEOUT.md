# Astra 인수 — Target Form Analyzer P0-2 종료

작성: 2026-09-27. 이 파일이 이번 구간의 정본이다.
이전 설계 메모 `ASTRA_TARGET_FORM_ANALYZER_HANDOFF.md`는 2026-09-26 기준이라 현재 판정 계약을 덮어쓰지 않는다.

## 지금 상태

P0-2 재감사 BLOCKER 2개는 코드에 반영됐고, 아래 회귀는 통과했다.

```
py -3.11 이 없는 이 PC에서는 Python 3.12로 실행했다.
C:\Users\ekth3\AppData\Local\Programs\Python\Python312\python.exe -m pytest ^
  app/tests/test_hwpx_protected_regions.py ^
  app/tests/test_hwpx_structure_types.py ^
  app/tests/test_hwpx_safety_golden10.py ^
  app/tests/test_hwpx_safety_runner.py ^
  app/tests/test_hwpx_t02_auto.py ^
  app/tests/test_hwpx_exact_write.py ^
  app/tests/test_hwpx_fill.py -q
```

결과: 109 passed.

| 항목 | 값 |
|---|---|
| CHOICE_STRUCTURE_PRECEDENCE_FIXED | YES |
| P0_2_AUTHORIZATION_GATE_FIXED | YES |
| P0_2_AUTO_WRITE_TRUE_COUNT | 0 |
| REGRESSION | 없음 |
| LEGACY_WRITER_REGRESSION | 없음 |
| AUTO_WRITE_ALLOWED | false |
| P0-3_READY | YES |
| P0-3 착수 | 하지 않음 |

`data/hwpx_safety/cursor/validation_summary.md`의 OVERALL PASS와 AUTO 집계는 **작성 허가를 닫기 전** 실행분이다. 그 파일을 현재 authorization 상태로 읽지 말 것. 현재 `assess_fields()`는 T02라도 `decision="REVIEW_REQUIRED"`, `auto_write_allowed=False`, `write_target=None`이다.

## 계약

판정과 작성은 분리돼 있다.

```
항목 발견 → 위치 검증 → 보호영역 검사 → (여기까지가 P0-2)
→ writer 수정범위 확인(P0-3, 아직 시작 안 함) → 작성 허가
```

P0-2에서 T02는 후보만 된다.

- `field_type="T02"`
- `eligible=True`
- `evidence`에 `T02_CANDIDATE`
- `review_reason=("AUTHORIZATION_PENDING",)`
- `decision="REVIEW_REQUIRED"`
- `auto_write_allowed=False`
- `write_target=None`

`assess_fields()` 끝에서 `decision=="AUTO"` 또는 `auto_write_allowed` 또는 `write_target`이 있으면 `RuntimeError`다.

`find_t02_auto_targets()`는 후보 좌표를 돌려준다. 그 반환은 작성 허가가 아니다.

`classify_protected_regions()`는 계속 `auto_write_allowed=False`만 만든다.

## BLOCKER 1 — 선택그룹이 제목 단어보다 먼저

같은 논리 행에 선택표시 대안이 2개 이상이면 `CHOICE_MARK`다. `전략`, `계획`, `현황`, `방안`이 있어도 HEADING으로 덮지 않는다. 판정은 `cellAddr`의 `rowAddr`/`colAddr`와 `rowSpan`/`colSpan`이다. XML `tc` 순서를 열로 쓰지 않는다.

확인된 반례:

- `수출 전략 보유 여부 | □ 전략 보유 | □ 전략 미보유` → CHOICE. 칸 순서를 뒤집어도 논리 좌표로 CHOICE.
- `향후 채용 계획 유무 | □ 계획 있음 | □ 계획 없음` → CHOICE
- `소유형태 | □ 자가소유 | □ 임차사용` → CHOICE
- 같은 행에 대안이 없는 `□ 기업개요 및 문제점`, `□ 성장전략` → HEADING

키워드 예외 목록은 넣지 않았다. 테스트: `app/tests/test_hwpx_protected_regions.py`의 `test_choice_group_precedes_heading_keywords`.

## BLOCKER 2 — P0-2가 작성 허가를 열지 않음

`assess_fields()`의 T02 레코드는 위 계약대로다. 기존 `fill_hwpx`, exact write, F01 경로는 끄지 않았다. `commit_t02_label_writes()` 함수는 남아 있고 테스트도 통과한다. P0-2 판정 결과가 그 함수를 호출하지는 않는다.

## 고친 파일

- `app/core/docx/services/hwpx_protected_regions.py`
- `app/core/docx/services/hwpx_safety_golden.py`
- `app/core/docx/services/hwpx_safety_report.py`
- `app/tests/test_hwpx_protected_regions.py`
- `app/tests/test_hwpx_structure_types.py`
- `app/tests/test_hwpx_safety_runner.py`

## Astra가 하지 말 것

- P0-2에서 `auto_write_allowed=True` 또는 `decision="AUTO"`를 다시 넣지 말 것
- 파일명·좌표 하드코딩으로 선택/제목을 가르지 말 것
- `fill_hwpx` / F01 / exact write를 이번 수정 때문에 전역으로 끄지 말 것
- 세로 배치 370건을 AUTO로 올리지 말 것
- Claude Holdout·Mimo Dry-run 원본(`data/holdout_validation_results.json`, `data/dry_run_367_summary.json`)을 덮어쓰지 말 것

## 다음 작업은 P0-3

작성 허가는 P0-3에서 writer 수정범위 검증이 끝난 뒤에만 연다. 그 전까지만 후보(`eligible=True`)다.
