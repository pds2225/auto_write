# AUTO_WRITE_DOMAIN_MAP.md — auto_write 도메인·코드 흐름 지도

> 작성: 2026-06-05 / 문서 품질 하네스가 연결되는 기존 코드베이스 구조

## 1. 한눈에 보는 구조

```
D:\auto_write\
├─ app\
│  ├─ main.py                      # 얇은 진입(71줄)
│  ├─ _build_chochang.py           # 진단 CLI: analyze|generate|finalize|inspect|struct|heads (345줄)
│  ├─ document_quality_orchestrator.py   # [신규] 품질 하네스 CLI 진입
│  ├─ requirements.txt             # fastapi/uvicorn/jinja2/python-docx/openai/pypdf/olefile/unhwp ...
│  ├─ tests\                       # pytest (기존 + test_document_quality_harness.py[신규])
│  └─ auto_write\
│     ├─ config.py                 # Settings, 경로 해석, .env 로드
│     ├─ models.py                 # TemplateProfile, ProjectInput, EvidenceSource 등
│     ├─ storage.py                # 프로젝트 입출력 저장
│     ├─ main.py                   # FastAPI 앱(382줄)
│     ├─ analysis\docx_template.py # 양식 분석·안내문구 탐지·완성도 판정(784줄)
│     └─ services\
│        ├─ docx_ops.py            # DOCX 셀/단락 쓰기, 색상/음영 정규화, 이미지 삽입
│        ├─ render_service.py      # answers → DOCX 렌더링
│        ├─ qa_service.py          # build_report(): 검수(가이드/placeholder/필수)
│        ├─ project_service.py     # PSST 정규식·generate 본체(1670줄)
│        ├─ evaluation_service.py  # 공고 평가기준 채점·보완 루프(AI)
│        ├─ openai_client.py       # AI provider 래퍼(openai/anthropic)
│        ├─ image_service.py       # 이미지 생성
│        ├─ submittable_filler.py  # finalize 잔존 채움
│        └─ [신규] doc_quality_ops / document_type_classifier / psst_check /
│                  infographic_suggest / doc_quality_score / document_quality_orchestrator
└─ results\  workspace\  outputs\  data\  backup\
```

## 2. 문서 생성 흐름 (기존)

1. **양식 분석** — `ProjectService.analyze_uploaded_template(name, bytes)` → `TemplateProfile`
   (sections: field_id/anchor_text, tables: cell 그리드, image_slots, questions)
2. **프로젝트 생성** — `create_project(template_id, name)` → `save_project_form(answers, references)`
3. **생성** — `ProjectService.generate(pid)` → `ArtifactBundle`
   - AI 작성(`openai_client`) → `render_service`(DOCX) → `qa_service.build_report` → `image_service`
   - 산출: `workspace/projects/<pid>/output/output.docx`, `qa_report.json`, `transfer_report.json`
4. **마감** — `_build_chochang.py finalize <pid>` → `SubmittableFiller` 로 잔존 placeholder/가이드 정리 → `results/<제출초안>.docx`

## 3. 문서 품질 하네스가 끼어드는 지점

하네스는 **3·4단계로 생성된 완성 DOCX** 를 입력으로 받아 후처리·검수한다. 즉 생성 파이프라인과 **독립**이며 어떤 완성 DOCX(과거 산출물 포함)에도 적용 가능.

```
완성 DOCX ─▶ DocumentQualityOrchestrator.run()
   ├─ 백업(results/backup/<ts>)
   ├─ 유형 분류(document_type_classifier)
   ├─ 후처리(doc_quality_ops.run_all): 안내문구·글머리표·표공백·빈문단·강조
   ├─ PSST 검사(psst_check)            # business_plan / pitch_deck
   ├─ 이미지 제안(infographic_suggest)
   ├─ 품질 점수(doc_quality_score, 100점)
   ├─ 게이트(85점) → 미달 시 보완 루프(≤10, 수렴 조기종료)
   └─ 저장 + 리포트(md/json)
```

## 4. 핵심 인터페이스 (하네스가 의존)

| 모듈 | 재사용 대상 |
|------|------------|
| `docx_ops` | `_iter_body_paragraphs`, `_paragraph_text`, `set_cell_text`, `GUIDE_MARKER_RE`, 색상/음영 정규화 |
| `qa_service` | `QAService.GUIDE_MARKER_RE`, `CRITICAL_GUIDE_MARKER_RE`, `build_report` |
| `project_service` | `PSST_PROBLEM_RE/SOLUTION_RE/SCALE_RE/TEAM_RE`, `CORE_TABLE_LABEL_RE` |
| `config` | `get_settings()` (results_root, workspace_root), `ensure_directories` |
| `_build_chochang` | `inspect` 서브커맨드(문단/표 덤프) |

## 5. 경로·실행 규약

- `app_root = D:\auto_write\app`, `workspace_root = D:\auto_write\workspace`, `results_root = D:\auto_write\results`
- `.env` 위치: `app/.env` (config가 로드, 값은 출력 안 함)
- AI provider: `OPENAI_API_KEY` 우선 → `ANTHROPIC_API_KEY` → `none`(규칙기반 fallback)
- 실행 인터프리터: 시스템 Python 3.11~3.13 (launch.bat 자동탐색). venv 없음. import는 `app/` 기준.

## 6. 기존 vs 신규 (중복 회피)

- **품질 점수**: 기존 `evaluation_service`(AI 공고 채점, 내용 품질) ≠ 신규 `doc_quality_score`(결정론 형식·구조 검수). 목적이 달라 병존.
- **검수**: 기존 `qa_service.build_report`(생성 직후 필수입력/placeholder) + 신규 `doc_quality_inspection`(후처리 후 형식 검수) → inspection 스킬이 둘을 함께 호출.
- **PSST**: 기존 정규식(섹션 헤더 인식) + 신규 내용 충실도(4영역×4항목 등급) → 재사용 + 확장.
