---
name: session-closeout-all
description: >-
  로컬·클라우드·GitHub 와 Cursor/Claude/Codex 가 같은 세션 마무리 깃발을 보게 한다.
  한 창은 다른 창 대화를 저장할 수 없다. GitHub 파일로 신호를 보내고, 각 창이
  RESUME.md 를 스스로 갱신한다. 다음 요청에 사용: "세션 마무리", "전체 세션 저장",
  "session-closeout-all", "마무리 예약", "다른 AI도 저장", "클라우드에서 로컬도 마무리".
---

# session-closeout-all — 위치×AI 공통 마무리 신호

체크포인트 SSOT 는 `RESUME.md`. 방송 채널은 git 추적 파일 `.session/closeout_due.json`.

## 이 창에서 예약 (클라우드 포함)

1. `python scripts/session_closeout.py plant --from <cursor-cloud|cursor-local|claude-local|...> --note "<한 줄>"`
2. `.session/closeout_due.json` 만 커밋·푸시 (`due: true`). 기본 커밋본은 `due: false` 로 둔다.
3. `python scripts/session_closeout.py status` 로 확인.

상대 창은 `git pull` 해야 깃발을 본다.

## 세션 시작 (모든 위치·AI)

1. `git pull` (가능하면).
2. `python scripts/session_closeout.py status`
3. 로컬 Claude Code 면 `python scripts/session_closeout.py sync-disk --agent claude --location local`
4. `due: true` 이고 이 `(agent, location)` 이 acks 에 없으면 **이 창** 상태를 `RESUME.md` 에 쓰고
   `ack --agent <cursor|claude|codex> --location <local|cloud|github>` 후 커밋·푸시.
5. 다른 창 대화를 저장했다고 말하지 않는다.
6. 모든 창이 끝나면 `cancel` 후 푸시.

## 한계

다른 채팅 원문을 읽거나 저장할 수 없다. 신호만 공유한다.
