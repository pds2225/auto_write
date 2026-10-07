# PM Gate 1 Review — Repository Split

기준일: 2026-08-07
브랜치: `refactor/repo-split-pm`
상태: **REJECTED / REWORK REQUIRED**

## 1. Gate 1 반려 사유

### G1-01. 전수조사 집계 불일치
주니어 보고:
- 전체 66개 파일 전수조사
- CORE 18
- RESUME 6
- BIZPLAN 21
- MIXED 0

합계는 45개로, 21개 파일이 집계에서 누락되었다. 따라서 전수조사 완료로 인정하지 않는다.

### G1-02. 테스트 baseline 인터프리터 불일치
지시사항은 Python 3.11이었으나 Python 3.12로 실행되었다.
또한 `docx`, `lxml`, `fitz`, `openai`, `matplotlib` 등 필수 의존성 미설치로 100개 collection error가 발생했다.
이는 코드 baseline이 아니라 환경 불완전 상태이므로 유효한 회귀 기준으로 사용할 수 없다.

### G1-03. 조사 산출물 원격 미반영
`docs/repo-split/docx-duplicate-map.md`가 로컬에는 생성되었다고 보고되었으나 PM 원격 브랜치에는 존재하지 않았다.
PM 검증 가능한 상태가 아니므로 Gate 통과 불가.

### G1-04. ownership 오분류 표본 발견
PM spot review 결과:

- `cross_form_autofill.py`: 사업계획서 양식 전사 엔진이지만 `resume_extract.py`가 `rank_source_pool`을 재사용한다. **MIXED_REFACTOR 후보**.
- `render_service.py`: 범용 TemplateProfile/ProjectInput 기반 DOCX 렌더링과 PSST 전용 옵션이 한 파일에 같이 있다. **MIXED_REFACTOR 후보**.
- `defect_classifier.py`: acceptance/self-improvement 계층이며 사업계획서 전용이 아니다. **CORE 후보**.
- `quality_rules.py`: 사업계획서 규칙 프리셋이 명확하므로 **BIZPLAN 후보**.

따라서 MIXED=0 판정은 승인하지 않는다.

## 2. 분류체계 보완

모든 파일을 억지로 CORE/RESUME/BIZPLAN에 넣지 않는다.

### ownership
- `CORE`: 두 도메인에서 재사용 가능한 런타임 기능
- `RESUME`: 이력서/컨설턴트 신청서 전용
- `BIZPLAN`: 사업계획서/지원사업/PSST 전용
- `MIXED`: 한 파일에 공통+도메인 책임이 혼재
- `NONE`: 런타임 도메인 소유권이 없는 파일

### file_role
- `SERVICE`
- `CLI`
- `TEST`
- `PACKAGE_META`
- `TOOLING`
- `CASE_SCRIPT`

이 두 축을 별도로 기록한다.

예:
- `scripts/docx2hwp.py` → ownership=CORE, file_role=TOOLING, proposed_action=KEEP_SCRIPT
- `scripts/run_document_quality_harness.py` → ownership=CORE, file_role=TOOLING, proposed_action=KEEP_SCRIPT
- `scripts/extract_doc_data.py` → ownership=NONE, file_role=CASE_SCRIPT, proposed_action=KEEP_LEGACY_OR_SALVAGE

## 3. 환경 관련 PM 결정

지금은 venv 생성 또는 패키지 설치를 승인하지 않는다.
먼저 Python 설치/패키지 상태만 조사한다.

필수 확인:
```powershell
py -0p
Test-Path "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"
& "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe" --version
& "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe" -m pip --version
& "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe" -m pip show pytest python-docx lxml PyMuPDF openai matplotlib
```

Python 3.11이 없거나 실행 불가하면 설치하지 말고 보고한다.
Python 3.11은 있으나 패키지가 부족해도 설치하지 말고 보고한다.

## 4. 다음 Gate 통과 조건

다음 조건을 모두 충족해야 T1.1 폴더 재편을 승인한다.

1. `docx-duplicate-map.md`에 66개 파일이 정확히 66행 존재
2. ownership 집계 합계가 66과 일치
3. file_role 집계 합계가 66과 일치
4. MIXED 후보가 실제 의존성 근거와 함께 재검토됨
5. Python 3.11 환경 인벤토리 완료
6. 산출물 commit/push 완료
7. 기존 파일 이동/삭제/import 변경 없음
8. PM이 원격 브랜치에서 산출물을 직접 검증 가능

## 5. 현재 금지사항

Gate 1 승인 전 아래를 하지 않는다.
- 기존 파일 이동/삭제
- `app/resume`, `app/bizplan` 본격 재편
- import 경로 변경
- compatibility wrapper 구현
- 패키지 설치
- 테스트 실패 수정
- master 직접 push
