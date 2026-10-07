# 세션 마무리 신호 (로컬 · 클라우드 · GitHub · 모든 AI)

한 창은 다른 창의 대화를 읽을 수 없다. 대신 **GitHub에 깃발을 올려** 다음에 이 저장소를 연 창이 스스로 `RESUME.md`를 갱신하게 한다.

이 클라우드 창에서 `plant` → 커밋·푸시하면, 아래 칸은 전부 같은 신호를 본다(`git pull` 후).

| 위치 \ AI | Cursor | Claude Code | Codex 등 |
|-----------|--------|-------------|----------|
| local (PC) | `AGENTS.md` 세션 시작 규칙 | JSON + `sync-disk` → `.claude/.closeout_due` 훅 | `AGENTS.md` |
| cloud (원격 에이전트) | `AGENTS.md` (이 창) | 원격 클론이 있으면 동일 | `AGENTS.md` |
| GitHub (PR/코딩에이전트) | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` |

불가능: 다른 창 대화 로그를 여기서 대신 저장하는 것. 신호만 보낸다.

| 경로 | 역할 | git |
|------|------|-----|
| `.session/closeout_due.json` | 공통 깃발 | 추적함 (`due: false` 가 기본. plant 할 때만 true) |
| `.claude/.closeout_due` | 로컬 Claude Code 훅용 | gitignore |
| `RESUME.md` | 실제 저장 내용 | 추적함 |

## 명령 (여기 클라우드에서도 동일)

```text
python scripts/session_closeout.py plant --from cursor-cloud --note "마무리 예약"
git add .session/closeout_due.json && git commit -m "chore: plant session closeout" && git push

python scripts/session_closeout.py status
python scripts/session_closeout.py sync-disk --agent claude --location local
python scripts/session_closeout.py ack --agent cursor --location cloud
python scripts/session_closeout.py cancel
```

`due: true` 이면 각 세션은 **자기 (agent, location) 이 acks에 없을 때만** `RESUME.md`를 갱신한 뒤 `ack` 하고 푸시한다. `due` 는 `cancel` 전까지 유지한다. 대화 로그를 대신 저장했다고 말하지 않는다.
