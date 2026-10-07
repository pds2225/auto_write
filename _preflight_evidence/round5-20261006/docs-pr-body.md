## 요약

다른 PC·클라우드에서 작업을 시작할 때 로컬 체크포인트만 읽어 최신 진행 상태를 놓치는 일을 막습니다. AGENTS.md와 CLAUDE.md에 `git fetch origin --prune` 후 `origin/main:TASK.md` → `origin/main:RESUME.md` 필수 확인을 명시하고, 최신 로컬 체크포인트를 공개 공유판에 반영합니다.

## 변경

- AGENTS.md·CLAUDE.md: 모든 위치·작업 브랜치에 같은 시작 순서 적용. 원격 파일 확인 전 제품 작업 착수 금지, 읽은 main SHA와 현재 상태·다음 액션 보고. TASK SSOT 유지.
- RESUME.md: 문서 PR 선병합 후 최신 main에서 Round-5 세 건 수정·draft PR까지만 진행하는 사용자 지시 기록. 기존 실제 한글 2022 실패와 테스트 집계의 한계 유지.
- 제품 코드·테스트·개인 자동화·로컬 증거·백업은 포함하지 않습니다. 기존 다른 세션의 변경과 stash는 보존합니다.

## 확인

- [x] 세 파일 UTF-8 읽기, 두 진입 문서의 필수 시작 순서, RESUME 65행 이내 및 공개 범위 확인 PASS.
- [x] `git diff --check -- AGENTS.md CLAUDE.md RESUME.md` PASS.
- [x] 변경 파일은 AGENTS.md·CLAUDE.md·RESUME.md만입니다. 문서 변경이므로 전체 pytest를 실행하지 않았습니다.
- [ ] GitHub docs-gate 통과 후 `gh pr merge --auto --merge`로 병합하고 원격 main의 공유판을 다시 조회합니다.

Round-5 제품 수정은 이 문서 PR 병합 후 별도 브랜치에서 시작하며, 해당 제품 PR은 draft로 유지합니다.
