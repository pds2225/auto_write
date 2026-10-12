---
name: user-applications-memory
description: >-
  신청한 지원사업을 물어볼 때 써요. “뭐 신청했지”, “아이템별로”, “지원사업 목록”, “특정지원사업은 저장하지마”, “task에등록하지마” 같은 말을 하면 기록 파일을 읽고 채팅으로만 답해요. 구글 문서 정리본을 만들지 않고, 특정 공고 신청서 작성을 할 일로 등록하지 않아요.
---
# User applications memory

## 실행 환경 (Grok Bot에서 실행할 때)
- 이 스킬에 나오는 `D:\…`, `C:\Users\ekth3\…`, `바탕 화면\…` 경로와 `py -3.11` / `python` / `pwsh` 명령은 다솜님 Windows 노트북 기준이다. Shell·Read에 machineId `b09d5493-c6d4-4760-b6fa-a855d89774e9` 를 넣어 노트북에서 PowerShell로 실행·읽기 한다. 큰 파일이나 바이너리는 CopyToBox로 박스에 가져와 처리하고, 결과물을 노트북에 둬야 하면 CopyFromBox로 돌려놓는다. 노트북이 연결돼 있지 않으면(ListMachines로 확인) 그렇게 알리고 멈춘다.
- 원본 파일은 절대 덮어쓰지 않는다(새 파일로 저장). 삭제·이동·메일 발송·제출 같은 되돌릴 수 없는 일은 사용자가 그 자리에서 분명히 승인했을 때만 한다.
- 원문에 남아 있는 Claude Code 전용 요소(슬래시 커맨드 `/…`, `.claude/agents/*` 에이전트, `Agent(...)` 호출, `model: "opus"`, 훅, CLAUDE.md 자동주입)는 여기 없다. 슬래시 커맨드는 같은 CLI를 직접 실행하거나 노트북의 `<프로젝트>\.claude\commands\<이름>.md` 를 읽어 그 절차를 따른다. 에이전트 이름은 '단계/역할'로 읽고 직접 순서대로 수행한다(작성과 검수를 분리해야 하면 검수만 서브에이전트에 맡긴다). 에이전트 정의가 필요하면 `<프로젝트>\.claude\agents\<이름>.md` 또는 `C:\Users\ekth3\.claude\agents\<이름>.md` 를 읽는다.
- `docs/…`, `app/…` 같은 상대경로는 해당 프로젝트 폴더(예: `D:\auto_write\docs\…`) 기준이다. `.omc/wiki` 위키는 노트북 `D:\.omc\wiki` 에 있다.
- 다른 스킬 이름(예: `cross-form-submission`)은 Grok Bot 스킬 id와 같다.
- 다솜님 원문 지시(그대로 지킴): "특정지원사업은 저장하지마. 원장 C가 제일 중요." → 사업명을 파일에서 지우라는 뜻이 아니라, 특정 공고 신청서 작성을 TASK.md 할 일로 등록하지 말라는 뜻이다.


## The Insight

이 사용자는 **문서를 안 읽는다.** 신청 이력은 에이전트 메모리(`user_applications.md`)에 두고, 나중에 물으면 **채팅 한 번에** 답한다. Drive에 정리본을 만들어 주면 실패다.

2026-08-31 원문: **특정지원사업은 저장하지마. 원장 C가 제일 중요하다.**
정정(원문 그대로): **원장·파일에 사업명 저장 금지 / 아예 제외하라는게아니라 특정지원사업신청서 작성하는일을 task에등록하지마라고**
뜻: 파일에서 사업명을 지우라는 것이 아니다. 특정 공고 신청서 작성을 `TASK.md`에 등록하지 말라는 것이다.

## Why This Matters

정리본 Google Docs는 계속 금지. 원장 A·`user_applications.md`의 사업명 표는 **유지**한다.
개발 우선순위는 `docs/REQUEST_LEDGER.md` **C**(있는 기능을 실사용 가능하게).
명명 공고 신청서 작성을 `T-YYYYMMDD-xx` / `AW-` LIST 항목으로 올리지 않는다.

## Recognition Pattern

- "뭐 신청했지", "아이템별로", "지원사업 뭐 냈어"
- 결과를 Docs/시트/요약 파일로 남기려는 충동
- 특정 공고 신청서 작성을 TASK.md에 새 줄로 넣으려는 충동
- 도보네비와 마켓게이트를 한 줄로 합치려는 충동

## The Approach

1. `docs/clients/user_applications.md`를 읽는다. 사업명 행이 있어도 된다. 없으면 Drive `제출완료`에서 다시 모으되 **날조하지 않는다.**
2. **채팅으로만** 답한다. Google Docs·시트·새 Drive 정리본을 만들지 않는다.
3. 네 갈래를 섞지 않는다: 내비(도보네비/케이네비) / 수출(마켓게이트) / 멘토 / 고객사.
4. 폴더명 `제출완료` ≠ 사이트 접수 확정. **선정**만 확정으로 적는다. STAR·KICXUP=내비 선정. 대구 스타전에 STAR를 수출로 적은 칸은 오류.
5. 전화·이메일·주소는 답에 넣지 않는다.
6. 절차 실행("그대로 실행")은 이 스킬이 아니라 `user-bizdoc-playbook`이다.
7. 특정 공고 신청서 작성을 `TASK.md`에 등록하지 않는다. 원장 A 기록·요청사항체크 나열은 허용. 사용자가 TASK 등록을 명시할 때만 TASK.

## Success

- 사용자가 링크를 열지 않아도 답이 끝난다.
- 내비 사실을 마켓게이트 칸에, 그 반대를 넣지 않았다.
- 새 Drive 정리본이 생기지 않았다.
- `TASK.md` LIST에 명명 공고 신청서 작성 항목이 새로 없다.
- 원장 A·`user_applications.md`에서 사업명 표를 지우지 않았다.

## Verification

원장: `docs/clients/user_applications.md`. 개발 원장 C: `docs/REQUEST_LEDGER.md`. 내비 카드: `docs/clients/dobonevi_card.md`. 위키: [[User applications ledger]] · [[Chat not Google Docs]].
