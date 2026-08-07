# JUNIOR_NEXT_TASK.md — 저장소 분리 다음 작업

## 역할
너는 구현 담당 주니어 개발자다. PM 승인 전 임의 판단으로 다음 단계로 넘어가지 않는다.

## 절대 금지
- 파일 삭제 금지
- 기존 파일 이동 금지
- import 경로 변경 금지
- master 직접 push 금지
- 기능 수정 금지
- 코드 리팩토링 금지
- app/core/docx 복사본과 기존 원본을 동시에 수정 금지

## STEP A-1 — Git baseline

1. 다음 브랜치로 전환한다.

```powershell
git switch refactor/repo-split-pm
```

2. 다음을 실행한다.

```powershell
cd C:\Users\ekth3\auto_write
git status
git branch --show-current
git fetch origin
git log --oneline --decorate -10
```

3. 결과를 요약한다.

## STEP A-2 — DOCX 중복소스 조사

`app/core/docx/` 아래 복사본 전체를 조사한다.

각 파일별로 아래를 확인한다.
- staged_path
- original_path
- 두 파일이 현재 동일한지
- 이 파일을 import하는 파일
- 이 파일이 import하는 모듈
- 실제 기능
- 이력서에서 사용하는지
- 사업계획서에서 사용하는지
- 공통으로 사용하는지

ownership은 아래 중 하나만 사용한다.
- CORE
- RESUME
- BIZPLAN
- MIXED

### 판단 기준

**CORE**
이력서와 사업계획서 양쪽에서 사용할 수 있는 공통 문서 처리 기능

**RESUME**
컨설턴트 신청서/이력서/경력/학력/자격 작성에 종속된 기능

**BIZPLAN**
PSST/공고문/평가기준/지원사업/사업계획서 작성에 종속된 기능

**MIXED**
공통 기능과 도메인 기능이 한 파일 안에 섞인 경우

특히 다음 파일은 이름만 보고 core로 확정하지 말고 의존성을 확인한다.
- resume_fill.py
- resume_fill_service.py
- psst_fill.py
- cross_form_autofill.py
- company_master.py
- document_ingest.py
- docx_template.py

## 산출물

다음 파일을 생성한다.

`docs/repo-split/docx-duplicate-map.md`

표 형식:

| staged_path | original_path | identical | imported_by | imports | ownership | reason | proposed_action |
|---|---|---|---|---|---|---|---|

`proposed_action`은 아래 값만 사용한다.
- KEEP_CORE
- MOVE_RESUME
- MOVE_BIZPLAN
- MIXED_REFACTOR

## STEP A-3 — 현재 테스트 baseline

Python 3.11 기준으로 현재 테스트 baseline을 측정한다.

```powershell
$py = "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONPATH = "C:\Users\ekth3\auto_write\app"
& $py -m pytest C:\Users\ekth3\auto_write\app\tests -q
```

실패가 있어도 수정하지 않는다. 현재 baseline 기록이 목적이다.

## 중요: 여기서 중지

여기까지 수행하고 멈춘다.

아래 작업은 PM 승인 전 금지한다.
- `app/core/`, `app/resume/`, `app/bizplan/` 구조 변경
- 기존 파일 이동
- 기존 파일 삭제
- import 수정
- 실패 테스트 수정
- 대규모 리팩토링

## 완료 보고 형식

```text
[STEP]
수행한 단계

[CHANGED]
생성/수정 파일

[FOUND]
중복 구조
CORE/RESUME/BIZPLAN/MIXED 각각 파일 수
순환 import 위험
중요 의존성

[TEST]
실행 명령
passed
failed
skipped
error

[DECISION NEEDED]
PM 판단이 필요한 사항

[NEXT]
다음으로 해야 할 작업 1개만 제안
```

그 이상 진행하지 말 것.
