# HARNESS_AUDIT.md — auto_write 하네스 안전 점검·현황 감사

> 작성: 2026-06-05 / 대상: `D:\auto_write` / 목적: 문서 품질 개선 하네스 신규 구축 전 현황 감사

## 0. 진행 판단 (요약)

- **신규 구축으로 진행 가능.** `D:\auto_write\.claude` 가 존재하지 않아 기존 프로젝트 전용 하네스와 충돌 없음.
- 기존 문서 생성 파이프라인(`app/auto_write/services/`)이 견고하게 존재 → 하네스는 **신규 구현이 아니라 기존 서비스 위에 품질 후처리·검수 계층을 얹는 방식**으로 설계.
- 위험 요소: **git 미초기화**(버전관리 부재), 일부 기능 이미 부분 구현(중복 주의), 시스템 Python 의존(venv 없음).

## 1. Git 상태

- `D:\auto_write` 는 **git 저장소가 아님** (`.git` 없음, `.gitignore`만 존재).
- → 커밋/롤백을 git 으로 할 수 없음. 하네스는 자체 파일 백업(`results/backup/<ts>/`)으로 원본 보호.
- 후속 조치 필요: `git init` 여부는 사용자 결정 사항(미승인 상태에서 강제 init 안 함).

## 2. 주요 폴더 구조 (D:\auto_write)

| 경로 | 용도 |
|------|------|
| `app/` | 메인 애플리케이션 (FastAPI + 문서 생성 엔진) |
| `app/auto_write/` | 핵심 패키지 (config, models, storage, services, analysis) |
| `app/auto_write/services/` | 서비스 레이어 (docx_ops, render, qa, project, evaluation, openai_client 등) |
| `app/auto_write/analysis/` | 템플릿 분석 (docx_template.py) |
| `app/tests/` | pytest 테스트 (docx_ops, template_analysis, psst_mapping 등) |
| `app/_build_chochang.py` | 진단/빌드 CLI (analyze/generate/finalize/inspect/struct/heads) |
| `results/`, `outputs/` | 생성 결과물 |
| `workspace/` | 프로젝트별 작업 공간 (templates, projects) |
| `data/`, `backup/`, `WORKS/`, `Playground/` | 데이터·백업·작업 산출물 |
| `autowrite_repo/`, `bizplan-autofill-codex/` | 별도 번들/이전 버전 (의존성 분리) |

## 3. 기존 문서 생성 파이프라인 (추정·확인)

진입: `app/_build_chochang.py` CLI 또는 FastAPI(`auto_write.main:app`, 포트 8765).

```
analyze_uploaded_template(양식 DOCX) → TemplateProfile(sections/tables/image_slots/questions)
create_project → save_project_form(answers, references) → generate()
  → ProjectService.generate(): AI 작성(openai_client) + render_service(DOCX) + qa_service(검수) + image_service
finalize(pid): SubmittableFiller — 잔존 placeholder/가이드 채움·정리
```

핵심 서비스:
- `services/docx_ops.py` — DOCX 셀/단락 텍스트 쓰기, 색상/음영 정규화, 이미지 삽입 (검증된 헬퍼)
- `services/qa_service.py` — `build_report()`: 가이드문구·placeholder(○○○)·필수입력·표길이·미리보기 검수 (errors/warnings)
- `services/evaluation_service.py` — 공고 평가기준 파싱 + AI 채점 + 취약섹션 보완 루프
- `services/project_service.py` (1670줄) — PSST 정규식·핵심표 인식·generate 본체
- `analysis/docx_template.py` — 안내문구 탐지(`GUIDE_HINT_RE`/`FORM_GUIDE_RE`), 완성도 판정

## 4. 기존 루트 문서 (AGENTS/CLAUDE/RULES)

- `D:\auto_write\CLAUDE.md` : **없음** (신규 생성 대상)
- `D:\auto_write\AGENTS.md` : **없음** (신규 생성 대상)
- `D:\auto_write\RULES.md` : **없음**
- 참고 문서: `실행방법.md`, `ONBOARDING.md` (실행 안내), `app/requirements.txt`

## 5. 글로벌 `D:\.claude` 참고 가능 자산

| 자산 | 재사용 판정 | 사유 |
|------|------------|------|
| `agents/todolist-planner.md` | 부분참조 | 작업 분해 패턴 참고 가능, 직접 사용 안 함 |
| `agents/web-*.md` (planner/designer/implementer/qa) | 불가 | 웹 개발 전용 도메인, 문서 품질과 무관 |
| `skills/web-dev-orchestrator` | 불가 | 웹 개발 전용 |
| `skills/approval-test-github-loop` | 부분참조 | 승인→테스트 루프 패턴 참고 |

→ **글로벌 자산은 직접 재사용 없음.** 도메인이 다름(웹 개발 vs 문서 품질). 글로벌은 훼손하지 않고 보존.

## 6. auto_write 전용으로 신규 생성한 자산

- **코드 (app/auto_write/services/)**: `doc_quality_ops.py`, `document_type_classifier.py`, `psst_check.py`, `infographic_suggest.py`, `doc_quality_score.py`, `document_quality_orchestrator.py`
- **진입점**: `app/document_quality_orchestrator.py`, `scripts/run_document_quality_harness.py`
- **테스트**: `app/tests/test_document_quality_harness.py`
- **.claude/**: `agents/`(12), `skills/`(11+오케스트레이터 허브), `commands/`(6), `workflows/`(1)
- **문서**: `CLAUDE.md`, `AGENTS.md`, `HANDOFF.md`, 규칙/설계 문서 5종, `PROJECT_REPORT.md`

## 7. 중복 가능성 (기존 기능과의 관계 — 재사용 우선)

| 요청 기능 | 기존 자산 | 처리 방침 |
|-----------|----------|----------|
| 안내문구 삭제 | `docx_ops` 음영/색상, `docx_template` GUIDE_RE | **재사용 + 보강** (보수적 단락 삭제 추가) |
| 품질 검사 | `qa_service.build_report` | **재사용** (inspection 스킬이 호출) |
| 품질 점수 | `evaluation_service`(AI 채점) | **분리** — 결정론 점수(doc_quality_score)는 후처리 검수용, evaluation은 내용 채점용 (목적 다름) |
| PSST | `project_service.PSST_*_RE`(섹션 정규식) | **재사용** + 내용 충실도 검사 추가(psst_check) |
| inspect | `_build_chochang.py inspect` | **재사용** (inspection 스킬/커맨드가 호출) |
| 이미지 삽입 | `docx_ops.insert_image_*` | **재사용** (제안은 신규, 삽입은 기존) |

## 8. 위험 요소 및 대응

| 위험 | 대응 |
|------|------|
| git 미초기화 | 자체 백업(results/backup) + 원본 덮어쓰기 금지 게이트 |
| 후처리로 서식 파손 | 런 단위 텍스트 노드만 수정, 폰트 조정 기본 비활성, 보수적 삭제 |
| 안내문구 오삭제 | `_PURE_GUIDE_RE` 시작 패턴 + 길이 제한 + 표 셀 제외 |
| 기존 기능 훼손 | 회귀 테스트 72개 전부 통과로 확인 |
| Secret 노출 | AI 키 출력 금지, `.env`는 config가 로드만(값 미출력) |

## 9. 검증 결과 (감사 시점)

- 환경: Python 3.11.9 + (fastapi/python-docx 1.2.0/openai/pydantic 등) + `auto_write` import 정상.
- 베이스라인 테스트: `test_docx_ops/template_analysis/psst_mapping/config` **16 passed**.
- 신규 하네스 코드 작성 후 전체: **72 passed (13.79s)** — 회귀 없음.
