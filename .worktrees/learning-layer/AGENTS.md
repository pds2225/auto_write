# AGENTS.md — auto_write 에이전트 협업 규약

> AI 에이전트(Claude Code / Codex 등)가 `D:\auto_write` 에서 작업할 때의 규약.
> 상세 작업 지침은 `CLAUDE.md`, 하네스 설계는 `HARNESS_TEAM_DESIGN.md` 참조.

## 1. 작업 환경

- OS: Windows 11 / PowerShell. 경로는 `D:\auto_write\...` 형식.
- Python: 시스템 Python 3.11~3.13 (venv 없음). `app/` 이 import 기준(`from auto_write...`).
- 패키지 설치 Python 예: `C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe`
  (또는 `launch.bat`/`check_env.bat` 가 자동탐색).
- AI 키 없이도 하네스는 결정론적으로 동작.

## 2. 문서 품질 하네스 에이전트 (6)

> 2026-06-07 슬림화: 기존 12종을 책임·코드모듈 기준으로 6종에 병합. 상세 설계는 `HARNESS_TEAM_DESIGN.md`, 트리거·목록은 `CLAUDE.md` 참조.

| 에이전트 | 역할 | 주요 코드 | 구 에이전트 |
|----------|------|-----------|-------------|
| doc-architect | 파이프라인 설계·단계 조율 | document_quality_orchestrator | document-architect |
| doc-safety-guard | 원본 백업·롤백 + Secret/.env·위험 차단 게이트 | backup_original/rollback, (보안 게이트) | backup-rollback-agent + security-agent |
| doc-analyzer | 유형 9종 분류 + PSST 4영역 검사 + 인포그래픽 제안 (읽기 전용) | classify_text, check_psst, suggest_images | document-type-classifier + psst-review-agent + infographic-suggestion-agent |
| doc-postprocessor | 안내문구 삭제 + 서식 정규화(글머리표·표·빈문단·글자크기) + 핵심문장 강조 (DOCX 변형) | doc_quality_ops.run_all | template-cleanup-agent + formatting-normalizer + content-emphasis-agent |
| doc-quality-gate | 100점 채점·85점 게이트·보완 트리거 + 회귀·비훼손 검수 | score_document, pytest | quality-gate-agent + qa-document-agent |
| doc-writer | 사용법·리포트·HANDOFF 문서화 | report 생성 | documentation-agent |

> 실행 순서: doc-architect → doc-safety-guard(백업) → doc-analyzer → doc-postprocessor → doc-quality-gate(미달 시 보완 루프) → doc-safety-guard(실패 시 복구) → doc-writer.

## 3. 실행 방법

```powershell
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx"     # 전체
python _build_chochang.py inspect "결과.docx"                   # 진단
python -m pytest tests/test_document_quality_harness.py -q       # 테스트
```

## 4. 최종 보고 형식

작업 후 다음을 반드시 보고(추상 표현 금지, 실제 경로/명령 포함):
확인한 파일 · 생성/수정한 파일 · 실행한 테스트와 결과 · 품질점수 · 백업 경로 ·
남은 문제 · 수동 확인 필요사항 · 다음 실행 방법.

## 5. 금지

원본 덮어쓰기 · 백업 없는 수정 · Secret/API Key/.env 출력 · 유료 API 무단 호출 ·
기존 정상 기능 삭제 · results/templates 원본 삭제 · 테스트 없이 커밋 · 실패의 성공 보고 ·
글로벌 `D:\.claude` 무단 대체.

---

**변경 이력**

| 날짜 | 변경 내용 | 사유 |
|------|----------|------|
| 2026-06-05 | 문서 품질 하네스 에이전트 12종 규약 신규 | 하네스 초기 구축 |
| 2026-06-07 | §2 에이전트 표 12→6 동기화 | 실제 `.claude/agents/` 슬림화(12→6)와 본 규약 불일치 해소 |
