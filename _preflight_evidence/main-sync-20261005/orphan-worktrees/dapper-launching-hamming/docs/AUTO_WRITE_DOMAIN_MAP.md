# AUTO_WRITE_DOMAIN_MAP.md — auto_write 도메인·코드 흐름 지도

> 작성: 2026-06-05 / 갱신: 2026-08-09 (도메인 구조개편 완료)

## 1. 한눈에 보는 구조

```
D:\auto_write\
├─ app\
│  ├─ main.py                      # 얇은 진입(71줄)
│  ├─ _build_chochang.py           # 진단 CLI
│  ├─ document_quality_orchestrator.py   # 품질 하네스 CLI 진입
│  ├─ lrule_gate.py                # L규칙 CLI 게이트
│  ├─ requirements.txt
│  ├─ auto_write\
│  │  ├─ config.py                 # Settings + 도메인 라우팅 (get_domain_workspace/results)
│  │  ├─ models.py                 # TemplateProfile, ProjectInput 등
│  │  ├─ storage.py
│  │  ├─ main.py                   # FastAPI 앱
│  │  ├─ analysis\docx_template.py # 양식 분석
│  │  ├─ domains\                  # [신규] 도메인 경계
│  │  │  ├─ domain_classifier.py   # business_plan/consultant_application/other 분류
│  │  │  ├─ domain_router.py       # runtime domain resolution
│  │  │  ├─ business_plan\pipeline.py    # BP facade
│  │  │  └─ consultant_application\pipeline.py  # CA facade
│  │  └─ services\
│  │     ├─ [CORE] label_utils, psst_patterns, source_pool_utils, docx_ops,
│  │     │         hwp_docx_convert, hwpx_fill, doc_text_extract, render_service,
│  │     │         qa_service, openai_client, image_service, submittable_filler,
│  │     │         doc_quality_ops, doc_quality_score, document_type_classifier,
│  │     │         document_quality_orchestrator, usage_acceptance, finalizer,
│  │     │         lrule_enforcer, lrule_domain_gate, hwpx_submit, form_analyzer,
│  │     │         cross_form_output_policy, defect_classifier, quality_ratchet,
│  │     │         conversion_fidelity, hwpx_layout_fix, hwpx_form_extract, ...
│  │     ├─ [BIZPLAN] cross_form_autofill, psst_fill, psst_check, evaluation_service,
│  │     │            announcement_analyzer, bizplan_autopilot, bizplan_ai_writer,
│  │     │            autopilot_pipeline, quality_rules, notice_pipeline,
│  │     │            folder_analyzer, pipeline_failure_ux, hwp_fill, hwp_com_fill, ...
│  │     └─ [RESUME] resume_extract, resume_fill_service, resume_form_map,
│  │                  hwpx_fill_coverage, hwpx_resume_supplement, ...
│  ├─ bizplan\                     # [신규] BUSINESS_PLAN 도메인 패키지
│  │  ├─ services\ (wrappers → auto_write.services)
│  │  ├─ cli\ (wrappers → app/*.py)
│  │  └─ {analyzer,evaluator,pipeline,psst,rules,validators,writer}.py (facades)
│  ├─ resume\                      # [신규] CONSULTANT_APPLICATION 도메인 패키지
│  │  ├─ services\ (wrappers → auto_write.services)
│  │  ├─ cli\ (wrapper → app/resume_fill.py)
│  │  └─ {analyzer,autofill,evidence,pipeline,resume,rules,validators}.py (facades)
│  └─ tests\
│     ├─ test_architecture_boundaries.py   # 도메인 경계 검증
│     ├─ test_lrule_enforcer.py            # LRule enforcement 테스트
│     ├─ test_finalizer.py                 # Finalizer 테스트
│     ├─ test_lrule_domain_gate.py         # LRule domain gate 테스트
│     └─ lessons_coverage.json             # 151 L규칙 (domain 태그 포함)
├─ workspace\                      # 프로젝트 작업空间
│  ├─ business_plan\               # [신규] BP 도메인 workspace
│  └─ consultant_application\      # [신규] CA 도메인 workspace
└─ results\                        # 산출물
   ├─ business_plan\               # [신규] BP 도메인 results
   └─ consultant_application\      # [신규] CA 도메인 results
```

## 도메인 분류 (2026-08-09 기준)

| 도메인 | 파일 수 | 설명 |
|--------|---------|------|
| CORE | 37 | 공통 문서처리 엔진 (DOCX/HWPX/HWP/AI/QA/수용검사) |
| BIZPLAN | 18+ | 사업계획서 작성/PSST/평가/공고분석 |
| CONSULTANT_APPLICATION | 7 | 이력서/신청서 자동작성/커버리지 |
| MIXED | 0 | 전부 분리 완료 |

## 의존성 방향

```
domains → core (허용)
core → domains (금지)
business_plan → consultant_application (금지)
consultant_application → business_plan (금지)
```

## 2. 도메인 라우팅 흐름

```
INPUT → DomainRouter.resolve()
  ├─ explicit_domain 우선
  ├─ document_type으로 판별
  ├─ domain_classifier 키워드 스코어링
  └─ 모호하면 OTHER (안전 fallback)

→ DomainContext(domain, workspace_dir, results_dir)
  ├─ business_plan → BusinessPlanPipeline
  ├─ consultant_application → ConsultantApplicationPipeline
  └─ other → 기존 단일 파이프라인
```

## 3. LRule Enforcement 흐름

```
artifact → LRuleEnforcer.enforce(domain, artifact_path)
  ├─ 151개 canonical 규칙 전수 판정
  ├─ domain별 applicable/non-applicable 결정
  ├─ mechanized guard 실행 (있으면)
  ├─ SHA256 binding
  └─ JSON report 생성

→ Finalizer.finalize(artifact, lrule_report)
  ├─ FAIL/REVIEW_REQUIRED/UNVERIFIABLE = 0 → FINAL
  └─ 아니면 → _DRAFT 유지, submittable=False
```

## 4. 문서 생성 흐름 (기존)

1. **양식 분석** — `ProjectService.analyze_uploaded_template(name, bytes)` → `TemplateProfile`
   (sections: field_id/anchor_text, tables: cell 그리드, image_slots, questions)
2. **프로젝트 생성** — `create_project(template_id, name)` → `save_project_form(answers, references)`
3. **생성** — `ProjectService.generate(pid)` → `ArtifactBundle`
   - AI 작성(`openai_client`) → `render_service`(DOCX) → `qa_service.build_report` → `image_service`
   - 산출: `workspace/projects/<pid>/output/output.docx`, `qa_report.json`, `transfer_report.json`
4. **마감** — `_build_chochang.py finalize <pid>` → `SubmittableFiller` 로 잔존 placeholder/가이드 정리 → `results/<제출초안>.docx`

## 5. 문서 품질 하네스가 끼어드는 지점

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

## 6. 핵심 인터페이스 (하네스가 의존)

| 모듈 | 재사용 대상 |
|------|------------|
| `docx_ops` | `_iter_body_paragraphs`, `_paragraph_text`, `set_cell_text`, `GUIDE_MARKER_RE`, 색상/음영 정규화 |
| `qa_service` | `QAService.GUIDE_MARKER_RE`, `CRITICAL_GUIDE_MARKER_RE`, `build_report` |
| `project_service` | `PSST_PROBLEM_RE/SOLUTION_RE/SCALE_RE/TEAM_RE`, `CORE_TABLE_LABEL_RE` |
| `config` | `get_settings()` (results_root, workspace_root), `ensure_directories` |
| `_build_chochang` | `inspect` 서브커맨드(문단/표 덤프) |

## 7. 경로·실행 규약

- `app_root = D:\auto_write\app`, `workspace_root = D:\auto_write\workspace`, `results_root = D:\auto_write\results`
- `.env` 위치: `app/.env` (config가 로드, 값은 출력 안 함)
- AI provider: `OPENAI_API_KEY` 우선 → `ANTHROPIC_API_KEY` → `none`(규칙기반 fallback)
- 실행 인터프리터: 시스템 Python 3.11~3.13 (launch.bat 자동탐색). venv 없음. import는 `app/` 기준.

## 8. 기존 vs 신규 (중복 회피)

- **품질 점수**: 기존 `evaluation_service`(AI 공고 채점, 내용 품질) ≠ 신규 `doc_quality_score`(결정론 형식·구조 검수). 목적이 달라 병존.
- **검수**: 기존 `qa_service.build_report`(생성 직후 필수입력/placeholder) + 신규 `doc_quality_inspection`(후처리 후 형식 검수) → inspection 스킬이 둘을 함께 호출.
- **PSST**: 기존 정규식(섹션 헤더 인식) + 신규 내용 충실도(4영역×4항목 등급) → 재사용 + 확장.
