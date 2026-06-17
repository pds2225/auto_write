# CLAUDE.md — auto_write 프로젝트 작업 지침

> `D:\auto_write` 전용. 정부지원사업 문서 자동생성 + 문서 품질 개선 하네스 프로젝트.
> 공통 지침(글로벌 CLAUDE.md)과 충돌 시 이 repo-local 규칙을 우선한다.
>
> **🔄 세션을 새로 시작했다면 `RESUME.md` 를 먼저 읽어라** — 진행 상태·남은 일·재개 명령이 있다.
> 작업을 잠시 멈추거나 컨텍스트가 무거워지면 "체크포인트 저장"으로 RESUME.md 를 갱신하고,
> 새 세션에서 "이어서"로 복원한다(session-resume 스킬).
>
> **현재 상태(2026-06-12):** 실사용 39건 수정 트랙(US-0~US-8) 완료 — 수용검사 게이트
> (R8/R9)·블라인드 마스킹(`--blind-review`)·제출 정리(`--submit-clean`)·HWP 형식 게이트
> (`--required-format`)·`--strict` 종료코드(0/1/2/3) 배선. 변경이력 표가 잘려 보여도
> 이 줄이 최신이다. 테스트는 반드시 `py -3.11 -m pytest` (기본 3.14 는 matplotlib 부재).

## 프로젝트 개요

- 핵심: 양식 DOCX 분석 → AI 작성 → DOCX 렌더링 → 검수(`app/auto_write/services/`).
- 실행: 시스템 Python(venv 없음) — **테스트·실행은 `py -3.11` 권장**(PATH 기본 3.14 는
  matplotlib 부재로 pytest 수집 에러). `app/` 이 import 기준. AI 키 없어도 동작.
- 진단 CLI: `app/_build_chochang.py inspect|analyze|generate|finalize|struct|heads`.

---

## 하네스: 문서 품질 개선 (Document Quality Harness)

**목표:** 완성된 DOCX(사업계획서·R&D·컨설팅·정책자금·인증·수출·현장클리닉 보고서)의
서식·구조·강조·시각화 품질을 자동으로 끌어올리고 100점 품질점수로 게이팅한다.

**트리거:** 다음 요청 시 `document-quality-orchestrator` 스킬을 사용하라.
- "문서 품질 개선", "DOCX 후처리", "양식 안내문구 삭제", "글머리표 공백 정리",
  "인포그래픽 제안", "auto_write 문서검수", "제출문서 서식 보정", "PSST 검사",
  "품질점수 산정", "문서 최종검수", "사업계획서 다듬어줘", "보고서 정리해줘"
- 재실행·수정·보완·부분 재실행(특정 단계만)·회귀 검수 요청도 동일 스킬로 처리.
- 단순 질문은 직접 응답 가능.

### 실행 명령 (PowerShell)

```powershell
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\경로\문서.docx"            # 전체 1회
python document_quality_orchestrator.py 문서.docx -o 결과.docx --underline
python document_quality_orchestrator.py --rollback "..\results\backup\<ts>" 결과.docx
python _build_chochang.py inspect "결과.docx"                          # 진단만
python auto_write_autopilot.py "문서.docx" --submit-clean --strict     # 무인 수정+수용검사 게이트
python self_diagnose.py "제출본.docx"                                  # 제출 가능성 진단(0/1/2/3)
# 테스트 (반드시 py -3.11 — 기본 3.14 는 matplotlib 부재로 수집 에러)
py -3.11 -m pytest tests/ -q
```

### 에이전트 (`.claude/agents/`) — 6개 (2026-06-07 슬림화: 12→6)

- **doc-architect** — 파이프라인 설계·단계 조율 (구 document-architect)
- **doc-safety-guard** — 원본 백업·롤백 + 보안 게이트 (구 backup-rollback-agent + security-agent)
- **doc-analyzer** — 유형분류 + PSST 심사 + 인포그래픽 제안 (읽기 전용; 구 document-type-classifier + psst-review-agent + infographic-suggestion-agent)
- **doc-postprocessor** — 안내문구 삭제 + 서식 정규화 + 핵심문장 강조 (DOCX 변형; 구 template-cleanup-agent + formatting-normalizer + content-emphasis-agent)
- **doc-quality-gate** — 채점·85점 게이트 + 회귀·비훼손 검수 (구 quality-gate-agent + qa-document-agent)
- **doc-writer** — 최종 리포트·핸드오프 문서화 (구 documentation-agent)

> 실행 순서: doc-architect → doc-safety-guard(백업) → doc-analyzer → doc-postprocessor → doc-quality-gate(미달 시 재작업 루프) → doc-safety-guard(실패 시 복구) → doc-writer.

### 스킬 (`.claude/skills/`)

오케스트레이터 허브: **document-quality-orchestrator**.
세부: docx-template-cleanup · bullet-spacing-normalization · paragraph-font-sizing ·
table-whitespace-cleanup · content-emphasis · document-type-classification ·
psst-structure-check · infographic-suggestion · document-quality-scoring ·
backup-and-rollback · document-quality-inspection

### 커맨드 (`.claude/commands/`)

`/improve-doc-quality` · `/auto-write-quality` · `/auto-write-inspect` ·
`/auto-write-psst` · `/auto-write-images` · `/auto-write-finalize` ·
`/auto-write-autopilot` · `/auto-write-bizplan` · `/auto-write-analyze` · `/auto-write-selfdev`

### 핵심 코드 (`app/auto_write/services/`)

doc_quality_ops · document_type_classifier · psst_check · infographic_suggest ·
doc_quality_score · document_quality_orchestrator (진입: `app/document_quality_orchestrator.py`,
`scripts/run_document_quality_harness.py`) ·
**usage_acceptance**(수용검사 엔진+AcceptanceConfig+force_draft_name) ·
**autopilot_pipeline**(무인 수정+게이트, 진입: `app/auto_write_autopilot.py`) ·
**submission_orchestrator**(제출 end-to-end, 진입: `python -m auto_write.submit`) ·
self_diagnose(진단 CLI: `app/self_diagnose.py`) · image_apply(NotebookLM 삽입/추출/제거) ·
hwp_docx_convert(HWP↔DOCX 변환, COM 대화형 전용)

### 품질 게이트

100점 만점, 9항목(안내문구15/글머리표10/문단공백10/글자크기15/표10/강조10/유형구조15/PSST10/이미지5).
**90 우수 / 85 통과 / 70 보완 / 미만 실패.** 미달 시 최대 10회 보완 루프, 수렴 시 조기종료 후 수동확인 항목 명시.

**⚠ 이중 게이트:** 점수 게이트는 '서식 품질'만 본다. 제출 가능성은 별도의
**수용검사 게이트(usage_acceptance, R7/R8/R9)** 가 판정한다 — fail 결함(마커·자기삽입
블록·자리표시·미체크 선택란·공란 필수칸·유색 텍스트·폰트 혼용 등) 1개라도 있으면
출력명에 `_DRAFT` 강제(제출 금지). 점수 99 라도 `_DRAFT` 면 제출불가다.
진단: `python self_diagnose.py` (exit 0=제출가능/1=입력오류/2=제출불가/3=검사불능).

### 백업·롤백

후처리 전 원본을 `results/backup/<YYYYMMDD_HHMMSS>/` 에 백업. **원본 절대 덮어쓰기 금지**
(출력=입력 경로면 ValueError). 복구: `--rollback <backup_dir> <target>`.

### 금지

원본 덮어쓰기 · 백업 없는 수정 · Secret/API Key/.env 출력 · 유료 API 무단 호출 ·
기존 생성 기능 삭제 · results/templates 원본 삭제 · 테스트 없이 완료 보고 · 실패의 성공 보고.

### 글로벌 `D:\.claude` 와의 관계

글로벌은 웹 개발 하네스 전용으로 도메인이 다르다. 직접 재사용·훼손하지 않는다.

---

**변경 이력**

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-06-05 | 문서 품질 개선 하네스 초기 구축 | 전체 | auto_write 전용 DOCX 후처리·검수·점수 하네스 신규 |
| 2026-06-07 | 에이전트 슬림화 12→6 (감사 78점 개선) | .claude/agents/(신규 6·삭제 12)·skills/document-quality-orchestrator/SKILL.md·commands/{improve-doc-quality,auto-write-quality,auto-write-psst,auto-write-images,auto-write-inspect}.md·CLAUDE.md | 팀 크기 권장 5~7 초과(12개 비대)·중복 의심쌍(qa↔gate, doc↔architect) 해소. 같은 코드 모듈/책임끼리 병합(분석3·후처리3·검증2·안전2 + 설계·문서화). app/ 코드 무수정 → pytest 72 회귀 없음. 옛 이름 참조 전부 새 이름으로 동기화 |
| 2026-06-08 | 공고 95점 채점 엔진 연결 + 이미지(차트) 생성 기능 구현 | app/auto_write/services/{chart_generator,chart_insert}.py(신규)·tests/test_chart_generator.py·scripts/{eval_announcement_score,build_chart_improved,extract_doc_data}.py·results/미래큐러스_95점_작성가이드_20260608.md | ultrawork: evaluation_service로 미래큐러스 AI인재실증형 작성본을 공고 5항목 채점=90/100. matplotlib 차트 4종(간트·막대·꺾은선·조직도)+DOCX삽입 모듈 신규(테스트 12+회귀 84 passed). 케이스A 준수(원문 실값만 차트화, 90→95 갭=미기재 수치는 사용자 작성 영역). 보완본 results/miraequrus_보완_차트_20260608.docx |
| 2026-06-08 | 진단 전용 스킬 4종 → 실제 수정 + 통합 오토파일럿 셋팅 | app/auto_write/services/{image_apply,psst_fill,autopilot_pipeline}.py(신규)·app/auto_write_autopilot.py(신규 CLI)·tests/test_auto_write_apply.py(신규)·.claude/commands/{auto-write-images,auto-write-psst,auto-write-inspect,auto-write-finalize,auto-write-autopilot}.md | 사용자 요청: images/psst/inspect/finalize 가 '진단만' → '실제 DOCX 수정'으로 전환 + 오토파일럿화. image_apply(표 실측치→차트, 없으면 자리표시 placeholder)·psst_fill(누락/미흡 영역 작성 뼈대+가이드 삽입)·autopilot_pipeline(백업+서식수정+점수게이트→이미지적용→PSST보강→통합리포트 무인 연속). 안전 결정(사용자 승인): **숫자 날조 0**(문서 실값만, 없으면 빈칸 placeholder), 점수는 서식수정 기준(보강이 점수 안 부풀림), 원본 절대 보존(out==in ValueError). 커맨드는 --apply/--fix 모드 추가, 신규 /auto-write-autopilot. 신규테스트 8 + 회귀 84 = **92 passed**, CLI E2E 실증(차트2·자리표시2·PSST2영역·게이트판정 OK) |
| 2026-06-09 | 제출가능 사업계획서 생성·완성 오케스트레이터(autopilot/ultraqa/ultragoal) | app/auto_write/services/{bizplan_ai_writer,bizplan_autopilot}.py(신규)·app/bizplan_autopilot.py(신규 CLI)·tests/test_auto_write_apply.py·.claude/commands/auto-write-bizplan.md(신규)·CLAUDE.md | 사용자 요청 '바로 제출 가능한 완성도 높은 사업계획서 생성 코드'. 기존 generate/score_document 재사용 + 빠진 조각 구현: bizplan_ai_writer(PSST 약점영역 AI 작성, **수치엔 [산출근거] 병기·무출처는 [확인필요]** = 사용자 승인 정책, 키 없으면 skip→psst_fill 폴백), bizplan_autopilot(AI작성→품질오토파일럿→공고채점→목표충족률까지 반복 = ultraqa/ultragoal 루프). project_service 무수정(최소변경 원칙). 신규테스트 3 + 회귀 92 = **95 passed**, 실 AI E2E 실증(3영역 작성·[확인필요] 정확 생성·품질99.5·게이트통과). 안전: 원본보존·날조0·점수 독립채점 |
| 2026-06-09 | 공고문 분석 + 양식 분석 기능 | app/auto_write/services/{doc_text_extract,announcement_analyzer,form_analyzer}.py(신규)·app/analyze_docs.py(신규 CLI)·tests/test_doc_analyze.py(신규)·.claude/commands/auto-write-analyze.md(신규)·app/bizplan_autopilot.py(공고 파일 입력 확장)·CLAUDE.md | 사용자 요청 '공고문분석·양식분석 기능'. doc_text_extract(DOCX/PDF/HWP/TXT→텍스트: ensure_template_docx 변환 재사용 + pypdf + HWP PrvText 폴백), announcement_analyzer(평가기준+지원대상·자격·금액·마감·제출서류·가점 종합 추출, AI 구조화+정규식 휴리스틱 폴백, 평가기준은 AI evaluation_criteria 폴백으로 안정화), form_analyzer(analyze_template 재사용, 작성항목·필수·표·이미지·PSST 구조 요약). bizplan_autopilot 공고입력을 파일형식 자동인식(extract_text)으로 확장. 읽기전용·원본 미수정. 신규테스트 6 + 회귀 95 = **101 passed**, CLI E2E(공고 평가기준4·총100점·핵심정보 / 양식 항목9·PSST4 정확) |
| 2026-06-08 | 제출-100 이니셔티브 Phase1~3 (공고 평가루프·인포그래픽·/goal) | 신규 app/auto_write/services/{eval_loop_runner,image_providers,plan_builder,submission_orchestrator}.py·app/auto_write/submit.py·tests/{test_eval_loop_runner,test_image_pipeline,test_submission_pipeline}.py / 수정 {config,main,evaluation_service,project_service,image_service,render_service}.py·requirements.txt | 공고 평가기준 채점 루프 종결+Gemini Nano Banana 요약 인포그래픽 생성·배치+end-to-end /goal CLI. 브랜치 feature/submission-100-auto, pytest 81 passed, 원본 미변경 |
| 2026-06-10 | 실사용 기준 자가진단·자동개발 루프 구축 (usage_acceptance + /auto-write-selfdev) | 신규 app/auto_write/services/usage_acceptance.py·app/self_diagnose.py·app/tests/test_usage_acceptance.py·workspace/requirements_ledger.json·.claude/commands/auto-write-selfdev.md | 사용자 보고: 품질점수 99.5 '통과' 문서가 실제로는 제출불가([확인필요]16·NotebookLM블록16·체크박스미선택3·폰트6종혼용·명칭공란 등) = 채점기가 '서식청소'만 측정, '제출가능성' 미측정. 해결: 심사위원 관점 하드페일 검사 9종(결정론·AI무호출·읽기전용·fail 1개=제출불가) + 사용자 요구사항 원장(R1~R8) 자동대조 + 한 루프 1개선 자동개발 커맨드(/auto-write-selfdev, 오답노트 규칙 포함). 구현 중 lxml proxy id 재사용에 의한 셀 dedup 과소집계 버그 발견·수정(refs 유지). 신규테스트 9 passed, 실문서 E2E로 사람이 찾은 결함 7종 전부 자동검출(판정 제출불가/fail 40). 회귀 137 passed + 2 failed는 샌드박스 한글폰트 부재(PIL OSError) 환경 이슈로 코드 무관. 기존 코드 무수정(신규 파일만) — 파이프라인(autopilot) 연결은 다음 루프(R8) |
| 2026-06-10 | 제출-100 master 통합 + 텍스트 위치/NotebookLM 프롬프트 버그 2건 수정 | 수정 app/auto_write/services/{image_apply,submittable_filler,submission_orchestrator}.py·app/auto_write/submit.py / 테스트 app/tests/{test_auto_write_apply,test_submission_pipeline}.py(신규 회귀 4) / docs workspace/{goldstandard_marketgate,bug_investigation}.md | 사용자 보고: ①텍스트가 맞는 위치에 안 들어감 ②NotebookLM 프롬프트가 안 나옴 + 마켓게이트 재도전(추경) 제출본을 골드 스탠다드로. 원인: ①image_apply/submittable_filler 앵커 탐색이 본문(doc.paragraphs)만 봐서 표 셀/헤더 앵커를 놓치고 문서 끝 덤프(표 중심 정부양식에서 전부 어긋남) ②SubmissionPipeline 이 PNG(image_service)만 쓰고 image_apply(NotebookLM) 미연결. 수정: 앵커 탐색을 본문+표 셀(중첩 포함)로 확장 + addnext 로 본문/표 뒤 정위치 삽입, SubmissionPipeline step6 NotebookLM 삽입 + submit --no-notebooklm 토글. master 통합(ce46d79, 충돌 CLAUDE.md 1곳) 후 **pytest 132 passed**(128+회귀4), 원본 미변경·날조0. master 병합은 승인 대기 |
| 2026-06-11 | selfdev 루프 #2: NotebookLM 작업용 블록 자동 제거 (R5 종결) | 수정 app/auto_write/services/{image_apply,usage_acceptance}.py / 신규 app/strip_notebooklm.py CLI / 테스트 app/tests/test_auto_write_apply.py(신규 회귀 4) / 원장 workspace/requirements_ledger.json(R5 달성·R1/R6/R7 진단 반영) | /auto-write-selfdev 진단: 제출수정본(06-11)이 NotebookLM 헤더·안내 블록 2개 잔존으로 제출불가. FAIL 3종 중 유일하게 자동 해결 가능(나머지는 사용자 입력 필요=날조 금지). 해결: strip_notebooklm_blocks(삽입의 역연산, 5단락 블록 구조 확장 제거 + 구조 미확인 시 마커만 지우는 보수 규칙으로 본문 오삭제 차단, 검출 usage_acceptance SELF_BLOCK_RE 와 단일 정의 공유) + 제출 직전 1커맨드 CLI(python strip_notebooklm.py 문서.docx). 검증: **pytest 146 passed**(신규4 포함), 실문서 before/after self_inserted_blocks 2→0(fail 결함 5→3), 원본 미수정. 다음 루프=R8(usage_acceptance 파이프라인 게이트 연결) |
| 2026-06-11 | HWP/HWPX ↔ DOCX 양방향 변환 서비스 + CLI (ultraqa) | 신규 app/auto_write/services/hwp_docx_convert.py·app/hwp_docx.py(CLI)·app/tests/test_hwp_docx_convert.py(13) | 사용자 요청 'hwp↔docx 변환 기능 개발'. 흩어진 자산 통합: HWP→DOCX 3단 폴백(①한글 COM=서식 최충실 ②unhwp/HWPX XML 구조변환=document_ingest 재사용 ③PrvText 텍스트) + DOCX→HWP/HWPX(한글 COM 유일 경로, 미가용 시 ok=False+사람 할 일 안내). 확장자 방향 자동 인식 convert(), 원본 덮어쓰기 금지(out==in ValueError), scripts/docx2hwp.py 보존. CLI: python hwp_docx.py 파일 [-o 출력] [--no-com]. 검증: **pytest 155 passed**(신규 13) + 실환경 E2E 라운드트립(DOCX→HWP→DOCX, hancom_com, 본문 보존)·CLI exit 0 |
| 2026-06-11 | selfdev 루프 #3: 수용검사 게이트를 autopilot 에 연결 (R8 종결) | 수정 app/auto_write/services/autopilot_pipeline.py·app/auto_write_autopilot.py(CLI --no-acceptance) / 테스트 app/tests/test_auto_write_apply.py(사양 갱신 1·신규 2) / 원장 workspace/requirements_ledger.json(R8 달성·R7 근거 갱신) | 원장 R8: 품질점수 99.5 '통과'인데 실제 제출불가인 모순 — doc_quality_score 는 서식청소만 측정. 해결: run_autopilot 4단계에 usage_acceptance 실행, fail 결함 있으면 **출력 파일명 _DRAFT 강제(제출본 이름 차단)** + 리포트/CLI/To-Do 에 판정·결함 명시(acceptance_gate=True 기본, autopilot 출력은 NotebookLM 블록 포함 작업용 중간본이라 DRAFT 판정이 정상). bizplan_autopilot 은 ap.output_docx 추종으로 자동 정합. 검증: **pytest 144 passed**(신규 2) + 실문서 E2E(fail 19 → r8_e2e_DRAFT.docx 강제·판정 명시). 잔여: submit 등 직행 경로 게이트 연결은 차기 루프 |
| 2026-06-11 | 통합 검증 + R7 종결: PR#9/#10/#11 통합 브랜치 + submit 게이트 (autopilot 오케스트레이션) | 머지 selfdev/strip-notebooklm-blocks·feature/hwp-docx-convert·selfdev/r8-acceptance-gate / 수정 app/auto_write/services/submission_orchestrator.py·app/auto_write/submit.py(--no-acceptance) / 테스트 app/tests/test_submission_pipeline.py(신규 2) / 원장 R7 달성 | 사용자 요청 '과거 요청사항(채팅·최초 요구사항) 모두 실사용 기준 정상작동'. 흩어진 PR 3건을 integration/all-requirements 로 합쳐 전체 동작 검증(이력 충돌만 수동 보존) 후 마지막 격차 R7 종결: SubmissionPipeline 7단계에 수용검사 게이트 — fail 결함 시 final_docx _DRAFT 강제 + needs_input 안내(acceptance_gate=True 기본). 검증: **pytest 163 passed**(통합 161+신규 2) + 통합 시나리오 E2E(autopilot DRAFT → strip 마커16/37단락 제거 → 재진단 자기삽입 0, 잔여 fail 3 = 전부 사용자 입력 영역). 원장 R2/R3/R5/R6/R7/R8 달성·R1/R4 부분달성(사용자 입력 대기) |
| 2026-06-11 | bizplan 최종 복사 시 DRAFT 마킹 소실 수정 (R8 정신 전파 완결) | 수정 app/auto_write/services/bizplan_autopilot.py·app/bizplan_autopilot.py(CLI) / 테스트 app/tests/test_auto_write_apply.py(사양 강화 1) | 병렬 세션 발견 갭: bizplan_autopilot 이 마지막에 shutil.copyfile 로 최종본을 깨끗한 이름으로 복사해 중간본의 _DRAFT 판정이 소실되고 BizplanReport 에 acceptance 필드도 없었음 → 이 경로로는 제출불가 문서가 제출용 이름으로 나갈 수 있었음. 수정: ap 의 acceptance 5필드를 BizplanReport 로 전파 + 최종 이름에도 _DRAFT 강제 + To-Do/리포트/CLI 판정 표시. 검증: pytest 163 passed(test_bizplan_no_ai_completes 를 DRAFT 전파 사양으로 강화) |
| 2026-06-11 | selfdev 루프 #4: 수용검사 게이트 견고화 — fail-closed·DRAFT 마킹 보장·경로 정합 (R9) | 수정 app/auto_write/services/{usage_acceptance,submission_orchestrator,autopilot_pipeline}.py·app/auto_write/submit.py / 표면수정 app/strip_notebooklm.py(raw docstring)·app/auto_write/services/image_apply.py(주석) / 테스트 app/tests/{test_auto_write_apply,test_submission_pipeline}.py(신규 4) / 원장 R9 신설 | 멀티에이전트 코드리뷰(cb85307..a3dfb1d, 52에이전트)가 검출하고 코드 대조로 확인한 게이트 무력화 경로 4종 차단: ①submit 게이트 fail-open(게이트 예외 시 제출 이름 그대로 통과)→fail-closed(판정 불가=_DRAFT 강제+needs_input) ②DRAFT rename 실패(파일 잠금)가 침묵 속에 보고-실파일명 불일치→draft_mark_error/draft_marked 명시 ③rename 후 report submit_docx/quality_docx 댕글링→경로 동기 갱신 ④autopilot draft_path==in_path 침묵 스킵→_DRAFT2 대체 마킹(원본 보존) + run_acceptance 예외 보호(리포트·백업정보 유실 방지). 정책 헬퍼 force_draft_name 을 usage_acceptance 에 단일화(양 게이트 공유). 검증: **pytest 167 passed**(신규 4)·DOC_OK(docstring BEL 제거). 잔여(저위험, 원장 R9 비고): 중간 산출물 제출초안_* 이름 잔존·셀단위/단락단위 검출 불일치·사용자 구분선 인접 오삭제 엣지 |
| 2026-06-12 | selfdev 루프 #5: R9 잔여 저위험 3건 종결 — 중간본 DRAFT 전파·검출=제거 정합·구분선 보존 | 수정 app/auto_write/services/{usage_acceptance,image_apply,submission_orchestrator}.py / 테스트 app/tests/{test_auto_write_apply(신규 3),test_submission_pipeline(신규 1)}.py / 원장 R9 근거 갱신·findings #9~#11 종결 | 코드리뷰 잔여(findings #9~#11): ①게이트 fail/판정불가 시 최종본만 _DRAFT 되고 중간 산출물(제출초안_*·_품질·_노트북LM)은 제출용 이름 잔존 → 명명 정책 확정(이름 유지+fail 시 artifacts 전체 전파+리포트 경로 동기 갱신) ②검출(셀 텍스트 \n 결합 매칭)과 제거(단락 단위)가 달라 셀 안에서 갈라진 마커가 '지웠는데 검출됨' → strip 에 셀 단위 보강 패스(dedup_cells 공유) + 삽입 헤더 시그니처 안전핀(실본문 크로스 매치는 보존=오삭제 금지, 게이트가 사람에게) ③구분선 '─'×10+ 전부 삭제 → 삽입 상수(─×30) 정확 일치만(사용자 구분선 보존). 구현 중 잠복 버그 발견·수정: _p_text 가 lxml itertext×python-docx text 프로퍼티 중복으로 텍스트 3중 반환(정확 일치를 깨뜨림) → w:t 결합으로 정정. 검증: 기준 167 + 신규 회귀 4 = **171 passed** |
| 2026-06-12 | 실사용 39건 수정 트랙(US-0~US-8, ralplan v2 합의·승인 실행) | PR #15~#24: app/auto_write/services/{usage_acceptance,autopilot_pipeline,submission_orchestrator,bizplan_autopilot,image_apply,psst_fill,bizplan_ai_writer}.py·app/{self_diagnose,auto_write_autopilot,bizplan_autopilot,strip_notebooklm}.py·auto_write/submit.py·tests 3종·.claude/commands 3종·CLAUDE.md / 원장(R10~R14 등록·R2/3/4/5 정합) | 2026-06-11 실사용 진단 39건(architect 승인) 전수 수정: ①US-1 AcceptanceConfig+머리글/바닥글/텍스트박스 순회(ACC-9) ②US-3b 폰트 ascii/eastAsia 이중집계 오탐(ACC-8) ③US-2 블라인드 마스킹 방향 역전 — --blind-review(○○○ 허용+실명검출, ACC-1/2) ④US-3a 색상·psst스캐폴드·한국식날짜·스타일폰트 검사+R8 __all__ 재정의(ACC-3/6/13/7, LEDGER-1) ⑤US-3c warn 선도입(괄호선택란·라벨확장·빈그림칸·분량)+HWP 형식 게이트 --required-format(ACC-4/5/10/11/12) ⑥US-4 재실행 백업·--strict(0/1/2/3)·공고파일 경고·이미지 단계 보호(PIPE-2/3/7/8) ⑦US-5 self_diagnose cp949 크래시+exit 계약(ENC-1/2) ⑧US-6 extract_notebooklm_prompts+--submit-clean(프롬프트 md 보존→strip→재검사, 상호배타 명명, PIPE-6/LEDG-4) ⑨US-7 원장 정합(LEDG-5/6/7) ⑩US-8 문서 동기화(DRIFT-1~5). pytest 167→202 passed(신규 35, 회귀 0). PR #14(R9 fail-closed)는 병렬 세션 기병합 확인 후 그 위에 작업 |
| 2026-06-18 | selfdev 루프 #6: R11 유색 텍스트 자동교정 추가(검출만 있고 교정 부재 갭) | 수정 app/auto_write/services/doc_quality_ops.py / 테스트 app/tests/test_usage_acceptance.py(신규 4) / 원장 R11 근거 갱신 | self_diagnose 진단: R11(검정 본문) check_residual_colored_runs(ACC-3)는 유색 텍스트를 fail로 '검출'하나 그것을 검정으로 바꾸는 '교정'이 doc_quality_ops에 없어 사용자가 수동으로 고쳐야 했음. 해결: normalize_colored_text_to_black(본문+표셀 sweep, 검정·보존색·테마색·미지정은 보존, 명시 유색만 검정 — docx_ops._set_run_color_black_unless_preserved 재사용으로 검출↔교정 단일출처) + run_all 배선(normalize_colors=True 기본). 멱등·텍스트무손실·강조보존. 검증: 미래큐러스 실문서 ACC-3 유색 18단락(46런)→0 실증, pytest 208→212 passed(신규 4, 회귀 0). 격리 워크트리 selfdev/r11-color-normalize |