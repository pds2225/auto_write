---
name: document-quality-orchestrator
description: >-
  다 쓴 사업계획서·보고서(워드)를 제출 전에 다듬을 때 써요. “사업계획서 다듬어줘”, “보고서 정리해줘”, “양식 안내문구 삭제”, “글머리표 공백 정리”, “PSST 검사”, “품질점수 산정”, “문서 최종검수” 같은 말을 하면 서식을 정리하고 핵심 문장을 강조한 뒤 100점 점수를 매겨요. 원본은 백업해 둬요.
---
# 문서 품질 개선 하네스 오케스트레이터

## 실행 환경 (Grok Bot에서 실행할 때)
- 이 스킬에 나오는 `D:\…`, `C:\Users\ekth3\…`, `바탕 화면\…` 경로와 `py -3.11` / `python` / `pwsh` 명령은 다솜님 Windows 노트북 기준이다. Shell·Read에 machineId `b09d5493-c6d4-4760-b6fa-a855d89774e9` 를 넣어 노트북에서 PowerShell로 실행·읽기 한다. 큰 파일이나 바이너리는 CopyToBox로 박스에 가져와 처리하고, 결과물을 노트북에 둬야 하면 CopyFromBox로 돌려놓는다. 노트북이 연결돼 있지 않으면(ListMachines로 확인) 그렇게 알리고 멈춘다.
- 원본 파일은 절대 덮어쓰지 않는다(새 파일로 저장). 삭제·이동·메일 발송·제출 같은 되돌릴 수 없는 일은 사용자가 그 자리에서 분명히 승인했을 때만 한다.
- 원문에 남아 있는 Codex 전용 요소(슬래시 커맨드 `/…`, `.Codex/agents/*` 에이전트, `Agent(...)` 호출, `model: "opus"`, 훅, AGENTS.md 자동주입)는 여기 없다. 슬래시 커맨드는 같은 CLI를 직접 실행하거나 노트북의 `<프로젝트>\.Codex\commands\<이름>.md` 를 읽어 그 절차를 따른다. 에이전트 이름은 '단계/역할'로 읽고 직접 순서대로 수행한다(작성과 검수를 분리해야 하면 검수만 서브에이전트에 맡긴다). 에이전트 정의가 필요하면 `<프로젝트>\.Codex\agents\<이름>.md` 또는 `C:\Users\ekth3\.Codex\agents\<이름>.md` 를 읽는다.
- `docs/…`, `app/…` 같은 상대경로는 해당 프로젝트 폴더(예: `D:\auto_write\docs\…`) 기준이다. `.omc/wiki` 위키는 노트북 `D:\.omc\wiki` 에 있다.
- 다른 스킬 이름(예: `cross-form-submission`)은 Grok Bot 스킬 id와 같다.


완성된 DOCX 를 입력받아 **백업 → 유형분류 → 결정론적 후처리 → PSST/구조검사 → 이미지 제안 →
품질점수 → 게이트 → 보완루프 → 저장 → 리포트** 를 한 번에 수행한다. 전 과정은 AI 키 없이
결정론적으로 동작하며(분류 보조만 선택적 AI), 원본은 절대 덮어쓰지 않는다.

## 실행 모드: 에이전트 팀 (Team Ralph)

2명 이상이 협업하므로 에이전트 팀이 기본값이다. 단일 문서 1회 처리는 오케스트레이터 코드
(`DocumentQualityOrchestrator.run()`)가 전 단계를 단일 호출로 끝내므로, 팀은 **설계·검수·보완
의사결정이 필요한 경우**(예: 게이트 미달 반복, 새 문서유형 추가)에 구성한다.

데이터 흐름 (에이전트 6개, 2026-06-07 슬림화):
```
[입력단] HWP/HWPX 입력 시 → DOCX 변환 (doc-architect 가 변환 시점 결정,
          doc-safety-guard 가 원본 HWP 보존) ─ hwp_docx_convert.convert / docx-hwp-conversion 스킬
  → doc-architect (파이프라인 설계·조율)
  → doc-safety-guard (원본 백업 · 출력≠입력 확인 · 보안 게이트)
  → doc-analyzer (유형 분류 → PSST 심사[사업계획서/발표자료] → 인포그래픽 제안)
  → doc-postprocessor (안내문구 삭제 · 서식 정규화 · 핵심문장 강조)
  → doc-quality-gate (점수·85점 게이트 → 미달 시 doc-postprocessor 재작업 루프 → 회귀·비훼손 검수)
  → doc-safety-guard (게이트 실패/오류 시 백업본 복구)
  → doc-writer (리포트·핸드오프)
[출력단] HWP 제출이 필요하면 → 최종 DOCX → HWP 변환 (doc-architect 결정,
          한글 COM 대화형 PC 전용 · COM 부재 시 ok=False+안내) ─ docx-hwp-conversion 스킬
```
> HWP/HWPX 는 엔진이 직접 다루지 못하므로, 입력이 한글이면 먼저 DOCX 로 변환해 파이프라인에
> 태우고, 제출 산출물로 HWP 가 필요하면 마지막에 DOCX→HWP 로 되돌린다. 두 변환 모두 원본을
> 덮어쓰지 않는다(`docx-hwp-conversion` 스킬 / `hwp_docx_convert.convert`).

## Phase 0: 컨텍스트 확인 (항상 먼저)

1. 입력 DOCX 경로가 주어졌는가? 없으면 사용자에게 요청.
2. `results/` 에 이전 품질 리포트가 있는가?
   - 있고 **부분 수정 요청**(예: "강조만 다시", "PSST만") → 해당 단계 커맨드만 재실행
     (`/auto-write-psst`, `/auto-write-images`, `/auto-write-inspect`).
   - 있고 **새 입력 문서** → 새 실행(이전 리포트 보존, 타임스탬프로 구분).
   - 없으면 → 초기 실행(전체 파이프라인).

## 표준 실행 (PowerShell)

```powershell
cd D:\auto_write\app
# 전체 품질 개선 1회
python document_quality_orchestrator.py "C:\경로\문서.docx"
# 출력 지정 + 밑줄 강조
python document_quality_orchestrator.py 문서.docx --output 결과.docx --underline
# 진단만(후처리 없이)
python _build_chochang.py inspect "결과.docx"
# 롤백
python document_quality_orchestrator.py --rollback "..\results\backup\<ts>" 결과.docx
# HWP↔DOCX 변환 (입력 한글이면 먼저 DOCX 로 / 제출이 HWP 면 마지막에 HWP 로 — docx-hwp-conversion 스킬)
python hwp_docx.py 양식.hwp                  # 한글 양식 → DOCX(작업용)
python hwp_docx.py 결과.docx -o 제출.hwp      # 완성 DOCX → 제출용 HWP(한글 COM 필요)
```

또는 래퍼: `python D:\auto_write\scripts\run_document_quality_harness.py "문서.docx"`

## 단계별 담당 (커맨드 ↔ 에이전트 ↔ 코드)

> 표의 `/…` 커맨드는 노트북 Codex 전용이다. 여기서는 오른쪽 "코드" 열의 함수를 쓰는 CLI(`document_quality_orchestrator.py`, `_build_chochang.py inspect` 등)를 노트북에서 직접 실행하거나, 이 스킬 폴더 `references/` 의 해당 단계 설명서를 따른다.

| 단계 | 커맨드 | 에이전트 | 코드 |
|------|--------|----------|------|
| HWP↔DOCX 변환 | (자동/필요시) | doc-architect+doc-safety-guard | `hwp_docx_convert.convert` / docx-hwp-conversion 스킬 |
| 전체 실행 | `/improve-doc-quality` | doc-architect | `DocumentQualityOrchestrator.run` |
| 백업·보안 | (자동) | doc-safety-guard | 백업(`results/backup/<ts>`) + 원본 보호·보안 게이트 |
| 유형 분류 | (자동) | doc-analyzer | `classify_text/classify_docx` |
| 안내문구 삭제 | (자동) | doc-postprocessor | `remove_guide_paragraphs` |
| 서식 정리 | (자동) | doc-postprocessor | `normalize_bullet_spacing`/`cleanup_table_whitespace`/`remove_empty_paragraphs` |
| 강조 | (자동) | doc-postprocessor | `emphasize_key_sentences` |
| PSST | `/auto-write-psst` | doc-analyzer | `check_psst` |
| 이미지 제안 | `/auto-write-images` | doc-analyzer | `suggest_images` |
| 점수·게이트 | `/improve-doc-quality` | doc-quality-gate | `score_document` |
| 검수 | `/auto-write-inspect` | doc-quality-gate | `_build_chochang inspect` + `qa_service.build_report` |
| 무인 최종 | `/auto-write-autopilot` | doc-writer | autopilot + 수용검사 게이트 |

> 구 `/auto-write-quality`·`/auto-write-finalize` 는 2026-07-16 아카이브. 입구 맵: `docs/BIZDOC_HUB_MAP.md`.

## 품질 게이트

- 90↑ 우수 / 85↑ 통과 / 70↑ 보완 필요 / 70 미만 실패. `passed = 총점 >= 85`.
- 미달 시 최대 2회 보완 루프(2회차에 밑줄 강조 보강). 점수 변화 0.5 미만이면 수렴 → 조기 종료.
  2회 후에도 미달이면 조기 종료하고 잔존 결함을 **수동 확인 항목**(NEEDS_MANUAL_REVIEW)으로
  리포트에 명시한다(거짓 통과 보고 금지, 같은 방식 재반복 금지).

## 에러 핸들링

- 입력 DOCX 없음/확장자 오류 → 즉시 중단, 명확한 메시지.
- 출력 경로 = 입력 경로 → `ValueError`(원본 보호). 다른 경로로 안내.
- 후처리 중 예외 → 원본은 백업에 보존됨. 롤백 명령 안내.
- AI 분류 실패 → 규칙기반 결과 유지(중단 안 함).

## 테스트 시나리오

- **정상 흐름**: 사업계획서 DOCX → `business_plan` 분류 → 후처리 → PSST 100% → 점수 90+ → 통과 → 리포트 생성.
- **에러 흐름**: 출력=입력 경로 → `ValueError` → 사용자에게 다른 출력 경로 안내.
- 회귀: `cd app; python -m pytest tests/test_document_quality_harness.py -q` (11 통과 기대).

## 금지

원본 덮어쓰기, 백업 없는 수정, Secret/.env 출력, 유료 API 무단 호출, 실패의 성공 보고, 기존 생성 기능 삭제.

## 세부 단계 설명서 (같은 폴더 references/)
각 단계의 상세 규칙은 이 스킬 폴더의 `references/*.md` 에 있다(원래 `D:\auto_write\.Codex\skills\*.md`): backup-and-rollback, document-type-classification, docx-template-cleanup, bullet-spacing-normalization, table-whitespace-cleanup, paragraph-font-sizing, content-emphasis, psst-structure-check, infographic-suggestion, document-quality-scoring, document-quality-inspection. 해당 단계만 다시 해 달라는 요청이면 그 파일을 읽고 그 단계만 실행한다.
