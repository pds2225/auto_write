# Round-5 값 채움 수정·PDF 재현 결과

- 기준 main: 12b5095f9fbeacb02257b3f169d5924f7fc947a2 (문서 PR #215 병합).
- 작업 브랜치: codex/round5-fill-fixes. [Draft PR #216](https://github.com/pds2225/auto_write/pull/216), main 미병합.
- 검증한 제품 코드 SHA: 2cb684e8d3310411019656f015b3054451990a9f.

| 항목 | 결과 | 근거와 제한 |
|---|---|---|
| 종업원수 현재 기간 | 수정·영향 검증 통과 | 라벨 앞 모든 행을 탐색하고 올해(예상)·현재 표현·실제 올해 숫자 연도를 병합 열 범위와 연결. 과거만 있거나 모호하면 사유 기록 후 인라인 동의어 경로도 보류. 양옆 다른 라벨 영역을 넘지 않음. |
| 창업아이템 개요 | 수정·영향 검증 통과 | 목적격·간략히 등 구체적인 괄호 안내 구문만 user_brief로 채움. 서술형 실제 개요는 EXISTING_VALUE로 보존. |
| IP디딤돌 PDF 120초 타임아웃 | 미재현·미해결 | 아래 접근 가능한 원본 및 변경 추적 사본은 기존 SaveAs[PDF]로 모두 저장 성공. 정확한 실패 입력은 확인되지 않음. PDF 코어와 120초 제한을 근거 없이 변경하지 않음. |

## 검증

영향 회귀: 89 passed / 0 failed.

```powershell
Set-Location -LiteralPath 'D:\auto_write'
$env:PYTHONUTF8='1'
py -3.11 -m pytest app/tests/test_hwpx_round5_fill.py app/tests/test_hwpx_round4_fill.py app/tests/test_hwp_round5_pdf.py app/tests/test_hwp_round4_ownership.py -q --tb=short
```

전체 Windows pytest **1회**: **2275 passed / 0 failed / 5 기존 skipped / 23 subtests passed**, exit 0, 943.29초. 실행 명령: `py -3.11 -m pytest -q --tb=short --junitxml=_preflight_evidence/round5-20261006/full-pytest.xml`. 로그·JUnit 대조 완료. 위 제품 코드 SHA에서 실행했으며 이후 변경은 검증 문서뿐이다.

합성 HWPX ZIP 회귀는 네 번째 행·병합 헤더, 현재 열이 중간/왼쪽인 경우, 과거만 있는 경우, 모호한 병합, 단위 헤더, 비헤더 연도, 다른 라벨 경계, 인라인 동의어 보류, 실제 괄호 개요를 검증한다. 원본 bytes·표 구조·열주소·변경 대상 외 ZIP member를 보존한다.

기존 Round4 과거 2사례는 삭제하지 않고 오기입 기대를 원본 모든 값 칸 보존·filled={}·PAST_PERIOD_ONLY 사유 검사로 강화했다. 신규 skip/xfail은 없다.

## 실제 한글 2022 PDF 저장

한글 버전: 12.0.0.893 (Office 2022). 원본은 읽기 전용으로 두고 별도 사본에서 검증했다.

| 입력 조건 | 기존 SaveAs[PDF] | PDF 확인 |
|---|---:|---|
| 2026년 IP디딤돌 HWP 원본 사본 | 65.609초, True | 2페이지·156406bytes·아이디어 텍스트 확인 |
| 2025년 IP디딤돌 HWPX 원본 사본 | 1.578초, True | 2페이지·72620bytes·아이디어 텍스트 확인 |
| 2025년 사본에서 변경 추적 설정+문구 삽입 | 3.953초, True | 3페이지·74786bytes·아이디어 및 추가 검증 문구 확인 |

변경 추적 사본의 대안 FileSaveAsPdf도 13.375초에 True를 반환했으나 기존 호출보다 빨라지지 않았으므로 저장 방식을 대체하지 않았다. 120초 타임아웃이나 저장 경고 대기를 재현하지 못했으므로 위 성공을 타임아웃 수정 성공으로 해석하지 않는다. 사용자는 정확한 실패 파일 경로를 모른다고 답했다.

PDF mock 3사례는 저장 성공·거부·타임아웃을 검사한다. 기존 자동확인 모드가 저장 전에 설정되고 120초 제한이 유지되며, 소유 PID만 정리하고 기존 및 동시에 열린 다른 사용자 프로세스와 원본을 보존한다. Mock 통과는 실제 PDF 변환 완료의 증거를 대체하지 않는다.

실제 COM 검증에서 모든 원본·사본 해시 보존, 기존 사용자 한글 생존, 종료 후 소유 PID 잔존 없음이 확인됐다. 원본·data·검증 로그·백업·개인 기록은 커밋하지 않는다.

## 남은 일

정확한 타임아웃 입력을 확보해 같은 한글 2022에서 실패를 재현한 뒤 원인을 수정한다. Round-5 전체 요청 상태는 PARTIAL이며 REQUEST_SOLVED=NO다. 기존 DOCX Open 실패·소유 PID 미확인 hard timeout 한계와 L050 gap은 별도로 유지한다.

공유 재개 기록: [RESUME.md](../RESUME.md), 작업 상태: [TASK.md](../TASK.md). GitHub main의 시작 규칙은 문서 PR #215에서 이미 병합했고, Round-5 최신 상태는 이 draft 브랜치에서 읽는다.
