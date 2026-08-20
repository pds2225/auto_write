# BIZDOC_HUB_MAP — 지원사업 문서 진입점 단일 맵

> 작성: 2026-08-11 · 목적: 스킬·커맨드·CLI가 많아 헷갈리는 문제를 **표 한 장**으로 해소.
> 기존 스킬/CLI를 삭제하지 않는다. **입구만 통일**하고 나머지는 라우팅한다.

---

## 1. 두 개의 "허브" — 역할이 다르다 (중복 아님)

| 허브 | 대상 | 역할 | 대표 명령 |
|------|------|------|-----------|
| **bizdoc-hub** (에이전트 스킬) | Claude/Cursor 에이전트 | 의도 파악 → 기존 스킬·CLI로 **라우팅** | `/bizdoc` 또는 스킬 `bizdoc-hub` |
| **auto_write_hub.py** (CLI) | 사람·스크립트·다른 PC | 환경점검·진단·HWPX 채움 **실행** | `py -3.11 app/auto_write_hub.py …` |

둘 다 "단일 진입점"이지만 계층이 다르다: **에이전트는 bizdoc-hub → (필요 시) auto_write_hub CLI**.

---

## 2. 의도 → 담당 (라우팅표)

| 의도 | 에이전트(스킬/커맨드) | CLI (사람이 직접) |
|------|----------------------|-------------------|
| 뭘 해야 할지 모름 / "문서 도와줘" | **bizdoc-hub** `/bizdoc` | — (먼저 의도 확정) |
| 공고·양식 분석 | `announcement-form-analysis` · `/auto-write-analyze` | `py -3.11 app/analyze_docs.py …` |
| 처음부터 본문 작성 | **bizplan-orchestrator** · `/auto-write-bizplan` | `py -3.11 app/bizplan_autopilot.py …` |
| 완성본 A → 빈 양식 B 전사 | `cross-form-submission` | `py -3.11 app/cross_form_fill.py …` |
| HWPX 직접 채움(변환 없음) | (hub가 CLI로 안내) | `py -3.11 app/hwp_fill_direct.py …` |
| 채움+검수+제출 판정 | (hub가 CLI로 안내) | `py -3.11 app/hwpx_submit.py …` 또는 `auto_write_hub.py fill …` |
| 완성 DOCX 다듬기·품질 | `document-quality-orchestrator` · `/improve-doc-quality` | `py -3.11 app/document_quality_orchestrator.py …` |
| 무인 품질+이미지+PSST+게이트 | `/auto-write-autopilot` | `py -3.11 app/auto_write_autopilot.py …` |
| HWP↔DOCX 변환 | `docx-hwp-conversion` | `py -3.11 app/hwp_docx.py …` |
| 한글 파일 안 열림 | `hwpx-doctor` | `py -3.11 app/hwpx_doctor.py …` |
| 제출 가능성 진단만 | — | `py -3.11 app/self_diagnose.py …` 또는 `auto_write_hub.py diagnose …` |
| JSON→DOCX 주입(구 autowrite) | — | `tools/injector/inject.py` / `run.sh` |
| 이력서 L규칙 | `resume-l-rules` | `py -3.11 app/lrule_gate.py …` |
| 일러스트 스토리보드 → PPT (IR/피치덱 시안) | **`ir-storyboard-pptx`** · Skywork + `docs/KNEVI_KICKXUP_SKYWORK_PROMPT.md` | Cursor python-pptx 카드덱 금지. 원본 이미지 첨부 |
| GitHub에서 저장소 받기 | — | `git clone https://github.com/pds2225/auto_write.git D:\auto_write` / `clone.bat` / `py -3.11 app/clone_repo.py --dest …` |
| 로컬 PC 리모트 컨트롤 | — | PC에서 `remote_control.bat` 더블클릭. `py -3.11 app/local_pc_remote.py --dest D:\auto_write --start` |

---

## 3. 품질 하네스 — 세부 스킬 vs 오케스트레이터

세부 스킬(글머리표·표공백·강조 등)은 **직접 호출도 가능**하지만, 보통은 오케스트레이터 한 번이면 된다.

| 권장 | 세부(부분 재실행용) |
|------|---------------------|
| `document-quality-orchestrator` / `/improve-doc-quality` | `docx-template-cleanup`, `bullet-spacing-normalization`, `paragraph-font-sizing`, `table-whitespace-cleanup`, `content-emphasis`, `document-type-classification`, `psst-structure-check`, `infographic-suggestion`, `document-quality-scoring`, `backup-and-rollback`, `document-quality-inspection` |

부분 진단·적용 커맨드: `/auto-write-inspect` · `/auto-write-psst` · `/auto-write-images`.

---

## 4. 아카이브됨 — 다시 만들지 말 것

| 죽은 이름 | 대신 쓸 것 | 근거 |
|-----------|------------|------|
| `/auto-write-quality` | `/improve-doc-quality` | 2026-07-16 통폐합 |
| `/auto-write-finalize` | `/auto-write-autopilot` | 2026-07-16 통폐합 |

가드 테스트: `app/tests/test_archived_commands_not_resurrected.py`.

---

## 5. 연계 흐름

```
공고·양식 분석 → bizplan(본문) → 값 채움(기업정보/cross-form/hwpx) → 품질·검수 → 제출본
```

- fail 결함 1개라도 있으면 출력명 `_DRAFT` (제출 금지).
- 이미지: NotebookLM 프롬프트 삽입(직접 생성 기본 금지).
- 테스트: `py -3.11`.

---

## 6. 구 레포

`pds2225/autowrite` → 자산은 `tools/injector/`. 원격은 archived · 삭제는 owner 수동.
상세: `docs/REPO_DUPLICATION_CHECK.md`.
