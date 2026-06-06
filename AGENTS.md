# AGENTS.md — auto_write 에이전트 협업 규약

> AI 에이전트(Claude Code / Codex 등)가 `D:\auto_write` 에서 작업할 때의 규약.
> 상세 작업 지침은 `CLAUDE.md`, 하네스 설계는 `HARNESS_TEAM_DESIGN.md` 참조.

## 1. 작업 환경

- OS: Windows 11 / PowerShell. 경로는 `D:\auto_write\...` 형식.
- Python: 시스템 Python 3.11~3.13 (venv 없음). `app/` 이 import 기준(`from auto_write...`).
- 패키지 설치 Python 예: `C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe`
  (또는 `launch.bat`/`check_env.bat` 가 자동탐색).
- AI 키 없이도 하네스는 결정론적으로 동작.

## 2. 문서 품질 하네스 에이전트 (12)

| 에이전트 | 역할 | 주요 코드 |
|----------|------|-----------|
| document-architect | 파이프라인 설계·후처리 삽입 위치 결정 | orchestrator |
| template-cleanup-agent | 양식 안내문구·예시·음영 삭제 기준 | remove_guide_paragraphs |
| formatting-normalizer | 글머리표/표/빈문단/글자크기 정리 | doc_quality_ops |
| content-emphasis-agent | 핵심문장 Bold/Underline 강조 | emphasize_key_sentences |
| document-type-classifier | 문서 유형 9종 분류 | classify_text |
| psst-review-agent | PSST 4영역 충실도 검사 | check_psst |
| infographic-suggestion-agent | 도식/이미지 삽입 제안 | suggest_images |
| quality-gate-agent | 품질점수·85점 게이트·보완 트리거 | score_document |
| backup-rollback-agent | 원본 백업·복구·버전관리 | backup_original/rollback |
| qa-document-agent | 샘플생성·inspect·회귀테스트 | _build_chochang inspect, pytest |
| security-agent | Secret/키/.env 보호·위험차단 | (게이트) |
| documentation-agent | 사용법·리포트·HANDOFF | report 생성 |

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
