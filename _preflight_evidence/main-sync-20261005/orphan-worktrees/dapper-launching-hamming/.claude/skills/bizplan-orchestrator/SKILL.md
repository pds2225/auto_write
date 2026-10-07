---
name: bizplan-orchestrator
description: >-
  초안/메모 DOCX를 제출에 가까운 사업계획서로 끌어올리는 작성 오케스트레이터.
  AI 근거명시 본문 작성 → 품질 오토파일럿 → 공고 채점 → 목표 충족까지 반복.
  다음 요청 시 반드시 사용: "사업계획서 작성", "처음부터 작성", "본문 써줘",
  "PSST 채워줘", "초안을 제출본으로", "bizplan", "/auto-write-bizplan".
  ※ 완성본 A의 사실을 빈 양식 B로 옮기는 것은 cross-form-submission,
  완성 DOCX 서식만 다듬는 것은 document-quality-orchestrator.
  의도가 불분명하면 bizdoc-hub 로 라우팅.
---

# bizplan-orchestrator — 사업계획서 본문 작성

> CLAUDE.md / bizdoc-hub 가 가리키는 **작성 단계** 스킬.
> 구현 본체는 기존 CLI·커맨드에 있다(이 스킬은 라우팅·경계만 고정).

## 실행

```powershell
cd D:\auto_write\app
py -3.11 bizplan_autopilot.py "<초안.docx>" --brief-file 브리프.txt --announcement-file 공고.txt
# 또는 Claude 커맨드: /auto-write-bizplan
```

상세 옵션·안전 원칙: `.claude/commands/auto-write-bizplan.md`.

## 파이프라인 (요약)

1. AI 본문 작성/보강 — PSST 약점 영역. 무출처 수치는 `[확인필요]` (날조 0).
2. 품질 오토파일럿 — 서식 + 이미지(NotebookLM 프롬프트) + PSST 가이드 + 점수 게이트.
3. 공고 채점 — 목표 충족률까지 약점 보완 루프.
4. 수용검사 — fail 시 출력명 `_DRAFT` 강제.

## 경계

| 이 스킬 | 다른 스킬 |
|---------|-----------|
| 서술 문장을 **새로** 씀 | `cross-form-submission` = 사실만 전사 |
| 초안→제출 직전본 | `document-quality-orchestrator` = 완성본 서식만 |
| 의도 불명 | `bizdoc-hub` |

## 불변

원본 백업 · 출력≠입력 · 날조 0 · `_DRAFT` = 제출 금지 · 테스트 `py -3.11`.
공고 맞춤 기술 문장(GPS→GNSS/KPS 등)은 보유·이전이 아님 — IR 단정 금지(`tech-framing-provenance`).
