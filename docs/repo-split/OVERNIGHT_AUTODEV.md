# OVERNIGHT_AUTODEV.md — auto_write 저장소 분리 야간 자율개발 Runbook

기준일: 2026-08-07
작업 브랜치: `refactor/repo-split-pm`
대상 저장소: `C:\Users\ekth3\auto_write`
목표: 아침 PM 일괄검수를 위해 저장소 분리 작업을 가능한 범위까지 자율 진행한다.

## 0. 역할

너는 야간 자동개발 담당 주니어 개발자다.
사람의 중간 승인을 기다리지 말고 아래 Runbook 순서대로 최대한 진행한다.
단, 안전 경계는 절대 넘지 않는다.

## 1. 절대 금지 — 위반 시 즉시 중단

- `master` 직접 commit/push 금지
- PR merge 금지
- force push 금지
- 기존 파일 영구 삭제 금지
- `git reset --hard`, `git clean -fd`, `git checkout -- .` 금지
- Secret/API Key/.env 내용 출력 금지
- 사용자 데이터/산출물/results/templates 원본 삭제 금지
- 유료 API 호출 금지
- 사용자 입력이 필요한 HWP COM GUI 자동화 금지
- 다른 저장소 수정 금지
- 리포지토리 밖 사용자 파일 수정 금지

## 2. 야간 작업 원칙

1. 모든 작업은 `refactor/repo-split-pm`에서만 한다.
2. 한 번에 대규모 리팩토링하지 않는다.
3. 작업 단위를 작게 나누고 각 단계마다 commit한다.
4. 실제 삭제 대신 compatibility wrapper / re-export / legacy 보존을 우선한다.
5. 테스트가 실패하면 실패 원인을 기록하고, 현재 변경 때문에 발생한 회귀만 수정한다.
6. 기존 baseline 실패를 억지로 고치지 않는다.
7. 판단이 애매한 파일은 `MIXED` 또는 legacy 유지로 보수적으로 처리한다.
8. 작업 결과는 반드시 `docs/repo-split/OVERNIGHT_REPORT.md`에 누적 기록한다.

## 3. 시작 전 Git 안전점검

```powershell
cd C:\Users\ekth3\auto_write
git fetch origin
git branch --show-current
git status --short
git log --oneline --decorate -10
```

현재 브랜치가 `refactor/repo-split-pm`가 아니면:

```powershell
git switch refactor/repo-split-pm
```

원격보다 뒤처졌으면 로컬 변경을 보존한 상태에서:

```powershell
git fetch origin
git rebase origin/refactor/repo-split-pm
```

충돌이 발생하면 임의로 대규모 해결하지 말고 `OVERNIGHT_REPORT.md`에 BLOCKER를 기록하고 코드 변경을 멈춘다.

---

# PHASE A — Gate 1 감사 완료

기존 `docs/repo-split/PM_GATE1_REVIEW.md`와 현재 `JUNIOR_NEXT_TASK.md`의 Gate 1 재작업 요구사항을 먼저 수행한다.

필수 산출물:
- `docs/repo-split/docx-duplicate-map.md`
- `docs/repo-split/baseline-env.md`

필수 조건:
- `app/core/docx/` 실제 파일 수 = 표 행 수
- ownership 합계 = 실제 파일 수
- file_role 합계 = 실제 파일 수
- 중복 행 0
- 누락 행 0

ownership:
- CORE
- RESUME
- BIZPLAN
- MIXED
- NONE

file_role:
- SERVICE
- CLI
- TEST
- PACKAGE_META
- TOOLING
- CASE_SCRIPT

PM 기본판정은 아래를 우선한다.
- `cross_form_autofill.py` → MIXED 후보
- `render_service.py` → MIXED 후보
- `defect_classifier.py` → CORE 후보
- `quality_rules.py` → BIZPLAN 후보
- `scripts/docx2hwp.py` → CORE/TOOLING, canonical은 scripts 유지
- `scripts/run_document_quality_harness.py` → CORE/TOOLING, canonical은 scripts 유지
- `scripts/extract_doc_data.py` → NONE/CASE_SCRIPT, core 편입 금지

PHASE A 완료 시 commit:

```text
docs: complete repository split ownership audit
```

---

# PHASE B — 테스트 환경 확보

## B-1. Python 3.11 우선

```powershell
py -0p
$py311 = "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"
```

Python 3.11이 존재하고 필요한 패키지가 이미 설치되어 있으면 그대로 사용한다.

## B-2. 패키지가 부족한 경우

글로벌 Python 환경은 수정하지 않는다.
Python 3.11이 존재할 경우에만 repo 밖 TEMP 영역에 임시 venv를 만들 수 있다.

예:

```powershell
$venv = Join-Path $env:TEMP "auto_write_repo_split_venv"
& $py311 -m venv $venv
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r C:\Users\ekth3\auto_write\app\requirements.txt
& $py -m pip install pytest
```

규칙:
- 설치 실패 시 반복 무한재시도 금지
- 최대 1회 설치 시도
- 설치 실패 내용을 보고서에 기록
- API를 실제 호출하는 테스트는 실행하지 않는다

Python 3.11 자체가 없으면 설치하지 않는다. 사용 가능한 기존 Python 중 프로젝트 규약에 가장 가까운 버전으로 정적검증만 진행하고 제한사항을 기록한다.

---

# PHASE C — 진짜 baseline 확보

가능한 테스트 환경이 확보되면 변경 전 baseline을 측정한다.

```powershell
$env:PYTHONPATH = "C:\Users\ekth3\auto_write\app"
& $py -m pytest C:\Users\ekth3\auto_write\app\tests -q
```

전체 테스트가 너무 오래 걸리거나 환경 의존 실패가 많으면 다음을 병행한다.

```powershell
& $py -m pytest C:\Users\ekth3\auto_write\app\tests\test_docx_ops.py -q
& $py -m pytest C:\Users\ekth3\auto_write\app\tests\test_cross_form_autofill.py -q
& $py -m pytest C:\Users\ekth3\auto_write\app\tests\test_resume_form_fill.py -q
& $py -m pytest C:\Users\ekth3\auto_write\app\tests\test_document_quality_harness.py -q
```

기록:
- passed
- failed
- skipped
- collection errors
- 환경성 실패
- 코드성 실패

baseline 자체의 기존 실패는 이번 작업 범위에서 수정하지 않는다.

---

# PHASE D — 최종 목표 구조 골격 생성

아래 패키지 골격만 먼저 만든다.

```text
app/
  core/
    __init__.py
    docx/
      __init__.py
  resume/
    __init__.py
    services/
      __init__.py
    cli/
      __init__.py
  bizplan/
    __init__.py
    services/
      __init__.py
    cli/
      __init__.py
```

주의:
- 기존 파일은 아직 삭제하지 않는다.
- `app/core/docx/` 기존 복사본은 staging 자료로 취급한다.
- package skeleton 생성 후 import smoke test를 수행한다.

```powershell
& $py -c "import core; import resume; import bizplan; print('OK')"
```

commit:

```text
refactor: add core resume bizplan package skeleton
```

---

# PHASE E — CORE canonicalization

## E-1. CORE 대상 원칙

다음 성격만 CORE로 canonical화한다.
- DOCX/HWP/HWPX 범용 I/O
- 문서 텍스트 추출
- 공통 렌더링 primitive
- 품질 검사 primitive
- 공통 데이터 모델/utility
- 두 도메인에서 실제 재사용되는 helper

도메인 정책(PSST, 지원사업 평가, 이력서 경력/학력)은 CORE에 넣지 않는다.

## E-2. staging 복사본 직접 채택 금지

`app/core/docx/`의 복사본과 기존 `app/auto_write/...` 원본이 동일한지 확인한다.
원본이 더 최신이면 원본을 기준으로 한다.

canonical 파일을 정한 뒤에도 기존 import 호환성을 깨지 않는다.

우선 전략:
1. 새 canonical 위치에 구현 유지
2. 기존 위치는 thin compatibility wrapper로 전환 가능
3. wrapper는 명시적 re-export만 수행
4. 실제 삭제는 이번 야간 작업에서 하지 않는다

예시 방향:

```python
# legacy path compatibility wrapper
from core.docx.services.docx_ops import *  # noqa
```

단, wildcard가 기존 공개 API를 불명확하게 만들면 명시적 symbol re-export를 사용한다.

## E-3. 한 번에 최대 3~5개 서비스만 canonicalize

각 묶음마다:
- import 검색
- 이동/복사/compat wrapper
- targeted tests
- commit

추천 첫 묶음:
- docx_ops
- doc_text_extract
- hwp_docx_convert
- hwpx_fill
- document_ingest

각 묶음 테스트 실패가 증가하면 그 묶음 변경을 추가 확대하지 않는다.

commit 예:

```text
refactor: canonicalize shared document core batch 1
```

---

# PHASE F — RESUME 분리

ownership audit에서 RESUME로 확정된 파일만 처리한다.

예상 후보:
- resume_fill_service.py
- resume_extract.py
- resume 전용 CLI
- resume 전용 테스트

원칙:
- `resume -> core` 의존 허용
- `core -> resume` 의존 금지
- `resume -> bizplan` 의존 금지

`resume_extract.py`가 `cross_form_autofill.rank_source_pool`에 의존하는 경우에는 전체 cross_form을 import하지 않도록 범용 source ranking helper를 CORE로 추출하는 것을 우선한다.

추출 시:
- 동작 변경 금지
- 원 함수와 동일 결과를 보장하는 테스트 추가
- 기존 import는 compatibility wrapper로 유지

commit 예:

```text
refactor: separate resume domain services
```

---

# PHASE G — BIZPLAN 분리

ownership audit에서 BIZPLAN로 확정된 파일만 처리한다.

예상 후보:
- psst_fill.py
- quality_rules.py
- 사업계획서 전용 orchestrator/pipeline
- 지원사업 평가/공고분석 정책
- bizplan 전용 CLI

원칙:
- `bizplan -> core` 의존 허용
- `core -> bizplan` 의존 금지
- `bizplan -> resume` 의존 금지

`render_service.py`처럼 범용 렌더링 + PSST 정책이 섞인 파일은 통째로 BIZPLAN로 이동하지 않는다.
가능하면:
- 범용 renderer → CORE
- PSST selection/policy → BIZPLAN
으로 분리한다.

`cross_form_autofill.py`도 whole-file 이동보다 공통 helper 추출 후 사업계획서 전사 엔진을 BIZPLAN에 두는 방향을 우선한다.

commit 예:

```text
refactor: separate business plan domain services
```

---

# PHASE H — 중복 및 import graph 검사

다음을 검색한다.

```powershell
rg "from auto_write|import auto_write|from core|from resume|from bizplan" app
```

규칙 위반을 확인한다.

금지 dependency:
- core -> resume
- core -> bizplan
- resume -> bizplan
- bizplan -> resume

허용:
- resume -> core
- bizplan -> core

compatibility wrapper 때문에 legacy `auto_write -> core`는 임시 허용한다.

또한 같은 구현이 두 곳에 그대로 복제되어 살아있는지 SHA/hash 또는 diff로 검사한다.
단, 기존 경로 호환 wrapper는 중복 구현으로 간주하지 않는다.

산출물:
- `docs/repo-split/import-graph-audit.md`

commit:

```text
docs: add repository split import graph audit
```

---

# PHASE I — 테스트 및 회귀 검증

각 도메인 targeted tests를 실행한다.

최소:
- core document tests
- resume tests
- bizplan/cross-form/PSST tests
- document quality harness tests

가능하면 전체:

```powershell
& $py -m pytest C:\Users\ekth3\auto_write\app\tests -q
```

비교:
- baseline 대비 신규 fail 수
- collection error 증감
- import error 증감

규칙:
- 이번 구조 변경으로 생긴 신규 실패는 수정한다.
- 기존 baseline 실패는 별도 표기한다.
- 테스트를 삭제/skip 처리해서 통과시키지 않는다.

---

# PHASE J — 문서 동기화

다음을 현재 실제 구조 기준으로 갱신한다.
- `README.md`
- `AGENTS.md`
- `.omc/wiki/auto-write-split-plan.md`가 존재하면 갱신
- `docs/repo-split/OVERNIGHT_REPORT.md`

중요:
기존 README의 `app/core/docx = 66개 파일` 같은 임시 설명은 실제 결과와 맞게 수정한다.

---

# PHASE K — 최종 야간 보고

`docs/repo-split/OVERNIGHT_REPORT.md`에 반드시 아래를 기록한다.

```text
# Overnight Repository Split Report

## 1. Executive Summary
- 완료 단계
- 미완료 단계
- 가장 큰 blocker

## 2. Git
- branch
- 시작 SHA
- 마지막 SHA
- 생성 commit 목록
- master/merge/force-push 미수행 확인

## 3. Ownership Audit
- TOTAL
- CORE
- RESUME
- BIZPLAN
- MIXED
- NONE

## 4. Files Changed
- 생성
- 이동/복제
- compatibility wrapper
- 문서

## 5. Dependency Audit
- core -> resume 위반
- core -> bizplan 위반
- resume -> bizplan 위반
- bizplan -> resume 위반
- remaining MIXED

## 6. Tests
- baseline
- final
- 신규 failures
- 기존 failures
- skipped
- environment blockers

## 7. Risks
각 위험을 HIGH/MEDIUM/LOW로 구분

## 8. Morning PM Review Required
아침에 PM이 반드시 봐야 하는 파일/commit/판단 10개 이내

## 9. Rollback Points
각 주요 단계 직전 commit SHA

## 10. Next Recommended Actions
우선순위 P0/P1/P2
```

마지막 commit:

```text
docs: finalize overnight repository split report
```

그 후:

```powershell
git status --short
git log --oneline --decorate -20
git push origin refactor/repo-split-pm
```

push 성공 후 멈춘다.

## 4. 자동개발 중 STOP 조건

아래 중 하나면 추가 구조변경을 멈추고 보고서 작성/commit/push만 수행한다.

- merge conflict 해결이 불명확함
- 원본 파일 삭제가 필요하다고 판단됨
- Secret 노출 위험
- 20개 이상 신규 테스트 실패 발생
- 핵심 CLI import가 대량 붕괴
- 사용자의 실제 문서/산출물 변경이 필요함
- HWP GUI 승인이 필요함
- 다른 저장소 수정이 필요함
- master 변경이 필요함

## 5. 성공 기준

야간 작업 성공은 "모든 리팩토링 완료"가 아니다.
아래를 만족하면 성공으로 간주한다.

1. master 무변경
2. 원본 삭제 0
3. 작업 브랜치에 작은 commit 단위 보존
4. ownership/import graph가 문서화됨
5. 가능한 범위의 core/resume/bizplan 분리가 구현됨
6. 테스트 baseline과 final 비교 가능
7. 아침 PM이 diff를 한 번에 검수할 수 있는 `OVERNIGHT_REPORT.md` 존재
