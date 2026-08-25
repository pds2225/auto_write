---
description: 지원사업 문서 단일 진입점 — 의도(분석/작성/채움/다듬기/변환/제출)를 파악해 알맞은 스킬·CLI로 라우팅한다.
argument-hint: "[의도 한 줄] 또는 파일 경로"
---

# /bizdoc

`bizdoc-hub` 스킬의 슬래시 커맨드 진입점. **기능을 새로 구현하지 않고** 골라서 이어준다.

## 절차

1. `.claude/skills/bizdoc-hub/SKILL.md` 를 읽고 그 라우팅표를 따른다.
2. 상세 맵(에이전트 vs CLI): `docs/BIZDOC_HUB_MAP.md`.
3. 모호하면 질문 **1개**로 확정한 뒤 해당 스킬/CLI 실행.
4. 끝나면 연계 흐름의 **다음 단계**를 제안한다.

## 빠른 분기

| 사용자 말 | 다음 |
|-----------|------|
| 공고/양식 분석 | `announcement-form-analysis` / `/auto-write-analyze` |
| 처음부터 작성 | `bizplan-orchestrator` / `/auto-write-bizplan` |
| 기술 출처 / 어디서 가져온거지 | `tech-framing-provenance` |
| A→B 전사·양식 채움 | `cross-form-submission` 또는 `auto_write_hub.py fill` |
| DOCX 다듬기 | `document-quality-orchestrator` / `/improve-doc-quality` |
| hwp↔docx | `docx-hwp-conversion` |
| 한글 안 열림 | `hwpx-doctor` |

개별 스킬명을 정확히 지목한 요청은 이 커맨드 없이 해당 스킬을 직접 쓴다.
