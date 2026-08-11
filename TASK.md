# TASK — AutoWrite 루트 폴더 정리

대상: `pds2225/auto_write`
기준 브랜치: `master`

## 이번 작업 1개

저장소 루트 폴더를 **기능을 깨지 않고 안전하게 정리**한다.

이 작업은 신규 기능 개발이나 대규모 코드 리팩터링이 아니다. 루트에 흩어진 문서·스크립트·날짜/과거 작업 폴더·임시/생성 파일·중복 파일을 실제 참조 관계를 확인한 뒤 성격에 맞는 기존 디렉터리로 정리하고, 루트에는 저장소 진입점에 필요한 최소 항목만 남긴다.

## 시작 전

먼저 반드시 확인한다.

```bash
git fetch --all --prune
git status
git branch --show-current
git rev-parse HEAD
git rev-parse origin/master
git log --oneline -10
git worktree list
```

- 기존 미커밋 변경을 덮어쓰지 않는다.
- 다른 세션/worktree가 같은 파일을 수정 중인지 확인한다.
- `git reset --hard`, `git clean -fd`, force push, `git add -A` 금지.
- 사용자 데이터·실사용 산출물·비밀정보 삭제 금지.
- 파일 이동은 가능하면 `git mv` 사용.

## 반드시 먼저 읽기

최소 다음을 확인한다.

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
- `app/tests/` 또는 `tests/`
- 존재하는 빌드/패키징 설정 파일

루트 위치가 계약인 파일은 이동하지 않는다.

## 1. 루트 전수 감사

루트의 모든 파일과 1단계 디렉터리를 빠짐없이 조사하고 다음으로 분류한다.

- `KEEP_ROOT`
- `SOURCE`
- `DOC`
- `SCRIPT`
- `TEST`
- `CONFIG`
- `DATA`
- `GENERATED`
- `ARCHIVE`
- `DUPLICATE`
- `UNKNOWN`

파일명만 보고 판단하지 말고 실제 내용을 읽고 저장소 전체 참조를 검색한다.

내부 작업표:

| 현재 경로 | 실제 역할 | 참조처 | 분류 | 제안 위치 | 조치 | 위험도 |
|---|---|---|---|---|---|---|

위험도: `LOW / MEDIUM / HIGH`.

## 2. 루트 유지 원칙

일반적으로 다음은 루트 유지 후보다.

- `.gitignore`, `.gitattributes`
- `.github/`, `.claude/`
- `README*`
- `LICENSE*`
- `CLAUDE.md`
- `AGENTS.md`
- 패키지/빌드/의존성 설정
- 핵심 애플리케이션 디렉터리
- 루트 위치가 실행 계약인 파일
- 이 `TASK.md`

깔끔해 보인다는 이유만으로 핵심 파일을 `docs/`로 옮기지 않는다.

## 3. 문서 정리

루트의 설계·감사·리팩터링·품질·handoff·과거 작업 문서를 전수 확인한다.

루트 고정이 필요하지 않으면 **기존 `docs/` 구조를 우선 사용**한다. 새 분류 체계를 중복 생성하지 않는다.

문서 이동 시 반드시 갱신:

- Markdown 링크
- README/CLAUDE/AGENTS 참조
- Python/CLI 문자열 경로
- 테스트 fixture 경로
- `.claude` skill/command 경로
- GitHub Actions/workflow 경로

## 4. 날짜/과거 작업 폴더

`YYYYMMDD` 같은 날짜 폴더나 과거 작업 디렉터리를 바로 삭제하지 않는다.

반드시 확인:

1. 현재 코드 참조
2. 테스트 참조
3. 문서/skill/CLI 참조
4. 사용자 데이터 여부
5. 유일본 여부
6. Git history상 목적

활성 참조가 없고 과거 보관용임이 명확할 때만 기존 archive 관례에 맞춰 이동한다.

판단 불가면 그대로 두고 `UNKNOWN`으로 보고한다.

삭제보다 보존/이동 우선.

## 5. 스크립트/유틸

루트의 `.py`, `.ps1`, `.bat`, `.sh`, `.js` 등을 조사한다.

루트 진입점 계약이 아닌 개발/관리 스크립트만 기존 `scripts/`, `tools/`, `devtools/` 구조 중 **이미 쓰는 한 곳**으로 수렴시킨다.

새 `scripts/`와 `tools/`를 동시에 만들지 않는다.

이동 시 README, workflow, subprocess, tests, `.claude`, PowerShell/Bash 호출을 모두 갱신한다.

## 6. 중복/좀비 파일

`*_old`, `*_v2`, `copy`, `backup`, 날짜 접미사 등은 실제 내용과 참조를 비교해 다음으로 구분한다.

- canonical
- compatibility wrapper
- historical archive
- genuine duplicate
- unknown

삭제는 다음이 모두 성립할 때만 허용한다.

- 저장소 전체 참조 0
- 실행/테스트 참조 0
- 다른 canonical이 완전 대체
- 사용자 데이터 아님
- Git으로 복구 가능
- unrelated 미커밋 변경 없음

불확실하면 삭제 금지.

## 7. 이동 직전 참조검사

각 파일/폴더를 이동하기 **직전** 기존 경로를 저장소 전체에서 검색한다.

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

검색 결과 확인 전에 이동 금지.

## 8. 이번 작업 범위 밖

원칙적으로 금지:

- 대규모 Python package 재설계
- business_plan / consultant_application 재리팩터링
- CORE 재설계
- LRule 로직 변경
- 신규 기능 개발
- API/CLI 의미 변경

파일 이동 때문에 깨진 import/path를 복구하는 최소 수정만 허용한다.

## 9. 단계별 수행

### Phase A — Audit
- 루트 전수분류
- 참조지도
- KEEP/MOVE/ARCHIVE/UNKNOWN 결정
- 테스트 baseline
- 이 단계 삭제 금지

### Phase B — LOW RISK
- 참조 없는 일반 문서
- 명확한 archive 자료
- 명확한 개발용 스크립트
- 추적이 부적절한 generated/temporary 파일

작은 묶음마다 테스트.

### Phase C — MEDIUM RISK
- 경로 참조 업데이트가 필요한 파일
- compatibility가 필요한 이동

대량 이동 금지.

### Phase D — Validation
- dangling path 전수검색
- import smoke
- CLI smoke
- 관련 pytest
- 가능한 전체 regression

## 10. 테스트

최소 검증:

1. Python import smoke
2. 주요 CLI `--help` 또는 무해한 smoke
3. 문서 경로 읽는 코드
4. `.claude` dangling path 0
5. GitHub workflow dangling path 0
6. business_plan 기존 테스트
7. consultant_application 기존 테스트
8. LRule/architecture 기존 테스트
9. 가능한 `app/tests/` 전체 regression

실패를 삭제/skip으로 숨기지 않는다.

기존 baseline failure와 신규 regression을 구분한다.

## 11. 완료조건

정리 후 루트를 다시 전수 감사한다.

완료 기준:

- 각 루트 항목의 존재 이유 설명 가능
- 이유 없는 루트 문서 최소화
- 날짜/임시 폴더는 정리 또는 보류 근거 존재
- dangling reference 0
- broken import 0
- broken CLI path 0
- 중복 canonical 0
- 사용자 데이터 손실 0
- unrelated 변경 0
- 신규 regression 0

## 12. Git / PR

루트 정리 전용 브랜치를 사용한다. 예: `refactor/root-cleanup`.

의미 단위로 작은 commit을 만든다.

PR 생성 후 전체 diff를 재검수한다.

다음이 모두 만족될 때만 병합 가능:

- merge conflict 없음
- unrelated 변경 없음
- 사용자 데이터 삭제 없음
- 참조 경로 검증 PASS
- 관련 테스트 PASS
- 신규 regression 0

불확실하면 PR까지만 만들고 병합하지 않는다.

## 13. 최종 보고

작업이 끝나면 아래 형식으로만 보고한다.

```text
[RESULT]
PASS / PARTIAL / BLOCKED

[ROOT BEFORE]
항목 수 및 주요 문제

[MOVED]
기존 → 신규

[KEPT ROOT]
경로 + 유지 이유

[ARCHIVED]
경로 + 근거

[DELETED]
경로 + 삭제 근거

[UNKNOWN / NOT MOVED]
경로 + 보류 이유

[REFERENCE UPDATES]
수정한 참조

[TEST]
passed:
failed:
skipped:
baseline-only failures:

[COMMITS]
sha + message

[PR]
번호:
상태:
병합 여부:

[REMAINING]
없으면 NONE
```

## 14. 절대 원칙

목표는 파일을 많이 옮기는 것이 아니라 **안전하고 이해하기 쉬운 루트**를 만드는 것이다.

확신이 없으면 이동하지 않는다.

이번 `TASK.md`에 적힌 작업 1개만 수행하고 결과를 보고한 뒤 멈춘다.
