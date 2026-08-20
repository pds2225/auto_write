---
name: session-resume
description: >-
  auto_write 세션을 시작·일시정지·마무리할 때 사용. RESUME.md 가 SSOT.
  CLAUDE.md 가 이 스킬을 가리키는데 파일이 없으면 안 된다.
  트리거: "이어서", "세션 재개", "세션마무리", "세션 마무리", "체크포인트 저장",
  "어디까지 했지", "RESUME", "session-resume".
  문서 작성/채움/다듬기는 bizdoc-hub. 일회성 이미지 편집은 스킬로 만들지 마라.
---

# session-resume — 세션 재개·체크포인트·마무리

> 2026-08-20 수확. 같은 날 만든 `promo-banner-localize` 는 배너 1건짜리라 철회.
> 매 세션 반복되는 것은 **RESUME 읽고 핀하고 닫는 절차**다.

## 언제 쓰나

| 사용자 말 | 모드 |
|-----------|------|
| 이어서 / 세션 재개 / 어디까지 했지 | **재개** |
| 체크포인트 저장 | **일시정지** (작업은 안 끝남) |
| 세션마무리 / 세션 마무리 | **종료** |

## 재개

1. `RESUME.md` 를 먼저 읽는다. 다음 할 일은 「재개 명령」과 「남은 일」만.
2. `git fetch origin main` 후 핀 SHA 가 원격과 같은지 본다. 로컬 main 이 스냅샷이면 한두 시간 늦을 수 있다.
3. `TASK.md` 열린 `[ ]` 만 본다. 옛 채팅을 새 일로 꺼내지 않는다.
4. 메일·양식·파일이 온 뒤에야 하는 일(STAR-Exploration IR 등)은 **파일이 없으면 시작하지 않는다.**
5. 테스트·실행은 `py -3.11`. PATH 기본 3.14 는 matplotlib 부재로 수집 에러.

## 일시정지 (체크포인트)

종료와 같게 `RESUME.md` 를 고치되, 「지금 세션」에 **막힌 지점·다음 한 줄**을 남긴다.
커밋은 코드 변경이 있을 때만. 문서만 고치면 `docs: pin … checkpoint` 한 커밋.

## 종료 (세션마무리)

`git fetch origin main` 한 뒤에 핀한다. 핀 SHA = 작업 시작 시점의 `origin/main` (이 마무리 커밋의 SHA 가 아님). 패턴: #158 이 `d6b96b8` 인데 본문은 그 전 핀 `fe4aa17` 을 가리켰다 → 이번 마무리는 현재 `origin/main` 을 핀하면 된다.

`RESUME.md` 필수 칸:

1. 최종 갱신 날짜 + 한 줄 (코드 변경 없음이면 그렇게 쓴다)
2. `origin/main` @ `<sha>` 와 열린 PR 여부
3. 「지금 세션」 — 한 일 / 안 한 일 / artifact 경로 (git 에 안 넣은 것 명시)
4. 「최근 완료」 맨 위 1행
5. 「남은 일」 우선순위. 끝난 배너 재작업을 0a 로 남기지 말 것(사용자가 원할 때만)
6. 「재개 명령」 복붙 가능한 3~6줄

그다음:

- `CLAUDE.md` 변경 이력은 **최근 5건만**. 6번째가 되면 가장 오래된 행을 `docs/CHANGELOG.md` 로 옮긴다. 옮기기 전에 CHANGELOG 에 이미 있는지 검색(중복 금지).
- PNG·DOCX 산출물은 `/opt/cursor/artifacts` 또는 로컬 results. **사용자가 저장소에 넣으라고 하기 전에 git add 금지.**
- 코드가 없으면 pytest 를 돌리지 않고 「해당 없음」이라고 쓴다. 허브 가드만 건드렸으면 `app/tests/test_hub_entrypoints.py` 만.
- Cursor 클라우드 PR 은 draft. GitHub 자동머지는 draft 에서 불가. 머지 요청이 있으면 Ready 후 `gh pr merge --auto --squash`.
- AGENTS.md §4 보고: 확인한 파일 · 생성/수정 · 테스트 · 남은 문제 · 다음 실행.

## 스킬 수확을 같이 시키면

품질 게이트 3개가 **모두** 참일 때만 스킬을 만든다.

- 5분에 구글 되는가? → 아니어야 함
- 이 저장소/이 팀 절차인가? → 예
- 이번만의 산출물(배너 1장, 문구 번역)인가? → 예면 **만들지 마라**

만들지 말 것: 홍보 이미지 한/영 변환, GenerateImage 비율 잔기술(다음에 배너를 또 안 만들면 0회), 이미 `CLAUDE.md`/`AGENTS.md` 에 있는 문장 재진술.

만들어도 되는 것: 파일이 없어서 매번 빈손이 되는 절차(`session-resume` 이 그 사례), 실측으로만 아는 게이트(`_DRAFT` ≠ 품질점수), 허브가 가리키는데 스킬 파일이 없는 것.

## 성공 기준

- [ ] 다음 세션이 `RESUME.md` 만 읽고 재개 명령을 실행할 수 있다
- [ ] 핀 SHA 가 `git fetch` 이후 `origin/main` 과 맞다
- [ ] 일회성 PNG 가 커밋되지 않았다
- [ ] `CLAUDE.md` 이력이 5건 이하이고 CHANGELOG 와 중복되지 않는다
- [ ] 「이어서」로 시작하라는 말이 「재개 명령」에 있다

## 실행 힌트 (Windows)

```powershell
cd D:\auto_write
git fetch origin main
git log -1 --oneline origin/main
# 테스트가 필요하면
cd app
py -3.11 -m pytest tests/test_hub_entrypoints.py -q
```
