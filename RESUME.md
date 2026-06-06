# RESUME.md — 세션 재시작 시 이어하기 진입점

> **새 세션을 시작하면 이 파일을 가장 먼저 읽어라.** auto_write 문서 품질 하네스 작업의
> 진행 상태·남은 일·재개 명령이 여기 있다. (최종 갱신: 2026-06-06)

## 0. 30초 컨텍스트

`D:\auto_write` 에 **문서 품질 개선 하네스**를 구축했다. 완성된 DOCX(사업계획서 등)를
백업→유형분류→결정론 후처리→PSST→이미지제안→100점 채점→게이트→리포트하는 파이프라인.
**코드·테스트·문서 모두 완성·검증 완료** 상태이며, 남은 것은 "실제 문서 검증"과 "git 결정"뿐이다.

## 1. 빠른 재개 (복붙용)

```powershell
# 패키지가 설치된 Python (시스템 Python, venv 없음)
$py = "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"

# (A) 하네스 정상 동작 재확인 — 전체 테스트
$env:PYTHONPATH = 'D:\auto_write\app'
& $py -m pytest D:\auto_write\app\tests -q        # 기대: 72 passed

# (B) 실제 문서로 품질 개선 실행
cd D:\auto_write\app
& $py document_quality_orchestrator.py "C:\제출\사업계획서.docx"
# 결과: results\ 에 개선 DOCX + 리포트(md/json), results\backup\ 에 원본 백업
```

## 2. 완료된 작업 ✅

- [x] 현황 감사 + 도메인 분석 (`HARNESS_AUDIT.md`, `AUTO_WRITE_DOMAIN_MAP.md`)
- [x] 코드 6모듈 (`app/auto_write/services/`): doc_quality_ops, document_type_classifier,
      psst_check, infographic_suggest, doc_quality_score, document_quality_orchestrator
- [x] 진입점 2 (`app/document_quality_orchestrator.py`, `scripts/run_document_quality_harness.py`)
- [x] 회귀 테스트 (`app/tests/test_document_quality_harness.py`) — **전체 72 passed**
- [x] CLI 인코딩 버그(cp949/em dash) 수정·재검증
- [x] end-to-end 드라이런 — 사업계획서 91.6점/우수/게이트 통과
- [x] 에이전트 12 (`.claude/agents/`), 스킬 12 (`.claude/skills/`, 허브 1+세부 11)
- [x] 커맨드 6 (`.claude/commands/`), 워크플로 1 (`.claude/workflows/`)
- [x] 규칙/설계 문서 5 + CLAUDE.md + AGENTS.md + HANDOFF.md + PROJECT_REPORT.md

## 3. 남은 작업 ⬜ (다음 세션에서 이어서)

- [ ] **실제 제출용 사업계획서 1건으로 검증** — `document_quality_orchestrator.py "<실제경로>"` 실행 후
      `results/*_quality_report_*.md` 를 열어 **안내문구 오삭제·과잉 강조** 여부 점검. 오탐 발견 시:
      - 안내문구 오삭제 → `app/auto_write/services/doc_quality_ops.py` 의 `_PURE_GUIDE_RE`(보수적 패턴) 조정
      - 과잉 강조 → `emphasize_key_sentences` 의 `_EMPHASIS_KEYWORDS`/`require_numeric`/`max_emphasis` 조정
      - 수정 후 반드시 `python -m pytest tests/test_document_quality_harness.py -q` 회귀
- [ ] **git 결정** — `D:\auto_write` 는 git 저장소 아님(.git 없음). 커밋 원하면:
      `git init` → `.gitignore` 정비(results/outputs/workspace/*.zip/별도 번들 제외 확인) → add → commit.
      (현재 커밋 보류 중. 사용자 승인 필요)
- [ ] (선택) 새 문서유형/PSST 항목 확장 시: `document_type_classifier.py`의 `_SIGNATURES`,
      `psst_check.py`의 `_PSST_ITEMS` 에 추가 + 테스트 케이스 추가.

## 4. 핵심 파일 인덱스 (어디에 뭐가 있나)

| 알고 싶은 것 | 파일 |
|---|---|
| 전체 진행 상태(이 문서) | `RESUME.md` |
| 인계/사용법 상세 | `HANDOFF.md` |
| 구축 결과 종합 보고 | `PROJECT_REPORT.md` |
| 코드 흐름·기존 구조 | `AUTO_WRITE_DOMAIN_MAP.md` |
| 감사 결과(git/위험/중복) | `HARNESS_AUDIT.md` |
| 점수 배점 규칙 | `DOCUMENT_QUALITY_SCORE_RULES.md` |
| PSST 검사 규칙 | `PSST_CHECK_RULES.md` |
| 문서유형 분류 규칙 | `DOCUMENT_TYPE_RULES.md` |
| 백업/롤백 규칙 | `BACKUP_ROLLBACK_RULES.md` |
| 팀/에이전트 설계 | `HARNESS_TEAM_DESIGN.md` |
| 트리거·에이전트·커맨드 목록 | `CLAUDE.md` |

## 5. 검증된 사실 (재확인 불필요, 신뢰 가능)

- 실행 Python: `C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe` (3.11.9, python-docx 1.2.0). venv 없음.
- import 기준: `app/` 디렉토리 (`from auto_write...`). CLI는 `cd app` 후 실행하거나 scripts 래퍼 사용.
- AI 키 없어도 전 단계 결정론 동작(분류 보조만 선택적 AI).
- 게이트: 90 우수 / 85 통과 / 70 보완 / 미만 실패 (passed = 총점≥85).
- 원본 절대 덮어쓰기 금지(출력=입력이면 ValueError). 백업: `results/backup/<YYYYMMDD_HHMMSS>/`.

## 6. 재개 시 첫 행동 권장

1. 이 파일 + `HANDOFF.md` 읽기 → 2. `pytest`로 72 passed 재확인 → 3. 위 "남은 작업" 중 하나 선택해 진행.
