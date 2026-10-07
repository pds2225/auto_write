## 요약

종업원수가 과거 칸에 들어가는 문제와 괄호 안내문 때문에 창업아이템 개요를 건너뛰는 문제를 수정했습니다. IP디딤돌 PDF 타임아웃은 확인 가능한 원본과 변경 추적 사본에서 재현되지 않아 미해결로 남깁니다. **Draft 유지, main 병합 금지.**

## 변경

| 항목 | 결과 | 처리 내용 |
|---|---|---|
| 종업원수 현재 기간 | 수정·검증 완료 | 네 번째 행 이후도 탐색. 작년·올해·올해(예상)·금년 및 실제 올해 연도를 인식하고 논리 colAddr+colSpan으로 값 칸 대응. 과거만 있거나 모호한 경우 사유 기록 후 인라인 동의어 채움도 보류. 비헤더 연도와 좌우 다른 라벨의 값 영역을 보호. |
| 창업아이템 개요 | 수정·검증 완료 | 구체적인 괄호 안내 구문만 user_brief로 채움. 괄호 안이라는 이유로 실제 서술형 입력을 덮지 않으며 EXISTING_VALUE 보존 검증. |
| IP디딤돌 PDF | 원인 미재현·수정 없음 | 한글 2022의 실제 저장 결과는 아래 참조. 타임아웃 숫자·PDF 코어·소유 PID 보호는 변경하지 않았으며 타임아웃 해결을 주장하지 않음. |

기존 Round4 과거 2사례는 삭제·skip 없이 원본 전체 값 칸 보존과 미기입 사유 검사로 강화했습니다. 신규 skip/xfail 없음. 제품 변경은 hwpx_fill.py만이며 범위 밖 코어 변경 없음.

## 확인

- [x] Windows 전체 pytest **1회**: **2275 passed / 0 failed / 5 기존 skipped / 23 subtests passed**, exit 0, 943.29초.
- [x] 영향 회귀: **89 passed / 0 failed** (현재 기간·괄호 실값·PDF mock·COM 소유권).
- [x] 안전 검토: 기존 오기입 6종, 변형 포함 14개 메모리 XML 사례 PASS.
- [x] 원본 bytes, 변경 대상 외 ZIP member, 병합 구조·열주소 보존 검사.

```powershell
Set-Location -LiteralPath 'D:\auto_write'
$env:PYTHONUTF8='1'
py -3.11 -m pytest -q --tb=short --junitxml=_preflight_evidence/round5-20261006/full-pytest.xml
```

전체 테스트한 제품 코드 SHA: `2cb684e8d3310411019656f015b3054451990a9f`.
현재 PR 헤드 SHA: `2f630a62eef6377c3ccdfc15d75587c5c17a4bd2`. 전체 실행 후 추가 커밋은 TASK.md·RESUME.md·검증 보고서 문서뿐이며 제품 코드와 테스트는 검증 SHA와 동일합니다.
기준 main: `12b5095f9fbeacb02257b3f169d5924f7fc947a2`, 문서 PR #215 병합 완료. AGENTS.md·CLAUDE.md의 원격 TASK→RESUME 필수 시작 순서는 main에서 실제 조회했습니다.

## 실제 한글 2022 PDF 결과

버전 12.0.0.893, 별도 사본에서 기존 SetMessageBoxMode(0x10)+SaveAs[PDF] 실행.

| 입력 조건 | 실제 저장 결과 | 확인 |
|---|---:|---|
| 2026년 IP디딤돌 HWP 원본 사본 | True, 65.609초 | 유효 PDF 2페이지·아이디어 텍스트 |
| 2025년 IP디딤돌 HWPX 원본 사본 | True, 1.578초 | 유효 PDF 2페이지·아이디어 텍스트 |
| 2025년 사본의 변경 추적 설정+문구 삽입 | True, 3.953초 | 유효 PDF 3페이지·추가 문구 보존 |

같은 변경 추적 사본의 FileSaveAsPdf도 True(13.375초)였지만 개선 근거가 없어 저장 경로를 대체하지 않았습니다. 원본·사본 해시와 기존 사용자 한글 생존, 정리 후 소유 PID 잔존 없음 확인. 위 성공은 요청한 120초 타임아웃의 수정 성공을 의미하지 않습니다.

PDF mock 3사례(성공·거부·타임아웃)는 자동확인 호출 순서, 120초 제한 유지, 소유 PID만 정리, 기존/동시에 열린 다른 사용자 PID와 원본 보존을 검증합니다. Mock 통과와 실제 PDF 저장 성공을 구분합니다.

## 남은 문제

정확한 실패 입력을 확인하지 못했고 사용자는 경로를 모른다고 답했습니다. 해당 입력 확보 후 한글 2022에서 120초 타임아웃을 재현해야 합니다. **REQUEST_SOLVED=NO / PARTIAL**. 기존 DOCX Open 실패·소유 미확인 hard timeout 한계와 L050 gap은 유지합니다. 로컬 증거·data·백업·개인 기록과 기존 위키 변경은 커밋하지 않습니다.

공유 재개: [RESUME.md](https://github.com/pds2225/auto_write/blob/codex/round5-fill-fixes/RESUME.md). 항목별 검증 보고: [docs/ROUND5_FILL_FIXES.md](https://github.com/pds2225/auto_write/blob/codex/round5-fill-fixes/docs/ROUND5_FILL_FIXES.md).
