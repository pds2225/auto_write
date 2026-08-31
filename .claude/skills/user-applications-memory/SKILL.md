---
name: user-applications-memory
description: >-
  특정지원사업은 저장하지마. 원장 씨가 제일 중요.
  박다솜 지원사업 목록은 채팅으로만 답한다. Google Docs 정리본을 만들지 않는다.
  사업명 표를 원장·이 파일에 다시 저장하지 않는다.
  "뭐 신청했지", "아이템별로", "지원사업 목록", "스킬수확" 시 이 스킬을 연다.
---

# User applications memory

## The Insight

이 사용자는 **문서를 안 읽는다.** 2026-08-20에 신청 목록 Google Docs를 만들면 실패.
2026-08-31: **특정 지원사업은 저장하지 마라. 원장 C가 제일 중요하다.**

## Why This Matters

정리본 Docs도, 원장 A 사업명 표도 저장이 된다. 사용자는 그걸 원하지 않는다.
개발 우선순위는 `docs/REQUEST_LEDGER.md` **C**(있는 기능을 실사용 가능하게).

## Recognition Pattern

- "뭐 신청했지", "아이템별로", "지원사업 뭐 냈어"
- 결과를 Docs/시트/원장 A 행으로 남기려는 충동
- 요청사항체크에서 특정 공고 상태를 표로 쌓으려는 충동

## The Approach

1. `docs/clients/user_applications.md`는 **저장 금지 안내**다. 사업명 행을 추가하지 않는다.
2. **채팅으로만** 답한다. 답한 내용을 파일에 다시 적지 않는다.
3. Google Docs·시트·새 md 정리본을 만들지 않는다.
4. `docs/REQUEST_LEDGER.md` 에 특정 공고 행을 만들지 않는다. C를 먼저 본다.
5. 전화·이메일·주소는 답에 넣지 않는다.
6. 절차 실행은 `user-bizdoc-playbook`. 채움 사실은 `docs/clients/dobonevi_card.md`.

## Success

- 사용자가 링크를 열지 않아도 답이 끝난다.
- 원장·user_applications.md에 새 사업명 행이 없다.
- 새 Drive 정리본이 생기지 않았다.
