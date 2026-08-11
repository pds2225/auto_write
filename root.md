# AutoWrite 루트 폴더 정리 TASK

대상 저장소: `pds2225/auto_write`
기준 브랜치: 현재 기본 브랜치(`master`)

## 목표

루트 폴더를 **기능을 깨지 않고 최소·명확하게 정리**한다.

이번 작업은 코드 리팩터링이나 신규 기능 개발이 아니다. 목적은 루트에 흩어진 문서·스크립트·임시/과거 산출물·중복 파일을 성격에 맞는 위치로 정리하고, 루트에는 저장소 진입점에 필요한 항목만 남기는 것이다.

중요: 파일을 많이 옮기는 것이 목표가 아니다. **안전하게 옮길 수 있다고 증명된 것만 정리**한다.

---

## 0. 시작 전 안전 점검

먼저 아래를 확인한다.

```bash
git fetch --all --prune
git status
git branch --show-current
git rev-parse HEAD
git rev-parse origin/master
git log --oneline -10
git worktree list
```

그리고 다음 원칙을 지킨다.

- 기존 미커밋 변경을 덮어쓰지 않는다.
- 다른 worktree/세션이 같은 파일을 수정 중이면 충돌 가능성을 먼저 확인한다.
- `git reset --hard`, `git clean -fd`, force push 금지.
- `git add -A` 금지. 이번 작업 파일만 명시적으로 stage한다.
- 사용자 데이터, 실사용 산출물, 비밀정보를 삭제하지 않는다.
- 파일 이동은 가능하면 `git mv`를 사용한다.

현재 `origin/master`가 시작 시점과 달라졌다면 최신 상태를 기준으로 다시 조사한다.

---

## 1. 루트 전수조사

루트의 **모든 파일과 1단계 디렉터리**를 빠짐없이 조사한다.

각 항목을 아래 중 하나로 분류한다.

1. `KEEP_ROOT` — 루트에 있어야 하는 저장소 핵심 파일
2. `SOURCE` — 실행 코드/패키지
3. `DOC` — 설계·정책·감사·handoff·작업보고 문서
4. `SCRIPT` — 운영/개발/검증용 스크립트
5. `TEST` — 테스트/fixture
6. `CONFIG` — 도구/빌드/CI 설정
7. `DATA` — 실제 코드가 참조하는 데이터
8. `GENERATED` — 생성 산출물·캐시·임시파일
9. `ARCHIVE` — 과거 작업/날짜 폴더/더 이상 활성 경로가 아닌 자료
10. `DUPLICATE` — 동일/대체 파일이 존재
11. `UNKNOWN` — 근거 없이 이동하면 안 되는 항목

표를 만든다.

| 현재 경로 | 종류 | 실제 역할 | 참조처 | 최근 사용 근거 | 제안 위치 | 조치 | 위험도 |
|---|---|---|---|---|---|---|---|

위험도는 `LOW / MEDIUM / HIGH`로 표시한다.

파일명만 보고 판단하지 말고 실제 내용을 읽고, 저장소 전체 참조를 검색한다.

---

## 2. 반드시 먼저 읽을 핵심 파일

최소 다음 파일/폴더를 확인하고 그 지시를 우선한다.

- `README*`
- `CLAUDE.md`
- `AGENTS.md`
- `.claude/`
- `.github/`
- `AUTO_WRITE_DOMAIN_MAP.md`
- `DOCUMENT_TYPE_RULES.md`
- `DOCUMENT_QUALITY_SCORE_RULES.md`
- `BACKUP_ROLLBACK_RULES.md`
- `HANDOFF.md`
- `app/`
- `tests/` 또는 `app/tests/`
- 빌드/패키징 파일(`pyproject.toml`, `requirements*.txt`, `package*.json` 등이 존재하면)

이 문서나 설정에서 **루트 고정 경로를 요구하는 파일은 이동하지 않는다.**

---

## 3. 루트에 기본적으로 남길 항목

실제 저장소를 확인해 조정하되, 일반적으로 아래 종류는 루트 유지 후보로 본다.

- `.gitignore`, `.gitattributes`
- `.github/`, `.claude/`
- `README*`
- `LICENSE*`
- `CLAUDE.md`
- `AGENTS.md`
- 패키지/빌드/의존성 설정 파일
- 애플리케이션 핵심 디렉터리(`app/` 등)
- 표준 테스트 디렉터리
- 실제 배포/실행에서 루트 위치가 계약인 파일

**“깔끔해 보인다”는 이유만으로 핵심 파일을 `docs/` 아래로 옮기지 않는다.**

---

## 4. 문서 정리 원칙

루트에 흩어진 설계·감사·리팩터링·품질·handoff 문서를 전수 확인한다.

루트 고정이 필요하지 않은 문서는 `docs/` 아래 성격별로 정리하는 방안을 우선 검토한다.

권장 예시:

```text
docs/
  architecture/
  rules/
  audits/
  refactor/
  operations/
  handoff/
  archive/
```

단 기존 `docs/` 구조가 이미 있다면 **새 분류 체계를 중복 생성하지 말고 기존 관례에 맞춘다.**

문서를 이동하면 다음도 반드시 갱신한다.

- Markdown 링크
- CLAUDE/AGENTS/README 참조
- Python/CLI에서 읽는 경로
- 테스트 fixture 경로
- `.claude` skill/command의 파일 경로
- CI/workflow 경로

---

## 5. 날짜명·과거 작업 폴더 처리

예: `YYYYMMDD` 형태의 루트 폴더나 과거 작업 디렉터리가 있더라도 바로 archive/delete하지 않는다.

반드시 확인:

1. 현재 코드가 참조하는가
2. 테스트가 참조하는가
3. 문서/스킬/CLI가 참조하는가
4. 실제 사용자 데이터인가
5. 유일본인가
6. Git history에서 왜 추가됐는가

활성 참조가 없고 과거 보관용임이 명확한 경우에만 현재 저장소 관례에 맞는 `archive/` 또는 `docs/archive/` 등으로 이동한다.

판단 불가면 그대로 두고 `UNKNOWN`으로 보고한다.

**삭제보다 보존·이동을 우선한다.**

---

## 6. 스크립트·유틸 정리

루트의 `.py`, `.ps1`, `.bat`, `.sh`, `.js` 등 실행 스크립트를 조사한다.

루트가 진입점 계약이 아닌 개발/관리 스크립트라면 기존 구조에 맞춰 `scripts/`, `tools/`, `devtools/` 중 하나로 수렴시킨다.

단 임의로 `scripts/`와 `tools/`를 동시에 새로 만들지 않는다.

스크립트 이동 시 다음을 갱신한다.

- README 명령
- PowerShell/Bash 호출
- GitHub Actions
- subprocess 호출
- tests
- `.claude` commands/skills
- scheduled task 관련 문서

---

## 7. 중복·좀비 파일

비슷한 이름의 파일이나 구버전(`*_old`, `*_v2`, `copy`, `backup`, 날짜 접미사 등)을 발견하면 내용과 참조를 비교한다.

분류:

- canonical
- compatibility wrapper
- historical archive
- genuine duplicate
- unknown

삭제 조건은 매우 엄격하게 한다.

삭제 허용은 다음이 모두 성립할 때만:

- 저장소 전체 참조 0
- 실행/테스트 참조 0
- 다른 파일이 기능을 완전히 대체
- 사용자 데이터 아님
- Git으로 복구 가능
- 현재 작업과 무관한 미커밋 변경 없음

하나라도 불확실하면 삭제하지 않는다.

---

## 8. 이동 전 참조검사

파일 또는 폴더를 이동하기 직전에 정확한 기존 경로를 저장소 전체에서 검색한다.

검색 대상:

- Python imports
- 문자열 경로
- subprocess
- PowerShell/Bash
- YAML/JSON/TOML
- GitHub Actions
- Markdown
- `.claude/`
- tests/fixtures
- packaging 설정

**검색 결과를 확인하기 전에 이동하지 않는다.**

---

## 9. import와 package 구조는 이번 작업에서 과도하게 건드리지 않는다

이번 목표는 루트 정리다.

따라서 다음은 원칙적으로 금지한다.

- 대규모 Python package 재설계
- business_plan / consultant_application 도메인 재리팩터링
- CORE 구조 재설계
- LRule 로직 변경
- 신규 기능 개발
- API/CLI 의미 변경

단 파일 이동으로 인해 깨진 import/path를 복구하는 최소 수정은 허용한다.

---

## 10. 목표 루트 형태

실제 repo를 보고 최종안을 결정하되, 이상적인 결과는 아래처럼 **루트 항목 수가 적고 역할이 명확한 상태**다.

```text
/
├─ .claude/
├─ .github/
├─ app/
├─ docs/
├─ tests/                 # 실제 구조가 app/tests면 억지 이동 금지
├─ scripts/ or tools/     # 실제 필요할 때만
├─ README.md
├─ CLAUDE.md
├─ AGENTS.md
├─ pyproject.toml / requirements* 등 실제 설정
├─ .gitignore
└─ 기타 루트 고정이 필요한 최소 파일
```

위 tree를 기계적으로 맞추지 않는다.

`KEEP_ROOT` 근거가 있는 파일은 남긴다.

---

## 11. 단계별 실행

### Phase A — Audit

- 루트 전수분류
- 참조지도 작성
- 이동/유지/보류 목록 작성
- 테스트 baseline 측정

이 단계에서는 삭제 금지.

### Phase B — LOW RISK 정리

먼저 다음만 처리:

- 참조 없는 일반 문서
- 명확한 archive 자료
- 명확한 개발용 스크립트
- generated/temporary 파일 중 Git 추적이 부적절한 것

각 작은 묶음마다 테스트.

### Phase C — MEDIUM RISK 정리

- 참조 경로 업데이트가 필요한 문서/스크립트
- compatibility가 필요한 이동

한 번에 대량 이동하지 않는다.

### Phase D — 검증

- 전체 경로 grep
- dangling path 0 확인
- import smoke test
- CLI smoke test
- 관련 pytest
- 가능한 전체 regression

---

## 12. 테스트

최소 다음을 검증한다.

1. Python import smoke test
2. 주요 CLI `--help` 또는 무해한 smoke test
3. 문서 경로를 읽는 코드 정상
4. `.claude` skill/command dangling path 없음
5. GitHub workflow dangling path 없음
6. business_plan 관련 기존 테스트
7. consultant_application 관련 기존 테스트
8. LRule/architecture 관련 기존 테스트
9. 가능한 `app/tests/` 전체 regression

테스트 실패를 삭제/skip으로 숨기지 않는다.

기존 baseline failure와 신규 regression을 구분한다.

---

## 13. 완료 전 루트 재감사

정리 후 다시 루트 전체를 나열하고 각 항목에 대해 설명 가능해야 한다.

최종적으로 확인:

- 이유 없는 루트 문서 최소화
- 날짜/임시 폴더 정리 또는 보류 사유 존재
- dangling reference 0
- broken import 0
- broken CLI path 0
- 중복 정본 0
- 사용자 데이터 손실 0
- unrelated 변경 0

---

## 14. Git 전략

루트 정리 전용 브랜치를 사용한다.

예:

`refactor/root-cleanup`

커밋은 의미 단위로 나눈다.

예:

- `chore(root): organize documentation`
- `chore(root): move maintenance scripts`
- `docs: update paths after root cleanup`

각 커밋 전 관련 테스트를 실행한다.

PR 생성 후 diff를 다시 확인한다.

자동 병합은 다음이 모두 맞을 때만 가능:

- merge conflict 없음
- unrelated 변경 없음
- 사용자 데이터 삭제 없음
- 참조 경로 검증 PASS
- 관련 테스트 PASS
- 신규 regression 0

불확실하면 PR까지만 만들고 병합하지 않는다.

---

## 15. 절대 금지

- 파일명만 보고 대량 삭제
- 루트가 지저분하다는 이유로 무조건 `docs/` 이동
- import/경로 검색 없이 이동
- 사용자 산출물 삭제
- Git history를 복구수단으로 핑계 삼아 위험한 삭제
- 기존 domain 구조 재설계
- 신규 기능 개발
- unrelated formatting
- `git add -A`
- `git reset --hard`
- `git clean -fd`
- force push

---

## 16. 최종 보고 형식

```text
[RESULT]
PASS / PARTIAL / BLOCKED

[BEFORE]
root entries:
files:
directories:

[AFTER]
root entries:
files:
directories:

[MOVED]
old -> new

[KEPT ROOT]
path : reason

[ARCHIVED]
path -> destination : reason

[DELETED]
없으면 NONE
삭제했다면 각 항목별 근거

[REFERENCES UPDATED]
목록

[TEST]
passed:
failed:
skipped:
baseline-only failures:

[BLOCKED / UNKNOWN]
판단 불가하여 그대로 둔 항목

[COMMITS]
SHA + message

[PR]
number:
state:
merged:

[REMAINING]
없으면 NONE
```

---

## 핵심 원칙

이번 작업의 성공 기준은 **루트 파일 수를 무조건 줄이는 것**이 아니다.

성공 기준은:

> 모든 루트 항목에 명확한 존재 이유가 있고, 옮긴 파일은 모든 참조가 함께 갱신되며, 기존 AutoWrite의 사업계획서·컨설턴트 신청서·LRule·CLI·테스트 동작이 그대로 유지되는 상태

이다.

먼저 실측하고, 확실한 것만 이동하고, 매 단계 테스트하며 진행해라.
