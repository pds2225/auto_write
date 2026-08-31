---
name: user-applications-memory
description: >-
  특정지원사업은 저장하지마. 원장 씨가 제일 중요.
  원장·파일에 사업명 저장 금지
  아예 제외하라는게아니라 특정지원사업신청서 작성하는일을 task에등록하지마라고
  박다솜 지원사업 목록은 채팅으로만 답한다. Google Docs 정리본을 만들지 않는다.
  "뭐 신청했지", "아이템별로", "지원사업 목록", "스킬수확" 시 이 스킬과
  docs/clients/user_applications.md 를 연다.
triggers:
  - 뭐 신청했지
  - 아이템별로
  - 지원사업 목록
  - 정리본
  - 스킬수확
  - 특정지원사업은 저장하지마
  - task에등록하지마
---

# User applications memory

## The Insight

이 사용자는 **문서를 안 읽는다.** 신청 이력은 에이전트 메모리(`user_applications.md`)에 두고, 나중에 물으면 **채팅 한 번에** 답한다. Drive에 정리본을 만들어 주면 실패다.

2026-08-31 명확화: **사업명은 원장·파일에 저장한다.** **TASK.md LIST에 특정 지원사업 신청서 작성을 등록하지 말 것.** 개발 우선순위는 `docs/REQUEST_LEDGER.md` **C**.

## Why This Matters

2026-08-20에 신청 목록 Google Docs를 만들어 링크를 줬다. 사용자 반응: 그런 정리본은 필요 없고 안 읽으니 메모리에만 두고 나중에 물어보게 하라. 같은 실수를 반복하면 신뢰를 깎는다.

## Recognition Pattern

- "뭐 신청했지", "아이템별로", "지원사업 뭐 냈어"
- 결과를 Docs/시트/요약 파일로 남기려는 충동
- 도보네비와 마켓게이트를 한 줄로 합치려는 충동
- named 지원사업 신청서 작성을 TASK LIST에 올리려는 충동

## The Approach

1. `docs/clients/user_applications.md`를 읽는다. 없으면 Drive `제출완료`에서 다시 모으되 **날조하지 않는다.**
2. **채팅으로만** 답한다. Google Docs·시트·새 md 정리본을 만들지 않는다.
3. 네 갈래를 섞지 않는다: 내비(도보네비/케이네비) / 수출(마켓게이트) / 멘토 / 고객사.
4. 폴더명 `제출완료` ≠ 사이트 접수 확정. **선정**만 확정으로 적는다. STAR·KICXUP=내비 선정. 대구 스타전에 STAR를 수출로 적은 칸은 오류.
5. 전화·이메일·주소는 답에 넣지 않는다.
6. 절차 실행("그대로 실행")은 이 스킬이 아니라 `user-bizdoc-playbook`이다.
7. named 지원사업 **신청서 작성**을 `TASK.md` LIST에 새로 등록하지 않는다.

## Success

- 사용자가 링크를 열지 않아도 답이 끝난다.
- 내비 사실을 마켓게이트 칸에, 그 반대를 넣지 않았다.
- 새 Drive 정리본이 생기지 않았다.

## Verification

원장: `docs/clients/user_applications.md`. 개발 원장 C: `docs/REQUEST_LEDGER.md`. 내비 카드: `docs/clients/dobonevi_card.md`. 위키: [[User applications ledger]] · [[Chat not Google Docs]].
