# /auto-write-selfdev — 실사용 기준 자가진단 → 자동개발 루프

사용자 요구사항(원장) 충족 여부를 자가진단하고, 미달성 항목 중 **임팩트 최대 1건만**
이번 루프에서 실제 코드로 개선한다. (한 루프 = 한 개선, service-dev-loop 규칙)

## 입력
- 진단 대상 DOCX 경로 (없으면 results/ 의 최신 제출본을 찾는다)
- 요구사항 원장: `workspace/requirements_ledger.json`

## 루프 절차 (매회 동일)

1. **자가진단 실행**
   ```powershell
   cd D:\auto_write\app
   python self_diagnose.py "<대상.docx>" --json ..\workspace\last_diagnosis.json
   ```
2. **격차 식별** — 진단 결과의 `ledger_gaps` (미달성/부분달성 요구) 확인.
   품질점수(85 게이트)는 통과인데 self_diagnose 가 FAIL 이면 그 check 가 최우선.
3. **이번 루프 개선 1건 선택** — 기준: 탈락(장애) 가능성 차단 > 서식 > 편의.
   선택 이유를 1줄로 보고하고 시작한다.
4. **최소 수정 구현** — 관련 서비스 모듈만 수정. 원본 DOCX 절대 미수정,
   날조 0, 기존 기능 삭제 금지. 새 검사가 필요하면 usage_acceptance.py 에 check 추가.
5. **검증** — 신규/기존 pytest 전체 + 대상 DOCX 재진단으로 before/after 비교:
   ```powershell
   py -3.11 -m pytest tests/ -q
   python self_diagnose.py "<대상.docx>"
   ```
6. **원장 갱신** — requirements_ledger.json 의 해당 요구 `상태`/`근거` 갱신,
   CLAUDE.md 변경이력 1줄 추가.
7. **보고 + 다음 루프 프롬프트 출력** — 남은 격차 중 차순위 1건을
   "다음 루프 프롬프트"로 제시하고 종료.

## 오답노트 규칙 (사람이 결함을 새로 발견했을 때)
- 발견 즉시 usage_acceptance.py 에 검출 check 추가 + tests/test_usage_acceptance.py 에
  재현 테스트 추가 + 원장에 요구 항목 등록.
- 같은 결함이 두 번 다시 게이트를 통과할 수 없게 만드는 것이 목적.

## 금지
- 한 루프에 2건 이상 대규모 개선 / 원본 덮어쓰기 / 테스트 없이 완료 보고
- 점수만 올리고 실결함을 남기는 수정 (self_diagnose FAIL=0 이 우선)
