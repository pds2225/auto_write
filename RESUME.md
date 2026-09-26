# RESUME.md — 세션 재시작 시 이어하기 진입점

> 새 세션을 시작하면 이 파일을 가장 먼저 읽는다. (최종 갱신: 2026-09-26)

## 0. 30초 컨텍스트

- 현재 작업: `D:\auto_write` 주간 진행상황 검토 및 공유 문안 정리.
- 공식 기준: GitHub `origin/main`과 `TASK.md`. 개발 원장 C(있는 기능의 실사용)가 최우선.
- 사용자 선호: 진행상황 문안은 카테고리+목록형, `~했습니다` 대신 `~임` 개조식.

## 1. 빠른 재개

```powershell
git -C D:\auto_write status --short --branch
git -C D:\auto_write branch -vv
git -C D:\auto_write worktree list --porcelain
git -C D:\auto_write stash list
gh pr list --repo pds2225/auto_write --state open
```

## 2. 완료된 작업 ✅

- [x] 2026-09-21~09-26 `origin/main`, GitHub PR, TASK, worktree·stash 상태 검토.
- [x] 자동 스냅샷 제외 후 이번 주 병합 PR 7건 확인: #185, #189~#192, #194, #195.
- [x] 핵심 성과 분류: HWPX 무결성/AW-001 최종 경로, 한글 COM 창 숨김, 모바일 운영 콘솔, Render 접근 보호·저장 설정, 원장 정리.
- [x] 공유용 문안을 카테고리별 개조식으로 변경하는 사용자 요청 확인.

## 3. 남은 작업 ⬜

- [ ] `_preflight_evidence/`, stash 8개, 기존 worktree를 보존하며 로컬 checkout을 최신 `origin/main`에 안전 동기화.
- [ ] 닫힌 PR #193의 AUTO 수용 계약 AT-002/003/005/007/010을 제품 구현과 다시 연결하고 실제 통과 증거 확보.

## 4. 핵심 결정·제약

- 자동생성·채움 기본 산출은 HWPX. DOCX는 명시할 때만 사용.
- named 지원사업 신청서 작성은 TASK에 등록하지 않고 신청 원장에만 기록.
- 원본 덮어쓰기·사용자 변경 삭제·Secret 출력 금지. 실패 시 `_DRAFT` 원칙 유지.
- Render 설정은 코드 병합까지만 완료. 실제 배포는 하지 않은 상태.
- 진행상황 보고는 완료/개선/검증/남은 일/다음 주 중심의 짧은 목록형으로 작성.

## 5. 핵심 파일 인덱스

| 주제 | 파일 |
|---|---|
| 공식 작업 정본 | `D:\auto_write\TASK.md` |
| 개발 요청 원장 | `D:\auto_write\docs\REQUEST_LEDGER.md` |
| 신청 원장 | `D:\auto_write\docs\clients\user_applications.md` |
| 허브 맵 | `D:\auto_write\docs\BIZDOC_HUB_MAP.md` |

## 6. 검증된 사실

- 원격 `origin/main`: `ad2c72d` (PR #195 병합 결과).
- 이번 주 병합 PR 7건, 현재 열린 PR 0건.
- PR #191 기록: 1,831 tests collected, collection error 0, 영향 테스트 96 passed.
- 병합 PR의 docs-gate 성공 확인.
- PR #193: acceptance-auto 실패 후 닫힘. 실제 GAP은 미해결.
- 로컬 checkout: `port/pr187-mobile-console`; `_preflight_evidence/` 미추적. 로컬 `main`은 `origin/main`보다 16커밋 뒤.

## 7. 재개 시 첫 행동

1. 위 빠른 재개 명령으로 사용자 변경·stash·worktree 상태 재확인.
2. 보존 대상을 분리한 뒤 최신 `origin/main` 기반 작업 브랜치에서 AUTO 수용 테스트 재연결.
