# PR #211 Round-4 — Windows 한글 2022 채움·소유권 회귀

- 저장소: pds2225/auto_write
- 브랜치: `cursor/rhwp-unsupported-lrule-status-6a12`
- 시작 코드: `360cbf99f6fda4008d790eb67976da0028b9438d`
- 새 PR 생성·머지·force push 없음. 기존 Round-3 미커밋 작업과 루트 변경은 보존한다.
- 작업 폴더: `D:\auto_write\.worktrees\pr211-round4` (독립 복제본)

| 항목 | 원인 | 수정 파일 및 처리 | 추가 회귀 |
|---|---|---|---|
| A | 기업명 예시와 괄호 안내가 여러 run에 나뉘면 split 보호에 걸림 | `app/core/docx/services/hwpx_fill.py`: 명백한 예시·안내로 승인된 값 칸의 run만 교체. 다른 칸 안내와 원본 유지 | `test_round4_mixed_example_and_guidance_cells` 기업명 |
| B | 날짜 뒤 안내가 있으면 전체 문자열 날짜 정규식 불일치 | 같은 파일: 0 날짜 뒤 작성·기재·기준 안내 허용 | 같은 테스트 개업연월일, 실제 날짜 보존 음성 테스트 |
| C | 여러 run의 파란 주소 예시가 split 보호에 걸림 | 같은 파일: 라벨·프로필이 매칭된 파란 예시 칸을 기존 예시 경로로 처리 | 같은 테스트 주소, 검정 실제 주소 보존 |
| D | 섹션 전체 used_keys 공유 및 T02가 팀명을 legacy identity에서 제거 | `hwpx_fill.py`, `app/auto_write/services/hwpx_submit.py`: 표 내부 중복은 유지하고 서약서/확약서 본문은 독립 사용. T02 팀명도 재전달, 작성된 같은 표 중복 방지 | 서약서·확약서, 같은 표, 실제 submit 경로 |
| E | ex) 시작 안내가 예시로 판정되지 않음 | `hwpx_fill.py`: ex) 안내만 있는 값 칸을 교체 | 같은 혼합 칸 테스트 업태, 실제 업태 보존 |
| F | 프로필 사업 개요·아이템 설명 키가 창업아이템 개요로 매핑되지 않음 | `app/auto_write/services/company_identity.py`: 한글·영문 개요 별칭을 사용자 원문 그대로 매핑. 생성·추론 없음 | 프로필 별칭 5개 합성 HWPX, 실제 submit |
| G | 오른쪽 첫 값 칸 및 T02가 과거 기간 칸을 선택 | `hwpx_fill.py`, `hwpx_submit.py`: 현재 열 우선, 없으면 마지막 기간 열. 모호 주소·중복 현재는 쓰지 않음. 기간표 종업원수의 과거열 T02 grant 차단 | 현재가 앞/뒤, 괄호 기간, 연도, 모호 현재, exact label submit, 다른 표 빈/실값 중복 |
| H | check_output이 테스트의 subprocess.run 패치를 호출 | `app/core/docx/services/hwp_docx_convert.py`, `app/tests/test_hwp_docx_convert.py`: tasklist는 Popen seam, 조회 예외는 빈 결과. 기본 rhwp 미호출 단언 유지 | Linux/win32 분기 파라미터, OSError/RuntimeError/AssertionError, run seam 미호출 |
| I | DOCX Open이 띄운 Hword를 정리하지 않아 WinError 32 발생 | `hwp_docx_convert.py`: 새 PID 중 이번 Python/소유 Hwp 자식만 추적하여 정상·실패·타임아웃 후 정리. 기존 Hwp 객체는 Open 전에 거절 | 정상/Open 예외/Open·SaveAs timeout, 기존·동시에 새로 연 비소유 Hword 보존. 실제 변환은 Open 실패, 입력 잠금 해제·잔존 PID 없음 확인 |
| J | WindowHandle 실패 시 소유권을 특정하지 못함 | 같은 파일: 조회 실패와 빈 목록 구분. fallback은 단일 Automation 후보 및 이번 Python 조상 증거 필수. 기존 Hwp 또는 소유 미확인 PID가 있으면 Visible/Open 전에 거절 | 핸들 유/무, Dispatch timeout, 조회 실패, 다른 세션 Automation, 일반 사용자 Hwp·다중 후보·기존 객체 보존. 소유 PID 미확인 시 hard timeout 보장은 미해결 |
| K | 실패 수를 허용하는 임시 CI가 남음 | `.github/workflows/pr-pytest-temp.yml` 삭제 | 삭제 diff 확인 |

새 합성·mock 회귀는 `app/tests/test_hwpx_round4_fill.py`, `app/tests/test_hwp_round4_ownership.py`에 있다. 기존 테스트 삭제·skip 추가·rhwp 미호출 단언 약화 없음. L050 gap/mechanized false와 rhwp 기본 OFF 유지.

## 검증 환경과 기준선

- Windows, Python 3.11, 설치된 한글 2022. PowerShell에서 실행한다.
- PATH의 기본 Python 3.14 대신 설치된 3.11을 선택한다. 명령은 `python -m pytest app/tests -q`와 동일 suite다.
- 기준선 복제본: `.round4-evidence/baseline-repo` (수정 없는 `360cbf9`). 원본 사용자 데이터는 쓰지 않았다.
- 기준선 전체: **35 failed, 2118 passed, 8 skipped, 23 subtests passed**, 1229.14초.
- 기준선 실패: rhwp 단언 1건, WinError 32 파일 잠금 16건, 실양식 fixture 부재 11건, Git 조회·origin/보안 검사 환경 6건, Lrule JSON 상태 1건. 기준선 복제본의 local origin/소유권 차이도 포함하므로 실패 감소 전부를 코드 효과로 해석하지 않는다.
- 샌드박스 계정은 사용자 한글 PID를 조회하지 못해 초기 실행이 정체됐다. 이 실행은 완료된 기준선으로 쓰지 않았다. 이후 실제 사용자 권한으로 두 suite를 실행했다.
- 수정 후 전체 suite와 실제 DOCX 잠금 smoke 결과는 아래 재개 검증에 기록했다.

## 2026-10-05 재개 검증

- 기존 `360cbf9`에 남아 있던 Round-4 수정본을 이어받았다. 날짜 자체가 여러 `hp:t`에 나뉜 경우는 원문을 보존하고 span note를 남기도록 최소 수정했다. 첫 run에 완전한 날짜가 있고 다음 run에 안내가 있는 예시는 계속 채운다.
- 실패 12건 중 11건은 독립 복제본에 검증용 `data`가 없어서 생겼다. 원본 `D:\auto_write\data`의 HWPX 489개를 로컬 검증용으로 복사하고 SHA-256 일치를 확인했다. 이 데이터와 `.round4-evidence/`는 Git에 넣지 않는다.
- 최초 실양식 회귀는 63 passed / 1 failed였다. Golden10만 복사하면 중첩 leaf를 검증할 추가 실양식이 없어 실패하므로 기존 검증 데이터 전체를 확보했다. 테스트를 삭제하거나 skip하지 않았다.
- 날짜·Round-4·Round-2 영향 회귀: 61 passed. 당시 실제 COM RPC 오류 로그도 발생했으므로 이 결과는 실제 한글 성공 근거가 아니다.
- 날짜·채움·중첩 양식·COM 영향 회귀: 96 passed. 최종 소유권 강화 후 COM 회귀 두 파일: 43 passed. 새 Round-4 두 파일은 채움 27개와 소유권 21개를 포함한다.
- 전체 suite 최종: **2206 passed, 0 failed, 5 skipped, 23 subtests passed**, 958.21초, exit 0. JUnit: `.round4-evidence/resumed-full.xml`. 이전 수정본의 실패 12건은 이번 실행에서 모두 해소됐다. 기본 COM 호출 중 RPC 오류 로그가 발생했으므로 실제 변환 성공 증거는 별도로 판단한다.

검증 명령(작업 폴더의 PowerShell, Python 3.11):

```powershell
Set-Location -LiteralPath 'D:\auto_write\.worktrees\pr211-round4'
$env:PYTHONUTF8='1'
py -3.11 -m pytest app/tests -q --junitxml=.round4-evidence/resumed-full.xml
py -3.11 .round4-evidence/resumed_smoke.py
```

### 실제 한글 2022 smoke와 남은 제한

- 한글 2022 COM 등록을 확인하고 합성 DOCX 1개를 HWP로 변환했다. 결과는 `ok=False`: 한글이 DOCX Open을 거절했다. 실제 변환 성공·제출 가능·실양식 9건 E2E 통과를 주장하지 않는다.
- 실패 후 입력 DOCX 이름 변경 가능, 원본 해시 보존, 새 Hwp/Hword 잔존 PID 없음, 기존 PID 보존을 확인했다. 실제 입력 잠금 해제·실패 정리는 통과했다.
- watchdog은 소유 프로세스를 종료할 수 없으면 블로킹 COM 호출 자체를 반환시키지 못한다. 모든 경우의 hard timeout 보장은 미해결이다. 소유권을 추측해 다른 세션 프로세스를 종료하는 방식으로 우회하지 않는다.
- 재발 방지는 날짜 보호 회귀와 PID 조회 실패·기존 객체·외부 Automation·비소유 Hword 음성 회귀로 검증한다. 기존 L003 실행 순서는 유지하되 현재 사용자 지시의 전역 종료 금지가 우선한다. L057에 따라 동일 COM 환경 오류를 반복 재진단하지 않는다.
- K 임시 CI 삭제는 유지했다. CI가 초록이어도 로컬 실사용 제한을 숨기지 않는다. PR #211은 기존 사용자 지시에 따라 draft·미병합으로 유지한다.

## 현재 확인 범위

- 10월 4일 새 회귀 43건 통과. 10월 5일 소유권 음성 회귀 5건을 추가했고, 기존 기본 rhwp 미호출 단언의 Windows 분기도 통과했다. 최신 전체 수치는 위 재개 검증에 기록한다.
- 원본 양식 9개의 Windows E2E와 픽셀 비교는 이번 합성/mock 검증으로 대체하여 완료 선언하지 않는다.
- L005 픽셀 PASS, L050 기계화, 제출가능 품질점수는 주장하지 않는다.
- 로컬 로그·JUnit·합성 결과는 `.round4-evidence`에 보존하고 PR에는 요약만 기록한다.
