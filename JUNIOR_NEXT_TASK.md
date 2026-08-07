# JUNIOR_NEXT_TASK.md — Gate 1 재작업

## 역할
너는 구현 담당 주니어 개발자다. PM 승인 전 임의 판단으로 다음 단계로 넘어가지 않는다.

먼저 반드시 읽는다:
- `docs/repo-split/PM_GATE1_REVIEW.md`

## 현재 판정
**Gate 1 반려(REWORK REQUIRED).**

이유:
1. 66개 전수조사라고 했으나 ownership 합계가 45개뿐이다.
2. 지정 Python 3.11이 아니라 Python 3.12로 baseline을 실행했다.
3. `docx-duplicate-map.md`가 원격 브랜치에 push되지 않았다.
4. PM 표본검수에서 ownership 오분류가 확인됐다.

## 절대 금지
- 파일 삭제 금지
- 기존 런타임 파일 이동 금지
- import 수정 금지
- 코드 리팩토링 금지
- 패키지 설치 금지
- venv 생성 금지
- 테스트 실패 수정 금지
- master 직접 push 금지

---

# STEP R1 — 66개 파일 재집계

로컬에 이미 만든 `docs/repo-split/docx-duplicate-map.md`를 다시 검수한다.

`app/core/docx/`에 현재 존재하는 파일을 재귀적으로 모두 열거하고 **실제 파일 수**를 먼저 산출한다.

PowerShell 예:
```powershell
cd C:\Users\ekth3\auto_write
$files = Get-ChildItem .\app\core\docx -Recurse -File
$files.Count
$files | ForEach-Object { $_.FullName.Replace((Get-Location).Path + '\\','') }
```

보고된 66과 실제 수가 다르면 실제 수를 기준으로 하고 이유를 기록한다.

## 분류표 컬럼

`docs/repo-split/docx-duplicate-map.md` 표를 아래 컬럼으로 고친다.

| staged_path | original_path | identical | file_role | imported_by | imports | ownership | reason | proposed_action |
|---|---|---|---|---|---|---|---|---|

### ownership 값
- CORE
- RESUME
- BIZPLAN
- MIXED
- NONE

### file_role 값
- SERVICE
- CLI
- TEST
- PACKAGE_META
- TOOLING
- CASE_SCRIPT

### proposed_action 값
- KEEP_CORE
- MOVE_RESUME
- MOVE_BIZPLAN
- MIXED_REFACTOR
- KEEP_SCRIPT
- KEEP_TEST_WITH_OWNER
- KEEP_PACKAGE_META
- KEEP_LEGACY_OR_SALVAGE

**모든 파일은 정확히 1행이어야 한다. 누락/중복 행 금지.**

문서 하단에 집계표를 추가한다.

```text
TOTAL_FILES = n

ownership:
CORE = n
RESUME = n
BIZPLAN = n
MIXED = n
NONE = n
SUM = n

file_role:
SERVICE = n
CLI = n
TEST = n
PACKAGE_META = n
TOOLING = n
CASE_SCRIPT = n
SUM = n
```

두 SUM 모두 TOTAL_FILES와 정확히 같아야 한다.

---

# STEP R2 — PM 지적 파일 재검토

아래 파일은 기존 판정을 그대로 복사하지 말고 코드와 import 사용처를 다시 확인한다.

## 1. cross_form_autofill.py
PM 기본판정: `MIXED`

근거:
- 본체는 사업계획서/양식간 자동전사 기능
- `resume_extract.py`가 `rank_source_pool` 기능을 재사용

따라서 whole-file MOVE_BIZPLAN을 승인하지 않는다.
`rank_source_pool` 및 관련 범용 helper를 CORE로 추출할 필요가 있는지 `reason`에 기록한다.

## 2. render_service.py
PM 기본판정: `MIXED`

근거:
- 범용 `TemplateProfile`, `ProjectInput`, DOCX 렌더링
- 동시에 `psst_only`, `psst_field_ids`, `core_table_ids` 같은 사업계획서 옵션 포함

공통 렌더러와 PSST 정책을 분리할 수 있는지 기록한다.

## 3. defect_classifier.py
PM 기본판정: `CORE` 후보

사업계획서 전용 근거가 실제 코드에 없으면 CORE로 수정한다.

## 4. quality_rules.py
PM 기본판정: `BIZPLAN` 후보

사업계획서 규칙 프리셋이 명시되어 있으므로 별도 반대 근거가 없으면 BIZPLAN 유지.

## 5. scripts/docx2hwp.py
ownership=`CORE`
file_role=`TOOLING`
proposed_action=`KEEP_SCRIPT`

`app/core/docx/cli/`의 복사본을 canonical로 만들지 않는다.
원본 `scripts/docx2hwp.py`를 실행 진입점으로 유지하는 방향을 기록한다.

## 6. scripts/run_document_quality_harness.py
ownership=`CORE`
file_role=`TOOLING`
proposed_action=`KEEP_SCRIPT`

## 7. scripts/extract_doc_data.py
ownership=`NONE`
file_role=`CASE_SCRIPT`
proposed_action=`KEEP_LEGACY_OR_SALVAGE`

이 파일은 특정 미래큐러스 문서와 로컬 임시경로가 하드코딩되어 있으므로 공유 core로 분류하지 않는다.

---

# STEP R3 — Python 3.11 환경 인벤토리

**설치하지 말고 조사만 한다.**

다음을 실행한다.

```powershell
cd C:\Users\ekth3\auto_write

py -0p

$py311 = "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"
Test-Path $py311

if (Test-Path $py311) {
    & $py311 --version
    & $py311 -m pip --version
    & $py311 -m pip show pytest python-docx lxml PyMuPDF openai matplotlib
}
```

추가로 현재 명령 해석 상태를 확인한다.

```powershell
Get-Command python -ErrorAction SilentlyContinue
Get-Command py -ErrorAction SilentlyContinue
python --version
```

결과를 새 파일에 기록한다.

`docs/repo-split/baseline-env.md`

반드시 기록:
- 설치된 Python 목록
- Python 3.11 존재 여부
- Python 3.11 정확한 경로
- pip 버전
- pytest/python-docx/lxml/PyMuPDF/openai/matplotlib 설치 여부와 버전
- 직전 Python 3.12 테스트가 왜 baseline으로 무효인지
- 다음 PM 승인 후 필요한 환경조치 제안

**requirements 설치 금지.**

---

# STEP R4 — Git 반영

구조 변경 없이 문서 2개만 commit한다.

허용 파일:
- `docs/repo-split/docx-duplicate-map.md`
- `docs/repo-split/baseline-env.md`

먼저 확인:
```powershell
git status --short
```

위 2개 이외에 예상치 못한 변경이 있으면 commit하지 말고 보고한다.

정상이면:
```powershell
git add docs/repo-split/docx-duplicate-map.md docs/repo-split/baseline-env.md
git commit -m "docs: complete Gate 1 repository split audit"
git fetch origin
git rebase origin/refactor/repo-split-pm
git push origin refactor/repo-split-pm
```

rebase 충돌이 나면 임의 해결하지 말고 중단 후 보고한다.

---

# STEP R5 — 여기서 중지

push 성공 후 더 진행하지 않는다.

보고 형식:

```text
[GATE]
Gate 1 REWORK 완료 / 미완료

[FILES]
TOTAL_FILES
ownership별 개수와 SUM
file_role별 개수와 SUM

[CORRECTIONS]
기존 판정에서 변경된 파일과 변경 전→후

[ENV]
Python 3.11 존재 여부
경로
필수 패키지 상태

[GIT]
commit SHA
push 성공 여부
unexpected changes 여부

[DECISION NEEDED]
PM이 결정할 사항
```

PM 승인 전 T1.1/T1.2 금지.