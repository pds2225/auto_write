---
description: 사업계획서 PSST 4영역(문제·실현·성장·팀) 충실도만 단독 검사한다
argument-hint: <input.docx> [--json]
---

# /auto-write-psst

## 사용 목적

사업계획서/발표평가 유형 DOCX의 **PSST 4영역 구조 충실도**만 단독으로 검사한다.
`auto_write.services.psst_check.check_psst(doc)` 를 호출해 각 영역의 누락·미흡 항목을
리포트한다. 전체 품질 후처리/점수 게이팅은 하지 않는다(그건 `/auto-write-quality`).

PSST = Problem(문제인식) / Solution(실현가능성) / Scale-up(성장전략) / Team(팀구성).
각 영역마다 핵심 하위항목 4개를 본문 키워드로 탐지하고, 영역별 등급을 매긴다.
등급 4단계: **누락 / 미흡 / 적정 / 우수** (충족비율 0=누락, 0.6미만=미흡, 0.6이상=적정, 0.9이상=우수).

쉽게 말하면: 사업계획서에 "문제·해결·성장·팀" 4개 블록이 빠짐없이, 알맹이 있게
들어갔는지만 빠르게 점검하는 검사 전용 명령이다. 파일을 고치지 않는다(읽기 전용).

## 입력값

- `input.docx` (필수): 검사할 DOCX 절대경로 또는 `app` 기준 상대경로.
- `--json` (선택): 결과를 JSON 으로 출력(`PSSTReport.as_dict()` 형식).

검사 대상 유형: business_plan(사업계획서), pitch_deck(발표평가) 권장.
그 외 유형도 호출 자체는 동작하나 PSST 양식이 없으면 대부분 "누락"으로 나온다.

## 실행 워크플로우(단계)

1. **유형 확인(권장)**: 입력 DOCX가 사업계획서/발표평가인지 먼저 분류한다.
   `document_type_classifier.classify_docx(path)` 결과가 business_plan/pitch_deck 가 아니면
   사용자에게 "PSST 검사 대상 유형이 아님"을 알리고 진행 여부를 묻는다.
2. **문서 로드**: `from docx import Document; doc = Document(path)`.
3. **PSST 검사 실행**: `from auto_write.services.psst_check import check_psst` 후 `report = check_psst(doc)`.
   - 섹션 헤더 존재 여부는 `ProjectService.PSST_*_RE` 정규식 재사용으로 판정(중복 구현 금지).
   - 각 영역 4개 하위항목을 본문 텍스트 키워드로 탐지해 found/missing 집계.
4. **결과 해석**: `report.overall_ratio`(전체 충족 비율), 영역별 `grade`/`missing_items`,
   `report.summary`(보완 필요 영역 요약)를 읽는다.
5. **보고**: 누락/미흡 영역과 빠진 하위항목을 구체적으로 제시한다. 파일은 수정하지 않는다.

검사 전용이므로 백업·후처리·점수산정·이미지삽입을 하지 않는다(원본 변경 없음).

## 호출 에이전트

- `doc-analyzer` (주): 유형 분류로 PSST 대상 여부 확인 → PSST 검사 실행·해석·보고.

## 출력물

- 콘솔 리포트: 영역별 등급(누락/미흡/적정/우수), 빠진 하위항목 목록, 전체 충족률, 보완 요약.
- `--json` 지정 시 `PSSTReport.as_dict()` JSON(applicable / overall_ratio / summary / areas[]).
- 파일 산출물 없음(읽기 전용 검사). 원본 DOCX 변경 없음, 백업 없음.

## 실패 시 처리

- 파일 없음/경로 오타: 절대경로 재확인 후 안내(수정 없이 종료).
- DOCX 아님/손상: `Document()` 로드 실패 메시지 그대로 보고, 진행 중단.
- 대상 유형 아님(business_plan/pitch_deck 아님): 경고만 출력하고 사용자 확인 후 진행.
- 전 영역 "누락": PSST 섹션 헤더가 양식에 없을 가능성. 먼저 `_build_chochang.py inspect` 로
  문단/표 구조를 덤프해 헤더 존재를 확인하라고 안내.
- import 오류: `app` 디렉토리에서 실행했는지(=`cd D:\auto_write\app`) 확인.

## 예시 명령(실제 PowerShell)

```powershell
# 1) app 디렉토리로 이동 (import 기준)
cd D:\auto_write\app

# 2) PSST 검사를 파이썬 한 줄로 단독 실행 (읽기 전용, 원본 변경 없음)
python -c "from docx import Document; from auto_write.services.psst_check import check_psst; r=check_psst(Document(r'C:\경로\사업계획서.docx')); print(r.summary); [print(a.label, a.grade, '누락:', a.missing_items) for a in r.areas]"

# 3) JSON 으로 받기
python -c "import json; from docx import Document; from auto_write.services.psst_check import check_psst; print(json.dumps(check_psst(Document(r'C:\경로\사업계획서.docx')).as_dict(), ensure_ascii=False, indent=2))"

# 4) 검사 대상 유형인지 먼저 확인
python -c "from auto_write.services.document_type_classifier import classify_docx; r=classify_docx(r'C:\경로\사업계획서.docx'); print(r.type_label, r.code, f'{r.confidence:.0%}')"

# 5) 섹션 헤더가 안 잡힐 때 구조 덤프로 원인 확인
python _build_chochang.py inspect "C:\경로\사업계획서.docx"
```

참고: 전체 품질 후처리+점수 게이팅까지 한 번에 하려면 PSST가 포함된 전체 파이프라인을 쓴다.
`python document_quality_orchestrator.py "C:\경로\사업계획서.docx"` (이 경우 business_plan/pitch_deck 에서 PSST 자동 포함).

## 보고 형식

첫 줄에 상태를 표시한다: **정상 실행 확인됨 / 미검증 / 실행 막힘 / 수정 없음**(검사 전용이므로 항상 "수정 없음").

1. 검사 대상 파일 경로(절대경로)와 분류 유형
2. PSST 전체 충족률(`overall_ratio`)과 한 줄 요약(`summary`)
3. 영역별 표: 영역 / 등급(누락·미흡·적정·우수) / 빠진 하위항목
4. 보완 필요 영역과 권장 보강 포인트(누락·미흡 영역 중심)
5. 실행한 명령어와 결과(검증됨/미검증)
