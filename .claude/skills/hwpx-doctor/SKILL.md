---
name: hwpx-doctor
description: >
  한글(HWP/HWPX) 파일이 안 열릴 때 원인을 진단하고 자동으로 고치는 도구.
  한글은 zip/XML이 멀쩡해도 표 격자(cellAddr rowAddr/colAddr) 충돌·ID 참조 오류·itemCnt
  불일치 같은 '의미 규칙'을 어기면 문서 열기를 거부한다. 이 스킬은 그 의미 규칙을 검사하고,
  자동 교정 가능한 결함(깨진 표 격자)을 고쳐 원본 서식 그대로의 수정본을 만든다.
  다음 요청·증상에 반드시 사용: "hwpx 안 열려", "한글 파일 안 열림", "한글에서 안 열려",
  "불러오기 안 됨", "빈 문서로 열려", "hwpx 진단", "hwpx 수정", "한글 문서 깨졌어",
  "프로그램으로 만든 hwpx가 한글에서 안 열림", "표 격자 깨짐", "이 hwpx 뭐가 문제야",
  "hwpx doctor", "파일 고쳐줘"(한글 파일 맥락). 재실행·다른 파일 진단·수정도 이 스킬로 처리.
  ※ HWP↔DOCX '변환'은 docx-hwp-conversion, 완성 문서 서식 '품질개선'은
  document-quality-orchestrator 담당 — 이 스킬은 "안 열리는 한글 파일을 열리게 고치는" 전용.
---

# hwpx-doctor — 안 열리는 한글 파일 진단·수정

## 언제 쓰나
프로그램(auto_write 등)으로 만들거나 편집한 hwpx가 **한글에서 안 열리거나 빈 문서로 뜰 때.**
파일 구조(zip/XML)는 멀쩡한데 한글이 거부하는 경우, 원인은 대개 **의미 규칙 위반**이다:
- **표 격자 깨짐**(가장 흔함): 셀 주소(rowAddr/colAddr)가 물리 위치와 어긋나 겹치거나 비어 있음.
  실측(박다솜 프로필 v3~v7): 채움 스크립트가 행 추가 시 rowAddr를 안 늘려 마지막 행이 겹침 → 한글 열기 거부.
- **ID 참조 오류**: section이 header에 없는 charPr/paraPr/style/borderFill id를 참조.
- **itemCnt 불일치**: 헤더 refList의 itemCnt가 실제 항목 수와 다름.

## 먼저 확인 (환경 vs 파일)
"안 열림"이 **파일** 문제인지 **한글 앱** 문제인지 먼저 가른다:
- 다른 한글 파일은 열리는데 이 파일만 안 열림 → **파일 문제** → 이 스킬로 진단·수정.
- 한글 자체가 무응답/모든 파일 안 열림(COM Version 공백 등) → **한글 앱 문제** → PC 재부팅/재활성화 안내(파일 수정 무의미).

## 실행 (PowerShell)
```powershell
cd D:\auto_write\app
# 1) 진단 — 무엇이 문제인지 (종료코드 0=정상 / 2=결함)
python hwpx_doctor.py diagnose "C:\경로\문서.hwpx"
# 2) 수정 — 깨진 표 격자 자동 교정한 수정본 생성 (원본 보존)
python hwpx_doctor.py repair "C:\경로\문서.hwpx"            # → 문서_수정.hwpx
python hwpx_doctor.py repair "문서.hwpx" -o "고친것.hwpx"
```
수정 후 그 파일을 `Start-Process`로 열어 사용자가 바로 확인하게 한다.

## 동작 원리 (엔진)
- 진단·교정 엔진 = `app/auto_write/services/hwpx_layout_fix.py`
  - `check_hwpx_semantics(path)` — itemCnt·ID참조·표격자 검사(읽기 전용).
  - `validate_table_grid(tbl)` — 표 격자 타일링 검증(P0).
  - `repair_table_grid(tbl)` / `repair_all_table_grids(section)` — 깨진 표 자동 재주소화.
- **자동 예방**: `finalize_layout_hwpx(..., repair_grid=True)`(기본)에 배선돼, hwpx_submit 등
  제출·마감 경로로 나가는 모든 hwpx가 저장 직전 격자 자동교정된다 → 깨진 파일이 애초에 안 나감.

## 안전 원칙 (불변)
- **원본 미수정**: 항상 새 파일(`_수정`)로 저장. 출력=입력이면 거부.
- **병합 표 보호**: rowSpan/colSpan>1 병합이 있는 표는 자동 교정하지 않는다(정상 병합을
  깨뜨릴 위험 → 사람 확인). 1×1 셀 표의 명백한 주소 오류만 고친다.
- **멱등**: 이미 정상인 문서엔 아무것도 바꾸지 않는다.
- 자동 교정으로 못 고치는 결함(ID참조·itemCnt·병합 표)은 정직하게 보고하고 수동 확인 안내.
