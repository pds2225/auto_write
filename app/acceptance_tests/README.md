# AutoWrite Acceptance AUTO suite

07_ACCEPTANCE의 AUTO 우선 항목 AT-002, AT-003, AT-005, AT-007, AT-010을
실제 제품 모듈에 연결해 검증하는 test-first suite다.

## 원칙

- 기본 회귀 `pytest.ini -> app/tests`와 분리한다.
- 이 디렉터리는 명시적으로 실행할 때만 수집한다.
- 현재 제품에 없는 Acceptance 계약은 skip/가짜 PASS로 숨기지 않고 FAIL로 드러낸다.
- 07_ACCEPTANCE H열을 `통과`로 바꾸려면 이 suite의 해당 AT가 전부 PASS하고,
  시트 G~K의 증거·실제결과·기준 SHA·실행일시를 별도로 남겨야 한다.
- 실제 HWP/한글 COM 및 HYBRID 항목은 이 suite의 범위가 아니다.

## 실행

Windows:

```powershell
cd app
py -3.11 -m pytest acceptance_tests/test_auto_at_002_003_005_007_010.py -q
```

repo root:

```powershell
py -3.11 -m pytest app/acceptance_tests/test_auto_at_002_003_005_007_010.py -q
```

## Test Pack 매핑

| AT | Test Pack | 실제 호출 모듈 | 핵심 자동 판정 |
|---|---|---|---|
| AT-002 | TP-02 LONG-NOTICE | announcement_analyzer | 후반부 조건, 문서내 명령 무시, 근거 위치 계약 |
| AT-003 | TP-03 COMPLEX-FORM | form_analyzer/document_ingest | HWPX 분석, 원본 hash 불변, 재현성, anchor/baseline 계약 |
| AT-005 | TP-04 FACT-CONFLICT | company_extract | 날조0, conflict 미해소, provenance, FactState 계약 |
| AT-007 | TP-03/05 구조 fixture | hwpx_submit | 원본 불변, 보호 구조/표 geometry 보존 |
| AT-010 | TP-06 UNREPAIRABLE | hwpx_submit/integrity gate | FINAL 차단, DRAFT 보존, repair attempt 상한 계약 |

## 현재 예상 GAP

이 파일을 추가하는 시점의 main(f63eb71b457c34c9f4fa9f6d928803043beb9592) 기준으로
다음 계약은 코드에 완전히 존재하지 않을 수 있다.

- AT-002: 추출 조건별 파일/페이지(또는 문단) provenance
- AT-003: 작성영역/보호영역 anchor map + baseline 계약
- AT-005: ACTUAL/IN_PROGRESS/TARGET/ASSUMPTION/VERIFY/DEPRECATED FactState
- AT-010: 최대 3회 bounded repair의 attempt/evidence 계약

따라서 위 GAP가 구현되기 전에는 Acceptance suite가 FAIL하는 것이 정상이며,
그 실패를 제품 PASS로 바꾸면 안 된다.
