# MiMo 야간 자동개발 시작 지시

작업 저장소: `C:\Users\ekth3\auto_write`
작업 브랜치: `refactor/repo-split-pm`

## 실행 지시

1. 먼저 현재 저장소에서 아래를 실행한다.

```powershell
cd C:\Users\ekth3\auto_write
git fetch origin
git switch refactor/repo-split-pm
```

2. 원격의 야간 자동개발 Runbook을 반드시 처음부터 끝까지 읽는다.

```powershell
git show origin/refactor/repo-split-pm:docs/repo-split/OVERNIGHT_AUTODEV.md
```

3. `docs/repo-split/OVERNIGHT_AUTODEV.md`의 지시를 그대로 수행한다.

- 중간 승인 질문 없이 가능한 범위까지 계속 진행한다.
- 단계별로 작은 commit을 남긴다.
- 각 단계마다 테스트를 실행하고 결과를 기록한다.
- 작업 브랜치는 `refactor/repo-split-pm`만 사용한다.
- `master` 직접 수정/push 금지.
- merge 금지.
- force push 금지.
- 기존 파일 영구 삭제 금지.
- 위험하거나 판단 불가능한 항목은 삭제/추측하지 말고 보존하며 보고서에 기록한다.

4. 마지막에는 반드시 다음 파일을 작성한다.

`docs/repo-split/OVERNIGHT_REPORT.md`

보고서에는 최소한 다음을 포함한다.

- 수행한 단계
- 변경 파일
- commit 목록
- 테스트 명령과 결과
- 실패/미해결 항목
- rollback 기준 commit
- 아침 PM 검수가 필요한 사항

5. 작업 결과를 `refactor/repo-split-pm` 브랜치에 push한다.

6. push 후 종료한다. `master`에는 병합하지 않는다.
