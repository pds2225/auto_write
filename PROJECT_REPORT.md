# PROJECT_REPORT.md — auto_write 문서 품질 하네스 구축 보고

> 작성: 2026-06-06 / 대상: `D:\auto_write` / 모드: Ultra Code + Team Ralph

## 전체 3줄 요약

1. `D:\auto_write` 전용 **문서 품질 개선 하네스**를 신규 구축했다 — 완성 DOCX 를 백업→유형분류→결정론 후처리→PSST→이미지제안→100점 채점→게이트→리포트하는 파이프라인.
2. 코드 6모듈 + 진입점 2 + 회귀 테스트(하네스 11) 를 작성했고 **전체 72 테스트 통과**, 합성 사업계획서로 end-to-end 드라이런 **91.6점/통과** 확인.
3. 에이전트 12 · 스킬 12(허브 1+세부 11) · 커맨드 6 · 워크플로 1 · 규칙문서 5 + CLAUDE.md/AGENTS.md/HANDOFF.md 를 생성했고, 기존 기능은 비훼손이다.

## 확인한 파일 (주요)

- `app/_build_chochang.py`(inspect/struct CLI), `app/auto_write/config.py`(경로), `services/docx_ops.py`·`qa_service.py`·`evaluation_service.py`·`project_service.py`(PSST 정규식)·`analysis/docx_template.py`(안내문구 탐지), `app/requirements.txt`, `launch.bat`·`check_env.bat`(실행환경).

## 생성한 파일

**코드 (app/auto_write/services/)**
- `doc_quality_ops.py` · `document_type_classifier.py` · `psst_check.py` · `infographic_suggest.py` · `doc_quality_score.py` · `document_quality_orchestrator.py`

**진입점·테스트**
- `app/document_quality_orchestrator.py` · `scripts/run_document_quality_harness.py` · `app/tests/test_document_quality_harness.py`

**.claude/**
- `agents/` 12개, `skills/` 11개 평면 + `skills/document-quality-orchestrator/SKILL.md`(허브), `commands/` 6개, `workflows/document-quality-harness.md`

**루트 문서**
- `HARNESS_AUDIT.md` · `AUTO_WRITE_DOMAIN_MAP.md` · `DOCUMENT_TYPE_RULES.md` · `PSST_CHECK_RULES.md` · `DOCUMENT_QUALITY_SCORE_RULES.md` · `BACKUP_ROLLBACK_RULES.md` · `HARNESS_TEAM_DESIGN.md` · `CLAUDE.md` · `AGENTS.md` · `HANDOFF.md` · `PROJECT_REPORT.md`

## 수정한 파일

- `app/document_quality_orchestrator.py` — **수정 이유**: Windows 콘솔(cp949)에서 `—`(em dash) 출력 시 `UnicodeEncodeError` 로 CLI 가 죽는 버그. **수정 내용**: main() 진입부 stdout/stderr UTF-8 reconfigure + 출력 문자열 em dash→하이픈. **검증**: 드라이런 재실행 정상(91.6점 출력).
- (기존 파일은 수정 없음 — 하네스는 신규 파일로만 추가, 기존 서비스 재사용)

## 생성한 Agent (12)

> ⚠️ 본 보고서는 2026-06-06 구축 시점 기록이다. 이후 **2026-06-07 에이전트를 12→6종으로 슬림화**했다(doc-architect, doc-safety-guard, doc-analyzer, doc-postprocessor, doc-quality-gate, doc-writer). 현재 기준 목록은 `CLAUDE.md`·`AGENTS.md`·`HARNESS_TEAM_DESIGN.md` 참조. 아래는 구축 당시 12종 원본 기록.

document-architect, template-cleanup-agent, formatting-normalizer, content-emphasis-agent, document-type-classifier, psst-review-agent, infographic-suggestion-agent, quality-gate-agent, backup-rollback-agent, qa-document-agent, security-agent, documentation-agent (전원 `model: opus`, 팀 통신 프로토콜·재호출 섹션 포함)

## 생성한 Skill (12)

허브: document-quality-orchestrator. 세부: docx-template-cleanup, bullet-spacing-normalization, paragraph-font-sizing, table-whitespace-cleanup, content-emphasis, document-type-classification, psst-structure-check, infographic-suggestion, document-quality-scoring, backup-and-rollback, document-quality-inspection

## 생성한 Workflow (1)

document-quality-harness (17단계, 병렬가능[안내문구·글머리표·표공백·이미지·PSST] / 순차필수[백업·저장·점수·테스트])

## 생성한 Command (6)

/improve-doc-quality, /auto-write-quality, /auto-write-inspect, /auto-write-psst, /auto-write-images, /auto-write-finalize

## 구현한 오케스트레이터 기능

입력검증 · 원본백업 · 유형 자동분류(9종) · 안내문구 삭제 · 글머리표/표 공백정리 · 빈문단 삭제 · 핵심문장 강조 · PSST 검사(사업계획서/발표) · 이미지 제안 · 100점 채점 · 85점 게이트 · 미달 시 보완루프(≤10, 수렴 조기종료) · 결과저장(원본 비훼손) · 리포트(md+json) · 롤백.

## 문서 품질점수 기준

100점 9항목 — 안내문구15/글머리표10/문단공백10/글자크기15/표10/강조10/유형구조15/PSST10/이미지5.
게이트: 90 우수 / 85 통과 / 70 보완 / 미만 실패.

## 백업·롤백 구조

`results/backup/<YYYYMMDD_HHMMSS>/` 자동 백업 · 출력=입력 경로 거부(ValueError) · `--rollback <dir> <target>` 복구.

## 실행한 테스트

```powershell
$py="C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"; $env:PYTHONPATH='D:\auto_write\app'
& $py -m pytest D:\auto_write\app\tests -q
& $py D:\auto_write\scripts\run_document_quality_harness.py "<합성 사업계획서>.docx"
```

## 테스트 결과

- 베이스라인(하네스 추가 전): 16 passed.
- 하네스 신규 단위/통합: 11 passed.
- **전체 회귀: 72 passed (24.0s) — 0 실패. 기존 기능 비훼손 확인.**
- 드라이런(end-to-end CLI): 유형=사업계획서(94%), 점수 91.6/100(우수), 게이트 통과, PSST 16/16, 이미지제안 4, 백업/출력/리포트 생성 정상.

## 실패 후 수정한 내용

- CLI UnicodeEncodeError(cp949/em dash) → UTF-8 reconfigure + ASCII 하이픈으로 수정 후 재검증 통과.

## 남은 문제

- git 미초기화(버전관리 없음) · 실제 사용자 DOCX 검증 미수행(합성 샘플만) · HWP/PDF 변환 후 후처리 범위 외 · 폰트 표준화 기본 비활성.

## 수동 확인 필요사항

1. 실제 제출용 사업계획서 1건으로 드라이런 후 `results/*_quality_report_*.md` 검토(안내문구 오삭제·과잉강조 여부).
2. `git init` 진행 여부 결정(현재 미초기화 → 커밋 보류 중).

## Git 상태

- `D:\auto_write` 는 **git 저장소 아님**(.git 없음). → **커밋 보류**. 커밋 원하면 `git init` 후 진행 필요(사용자 승인 대기).

## 다음 실행 방법

```powershell
cd D:\auto_write\app
& "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe" document_quality_orchestrator.py "C:\제출\사업계획서.docx"
# 결과: results\ 에 개선 DOCX + 리포트(md/json), results\backup\ 에 원본 백업
```
