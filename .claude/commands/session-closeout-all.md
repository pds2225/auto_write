---
description: 로컬·클라우드·GitHub × 모든 AI에 세션 마무리 깃발을 심거나 상태를 확인한다.
argument-hint: "plant|status|ack|cancel"
---

# /session-closeout-all

`.claude/skills/session-closeout-all/SKILL.md` 를 읽고 `scripts/session_closeout.py` 를 실행한다.

| 인자 | 할 일 |
|------|--------|
| (없음) 또는 plant | `plant --from` 이 창 → `closeout_due.json` 커밋·푸시 |
| status | `status` 출력 |
| ack | 이 창 `RESUME.md` 갱신 후 `ack` · 푸시 |
| cancel | `due: false` 로 끄고 푸시 |

상세 표: `.session/README.md`.
