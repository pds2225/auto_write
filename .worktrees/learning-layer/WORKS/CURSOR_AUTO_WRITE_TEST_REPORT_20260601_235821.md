# Cursor auto_write 서브에이전트 집중 테스트 보고서

- 실행 일시: 2026-06-01 23:58
- 실행자: Cursor
- 대상 레포: d:/auto_write
- 연동 레포: d:/v_up (오케스트레이터 라우팅 확인)
- Python (기본 PATH): 3.14.5 — **의존성 대부분 미설치**
- Python (권장, launch.bat 우선 탐색): 3.11.9 (`%LocalAppData%\Programs\Python\Python311\python.exe`) — **docx/openai/pypdf 등 설치됨, fastapi·unhwp 누락**

## 사전 맥락 (AGENTS.md auto_write 관련)

| 일시 | 요약 |
|---|---|
| 2026-05-20 | 케이스A 이전, 경쟁사 다중 스니펫, max_tokens 8192, evaluation_service + `/evaluate` 계열 |
| 2026-05-21 | requirements.txt `python-multipart` 추가, pytest 50 passed (WSL/Hermes 기록) |

## 0. 의존성 점검 (설치하지 않음)

| 패키지 | Python 3.14 (PATH 기본) | Python 3.11 (권장) |
|---|---|---|
| fastapi | **없음** | **없음** |
| uvicorn | 있음 | 있음 |
| openai | **없음** | 있음 |
| python-docx | **없음** | 있음 |
| jinja2 | 있음 | 있음 |
| httpx | 있음 | 있음 |
| pydantic | 있음 | 있음 |
| pypdf | **없음** | 있음 |
| unhwp | **없음** | **없음** |
| python-multipart | 있음 | 있음 |

**권장 조치:** `D:\auto_write\app`에서 Python 3.11로 `pip install -r requirements.txt` (특히 `fastapi`, `unhwp`).

---

## 1. pytest 결과 (스킬 단위)

실행: `PYTHONPATH=D:\auto_write\app` + `Python311\python.exe -m pytest`

| 테스트 파일 | 결과 | 소요시간 | 실패 시 상세 |
|---|---|---|---|
| test_docx_ops.py | **PASS** | 1s | 2 passed |
| test_document_ingest.py | **PASS** | 2.9s | 7 passed |
| test_project_service_safety.py | **FAIL** | 6.2s | 1 failed, 17 passed — `test_generate_inserts_section_when_anchor_has_no_blank_paragraph`: `AssertionError: 2 != 0` (generate 시 errors=2) |
| test_autofill.py | **PASS** | 0.8s | 2 passed |
| test_template_analysis.py | **PASS** | 1.7s | 4 passed |
| test_service_resilience.py | **PASS** | 3.3s | 12 passed |
| test_config.py | **PASS** | 0.8s | 3 passed |
| test_web_smoke.py | **FAIL** | 0.9s | 수집 오류: `ModuleNotFoundError: No module named 'fastapi'` |

**Python 3.14 (PATH 기본)으로 실행 시:** 8개 파일 모두 수집 단계에서 실패 (`docx`/`fastapi`/`auto_write` 경로 문제).

**합계 (Python 3.11):** 47 passed, 1 failed, 1 error(수집).

---

## 2. CLI 파이프라인 결과

지시서 명령: `python -m auto_write.main --input ... --output ...`

| 항목 | 결과 | 비고 |
|---|---|---|
| JSON 입력 로드 | OK | `tmp_test_input.json` 생성 (UTF-8) |
| 파이프라인 실행 (`auto_write.main`) | **FAIL** | `auto_write.main`은 FastAPI 앱 진입점이며 CLI `--input`/`--output` 미지원. `ModuleNotFoundError: fastapi` (Py3.11) |
| 대체 경로 `python -m app.main` | **FAIL** | `app.generator.content_writer` 없음 — `generator/`, `validator/` 디렉터리가 비어 있음 |
| 출력 파일 생성 | **FAIL** | `tmp_test_output.json` 미생성 |
| total_score 범위 | N/A | |
| 한글 인코딩 | OK | 입력 JSON UTF-8 저장 확인 |

---

## 3. FastAPI 서버 스모크 결과

`uvicorn auto_write.main:app` @ `127.0.0.1:18000` (Python 3.11)

| 엔드포인트 | 결과 | 응답 요약 |
|---|---|---|
| /health | **FAIL** | 서버 기동 실패 — `from auto_write.main import app` 시 `No module named 'fastapi'` |
| /evaluate (루트 POST) | **SKIP** | 실제 API는 `POST /api/projects/{project_id}/evaluate` (프로젝트·DOCX 선행 필요). 루트 `/evaluate` 없음 |

**참고:** `launch.bat`도 동일하게 `uvicorn auto_write.main:app` 사용 → fastapi 설치 전에는 웹앱 기동 불가.

---

## 4. 오케스트레이터 연동 (d:/v_up)

| 항목 | 결과 | 비고 |
|---|---|---|
| auto_write 업무 라우팅 | **OK** | `Get-RouteForTask "auto_write 사업계획서 생성 및 평가"` → `GPT\|FULL_AUTO\|` (동일 셸, UTF-8) |
| orchestrator.ps1 -WhatIf | **OK** | exit code: **0**. 배정: GPT (FULL_AUTO). DryRun/WhatIf 메시지 출력. LIVE 보드 실제 변경 없음(WhatIf) |
| 라우팅 (중첩 powershell) | **FAIL** | `consulting-prompt.ps1` 파서 오류(인코딩 깨짐) — 별도 프로세스에서 dot-source 시 |

---

## 5. 모듈 로드 점검

`PYTHONPATH=D:\auto_write\app`, Python 3.11:

| 모듈 | 결과 |
|---|---|
| openai_client | **OK** |
| project_service | **OK** |
| evaluation_service | **OK** |
| docx_ops | **OK** |
| render_service | **OK** |
| autofill | **OK** |

Python 3.14 (PATH 기본): 위 5개 서비스 **FAIL** (`openai`/`docx` 미설치), autofill만 OK.

---

## 6. 종합 판정

- [ ] 전체 통과 (pytest 모두 PASS + 서버 기동 OK + 연동 OK)
- [x] **일부 실패 (수동 조치 필요)**

### 실패 항목

| 영역 | 원인 |
|---|---|
| pytest `test_project_service_safety` 1건 | 앵커에 빈 문단 없을 때 섹션 삽입 — generate errors=2 (기대 0) |
| pytest `test_web_smoke` | `fastapi` 미설치 |
| FastAPI /health | 동일 — `fastapi` 미설치 |
| CLI JSON 파이프라인 | 진입점 혼동 + `app/generator`·`app/validator` 빈 폴더로 `app.main` 불가 |
| Python 3.14 기본 실행 | requirements 미반영 |

### 권장 조치

1. **Python 3.11 고정**으로 테스트·서버 실행 (`launch.bat`과 동일 후보).
2. `cd D:\auto_write\app` 후 `pip install -r requirements.txt` (최소 `fastapi`, `unhwp` 확인).
3. `test_generate_inserts_section_when_anchor_has_no_blank_paragraph` — `project_service.generate` DOCX 삽입 오류 2건 원인 조사.
4. CLI 검증 시 `auto_write.main` 대신 레거시 `app.main` 복구 또는 별도 CLI 모듈 문서화 필요.
5. `/evaluate` 스모크는 프로젝트 생성·`output.docx` 후 `POST /api/projects/{id}/evaluate`로 재검증.

---

## 7. 다음 조치

- **전체 통과 아님** → `D:\v_up\valueup-ai-hub\40_AI_SHARED\07_EXECUTION_RESULT.md` 기록 **생략** (완료 기준 미충족).
- 임시 파일 `tmp_test_input.json` 삭제 완료. `tmp_test_output.json`은 미생성.

---

## 8. 실행 환경 메모

- 실제 OpenAI API 호출: **수행하지 않음** (모듈 import만).
- 서버 바인딩: `127.0.0.1:18000` only.
- 오케스트레이터: `-WhatIf` only.
