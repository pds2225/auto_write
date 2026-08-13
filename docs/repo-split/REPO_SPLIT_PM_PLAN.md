# REPO_SPLIT_PM_PLAN.md — auto_write 저장소 분리 PM 실행계획

> PM 관리 문서. 작업자는 이 문서의 순서·승인 게이트를 임의로 건너뛰지 않는다.
> 기준 브랜치: `refactor/repo-split-pm`
> 목표 구조: 같은 저장소 내 `app/core/`, `app/resume/`, `app/bizplan/`

## 0. PM 결론

현재 `app/core/docx/`는 **정식 이동 완료 상태가 아니다.** 기존 파일을 삭제하지 않고 복사해 둔 **staging/중복 소스 상태**다.

따라서 현재 작업 상태는 다음처럼 정정한다.

| Task | 기존 표시 | PM 판정 | 이유 |
|---|---|---|---|
| T1 DOCX 관련 파일 분류 및 app/core/docx/로 이동 | 완료처럼 취급 | **진행중 / staging 완료** | 원본이 남아 있어 source of truth가 2개임 |
| T2 DOCX 관련 파일 분류 및 이동 계획 수립 | 미완료 표시 | **1차 완료, 재검증 필요** | 파일명 기준 분류가 섞여 있고 domain ownership 검증이 부족함 |
| T1.1 폴더 구조 재편(core/resume/bizplan) | 미완료 | **다음 핵심 단계** | 소유권 확정 후 진행해야 함 |
| T1.2 import 경로 수정 및 테스트 검증 | 미완료 | **T1.1 이후** | 이동 전에 import를 먼저 바꾸면 혼선 발생 |

## 1. 절대 규칙

1. **파일 삭제 금지.** PM 승인 전 기존 정상 파일 제거 금지.
2. **master 직접 push 금지.** 모든 변경은 `refactor/repo-split-pm` 또는 그 하위 작업 브랜치에서 수행.
3. **한 번에 대규모 이동 금지.** 기능군 1개씩 이동 → import 수정 → 테스트 → 커밋.
4. **테스트 없이 커밋 금지.** 최소 import smoke test + 해당 기능군 테스트 수행.
5. **복사본과 원본을 동시에 수정 금지.** 정식 source of truth 전환 전에는 기존 `app/auto_write/...`가 기준.
6. **DOCX라는 파일명만 보고 core로 분류하지 말 것.** 실제 사용 도메인과 의존성으로 분류.
7. **resume 전용 코드가 core/docx 안에 들어가 있으면 core로 확정하지 말 것.** 예: `resume_fill_service.py`, `resume_fill.py`는 재분류 후보.
8. **bizplan 전용 코드가 core/docx 안에 들어가 있으면 core로 확정하지 말 것.** 예: `psst_fill.py`는 사업계획서 전용 여부를 의존성으로 판단.
9. **rollback 가능 상태 유지.** 각 커밋은 독립적으로 revert 가능해야 함.
10. **작업 종료 시 HANDOFF/본 문서 갱신.** 다음 AI가 현재 상태를 추측하지 않도록 한다.

## 2. 목표 구조

```text
app/
├─ core/
│  ├─ document/             # 문서 공통 I/O·변환·렌더·품질
│  ├─ extraction/           # 회사/문서 공통 추출
│  ├─ ai/                   # 공통 AI provider/client
│  ├─ storage/              # 공통 저장/설정
│  └─ ...
├─ resume/
│  ├─ cli/
│  ├─ services/
│  └─ tests/
├─ bizplan/
│  ├─ cli/
│  ├─ services/
│  ├─ injector/
│  └─ tests/
└─ auto_write/              # 전환 완료 전까지 legacy compatibility layer
```

> `app/core/docx/` 명칭은 임시 staging 폴더로 본다. 최종 core 구조가 꼭 `core/docx`일 필요는 없다.

## 3. 소유권 분류 기준

### CORE
다음 조건을 모두 만족하면 core 후보.
- 이력서와 사업계획서에서 모두 사용 가능
- 특정 PSST/이력서 문항 구조를 전제로 하지 않음
- DOCX/HWPX/HWP 변환, 공통 텍스트 추출, 공통 렌더/품질, 저장/설정 등 인프라 역할

### RESUME
다음 중 하나면 resume 후보.
- 컨설턴트 신청서/이력서 필드명 또는 경력/학력/자격 구조에 강하게 결합
- 진입점이나 서비스 이름이 resume 전용
- 사업계획서 없이도 독립적으로 사용되는 이력서 작성 플로우

### BIZPLAN
다음 중 하나면 bizplan 후보.
- PSST, 공고문, 평가기준, 사업계획서 문항, 지원사업 양식에 결합
- injector, bizplan_autopilot, announcement analyzer 등 사업계획서 작성 파이프라인
- 사업계획서 전용 차트/이미지/근거/평가 루프

### MIXED
- core와 도메인 코드가 한 파일에 섞여 있으면 바로 이동하지 않는다.
- 먼저 함수/클래스 단위 분리 설계안을 작성하고 PM 승인 후 분할한다.

## 4. 주니어 개발자 작업 순서

### Phase A — 현황 고정

#### A-1. Git 상태 확인
실행:
```powershell
cd C:\Users\ekth3\auto_write
git status
git branch --show-current
git fetch origin
git log --oneline --decorate -10
```
합격 기준:
- 작업 브랜치가 `refactor/repo-split-pm`
- 예상치 못한 uncommitted change 없음
- 원격 master와 기준점 확인

#### A-2. 현재 중복 목록 작성
복사된 `app/core/docx/**` 각각에 대해 원본 경로를 1:1 매핑한다.

산출물: `docs/repo-split/docx-duplicate-map.md`

필수 열:
| staged_path | original_path | identical? | imported_by | imports | ownership | action |

`action` 값은 아래 4개만 사용:
- KEEP_CORE
- MOVE_RESUME
- MOVE_BIZPLAN
- MIXED_REFACTOR

#### A-3. import graph 조사
다음 문자열을 전역 검색:
```text
from auto_write
import auto_write
resume_fill
bizplan
psst
injector
hwp_docx_convert
docx_ops
cross_form_autofill
```

단순 grep 결과 개수만 보고하지 말고 **실제 호출 관계**를 위 매핑표에 적는다.

### Phase B — 분류 승인

#### B-1. 먼저 명백한 전용 파일만 분류
우선 검토 대상 예시:
- `resume_fill.py` → RESUME 후보
- `resume_fill_service.py` → RESUME 후보
- `bizplan_autopilot.py` → BIZPLAN 후보
- `bizplan_ai_writer.py` → BIZPLAN 후보
- `psst_fill.py` → BIZPLAN 후보
- `docx_ops.py` → CORE 후보
- `hwp_docx_convert.py` → CORE 후보
- `doc_text_extract.py` → CORE 후보

주의: 예시는 결론이 아니라 후보. import graph로 검증한다.

#### B-2. PM 승인 게이트 1
다음 정보를 제출하기 전 실제 이동 금지.
- CORE/RESUME/BIZPLAN/MIXED 파일 수
- MIXED 파일 목록
- cyclic import 예상 목록
- CLI entrypoint 변화 목록
- 테스트 영향 목록

### Phase C — 폴더 골격 생성

승인 후 다음만 먼저 생성:
```text
app/core/
app/resume/
app/resume/services/
app/resume/cli/
app/resume/tests/
app/bizplan/
app/bizplan/services/
app/bizplan/cli/
app/bizplan/injector/
app/bizplan/tests/
```

이 단계에서는 기존 파일 이동 금지. `__init__.py`와 README 성격의 설명 파일만 추가.

테스트:
```powershell
$env:PYTHONPATH='C:\Users\ekth3\auto_write\app'
python -c "import core; import resume; import bizplan; print('package-ok')"
```

커밋 예:
```text
refactor(split): add target package skeleton
```

### Phase D — CORE부터 전환

가장 의존성이 낮고 공통성이 높은 모듈부터 1개 기능군씩 전환한다.

권장 순서:
1. 문서 변환/텍스트 추출
2. DOCX primitive ops
3. 공통 품질/렌더 도구
4. 공통 config/storage/model 의존성

각 기능군별 순서:
1. 신규 위치에 정식 파일 배치
2. 신규 import path를 사용하는 테스트 1개 추가/수정
3. legacy path는 즉시 삭제하지 않고 compatibility re-export 여부 검토
4. 해당 테스트 실행
5. 전체 smoke test 실행
6. 커밋

### Phase E — RESUME 전환

1. resume CLI
2. resume service
3. resume extract/fill tests
4. legacy entrypoint compatibility 확인

합격 기준:
- 기존 사용 명령이 깨지지 않거나 명시적 migration wrapper 제공
- resume 관련 targeted tests 100% pass

### Phase F — BIZPLAN 전환

1. bizplan CLI
2. bizplan services
3. injector
4. PSST/evaluation/image/chart 관련 전용 코드
5. 사업계획서 테스트

injector는 파일 수가 많으므로 별도 커밋군으로 처리한다.

### Phase G — import 정리

원칙:
- 새 도메인 코드는 새 경로를 직접 import
- legacy compatibility layer만 `auto_write`를 유지
- 양방향 import 금지: `core -> resume/bizplan` 금지
- `resume <-> bizplan` 직접 import 금지

허용 방향:
```text
resume  ─┐
         ├─> core
bizplan ─┘
legacy auto_write -> core/resume/bizplan (전환기 wrapper만)
```

### Phase H — 검증

#### H-1. import smoke
```powershell
$env:PYTHONPATH='C:\Users\ekth3\auto_write\app'
python -c "import auto_write; import core; import resume; import bizplan; print('imports-ok')"
```

#### H-2. targeted tests
- core 관련 테스트
- resume 관련 테스트
- bizplan 관련 테스트

#### H-3. 전체 회귀
기존 규약상 Python 3.11 사용 우선:
```powershell
$py='C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe'
$env:PYTHONPATH='C:\Users\ekth3\auto_write\app'
& $py -m pytest C:\Users\ekth3\auto_write\app\tests -q
```

주의: 과거 HANDOFF의 `202 passed`는 2026-06-12 스냅샷이므로 현재 기대 테스트 수로 사용하지 않는다. 현재 master baseline을 먼저 측정한다.

### Phase I — 중복소스 종료

이 단계 전까지 기존 파일 삭제 금지.

중복소스를 없애는 최종 방식은 둘 중 하나:
1. legacy 파일을 얇은 re-export wrapper로 변경
2. 모든 호출 전환 확인 후 legacy 파일 제거

사용자 지시가 **파일 삭제 금지**이므로 현재 프로젝트에서는 우선 1번을 기본안으로 한다.

예:
```python
# legacy compatibility wrapper
from core.document.docx_ops import *  # noqa
```

단, wildcard re-export는 최종 설계에서 명시적 export로 바꿀 수 있다.

## 5. 커밋 전략

한 커밋당 한 목적.

권장 순서:
1. `docs(split): add ownership and duplicate map`
2. `refactor(split): add package skeleton`
3. `refactor(core): move document conversion primitives`
4. `refactor(core): move docx operations`
5. `refactor(resume): isolate resume workflow`
6. `refactor(bizplan): isolate business-plan workflow`
7. `refactor(split): update imports and compatibility wrappers`
8. `test(split): complete repository split regression coverage`
9. `docs(split): finalize handoff and architecture map`

금지:
- `git add .` 후 의미 불명 대형 커밋
- 코드 이동 + 기능 변경 + 포맷팅을 한 커밋에 섞기
- 테스트 실패 상태 커밋

## 6. PM 체크포인트

### Gate 0 — baseline
- [ ] branch 확인
- [ ] git clean 확인
- [ ] 현재 전체 테스트 baseline 기록

### Gate 1 — ownership map
- [ ] 모든 staged 파일의 원본 매핑
- [ ] CORE/RESUME/BIZPLAN/MIXED 분류
- [ ] import graph 위험 표시

### Gate 2 — package skeleton
- [ ] 새 폴더 import 성공
- [ ] 기존 기능 변화 없음

### Gate 3 — core migration
- [ ] core가 resume/bizplan을 import하지 않음
- [ ] core targeted tests pass

### Gate 4 — resume migration
- [ ] resume targeted tests pass
- [ ] 기존 resume entrypoint 호환

### Gate 5 — bizplan migration
- [ ] bizplan targeted tests pass
- [ ] injector 테스트 pass

### Gate 6 — final regression
- [ ] full pytest baseline 대비 신규 실패 0
- [ ] import smoke pass
- [ ] legacy compatibility 확인
- [ ] 문서 갱신

## 7. 작업자가 매 단계 PM에게 보고할 형식

```text
[STEP]
예: A-2 중복 목록 작성

[CHANGED]
- 생성/수정 파일

[FOUND]
- 의존성/중복/위험

[TEST]
- 실행 명령
- passed/failed 개수

[DECISION NEEDED]
- PM 판단이 필요한 항목

[NEXT]
- 다음 1개 작업만
```

## 8. STOP 조건

아래 중 하나라도 발생하면 주니어는 임의 해결하지 말고 작업 중지 후 보고.

- circular import 발생
- baseline 테스트가 원인 불명으로 감소
- 동일 모듈이 core와 resume/bizplan 양쪽에서 수정되기 시작함
- CLI 실행 경로가 바뀌어 기존 자동화가 깨질 가능성
- Secret/.env/API key 관련 파일이 diff에 잡힘
- 1개 커밋 변경 파일이 30개를 초과함(순수 injector 이동 제외)
- 기존 결과물 생성 품질이 달라짐

## 9. 다음 즉시 실행할 작업

**주니어에게 지금 시킬 작업은 A-1 + A-2까지만이다. 실제 이동 금지.**

### 주니어용 실행 지시

```text
C:\Users\ekth3\auto_write 저장소 분리 작업을 수행한다.
PM 승인 전 실제 파일 이동/삭제/import 수정 금지.

1) refactor/repo-split-pm 브랜치로 전환한다.
2) git status / branch / fetch / 최근 log를 보고한다.
3) app/core/docx 아래 현재 복사본 전체를 원본 경로와 1:1 매핑한다.
4) 파일별로 imported_by, imports를 조사한다.
5) ownership을 CORE / RESUME / BIZPLAN / MIXED 중 하나로 분류한다.
6) docs/repo-split/docx-duplicate-map.md를 작성한다.
7) 코드 이동은 하지 않는다.
8) 테스트 baseline을 Python 3.11로 측정하고 결과를 기록한다.
9) 완료 후 STEP/CHANGED/FOUND/TEST/DECISION NEEDED/NEXT 형식으로 보고한다.
```

PM 승인 없이 다음 Phase로 넘어가지 않는다.
