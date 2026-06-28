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
- **평생개발목표: DOCX↔HWP 양방향 변환 일치도 100%**(측정 하네스 conversion_fidelity 로
  baseline%→개선 루프, 거짓완료 금지 — 항상 측정값으로 보고). 정부양식이 HWP 라 입출력단
  변환은 `docx-hwp-conversion` 스킬이 담당한다.

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
backup-and-rollback · document-quality-inspection ·
**docx-hwp-conversion**(DOCX↔HWP/HWPX 양방향 변환, 입출력단)

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

## 하네스: 빈 양식 자동완성·제출완성 (cross-form-submission)

**목표:** 빈 새 양식 B + 완성된 기존 사업계획서 A → A 의 **사실 항목을 B 의 유사 칸에 전사**
(표칸·본문빈칸·선택칸 □→■)하고 검수해서 **즉시 제출 가능한 B** 로 완성한다. 이미지는 직접
생성하지 않고 **NotebookLM 프롬프트로 대체**. A 에 없는 칸은 `[확인필요]`(사실)/`[작성 필요]`
(서술)로 정직하게 남긴다. **글을 새로 쓰지 않는 "사실 재배열 전사" 전용**(서술 문장 작성은
다음 단계 하네스).

**트리거:** 다음 요청 시 `cross-form-submission` 스킬을 사용하라. 단순 질문은 직접 응답 가능.
- "빈 양식 채워줘", "이 양식에 옮겨줘", "기존 사업계획서로 새 양식 작성", "양식 자동완성",
  "새 양식 제출본 만들어줘", "A 내용으로 B 채워 제출가능하게", "cross-form", "전사해서 제출본 완성"
- 재실행·수정·보완·부분 재실행(전사만/검수만)·needs_confirm 확정·다른 양식 재전사도 동일 스킬.

**경계:** '완성 DOCX 다듬기'=document-quality-orchestrator / '처음부터 작성'=bizplan-orchestrator
/ '공고·양식 분석'=announcement-form-analysis. 이 스킬은 **입력 2개(완성본 A + 빈 양식 B)** 로
"전사 후 제출완성"만 한다. 엔진은 모두 기존 코드 재사용(cross_form_autofill·usage_acceptance·
submission_orchestrator·image_apply). 신규 에이전트는 `cross-form-filler` 1개, 나머지 6개 재사용.

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
| 2026-06-18 | autopilot 배치: R4 앵커 정위치 정합 + 제출 파이프라인 quality 리포트 빈값 버그 | 수정 app/auto_write/services/{image_apply,submission_orchestrator}.py / 테스트 app/tests/{test_auto_write_apply(신규 1),test_submission_pipeline(단언 강화)}.py | ①R4(정위치 삽입): image_apply._find_anchor 가 단일 패스에서 역포함 매칭(짧은 부분문자열 본문 t in a)을 써서 표 셀 정방향 앵커보다 앞 단락을 먼저 잡아 프롬프트 블록을 엉뚱한 위치에 삽입하던 결함 → 정방향 우선 2-패스(2차 역포함은 길이>4 & 앵커 25%이상 임계)로 차단, 죽은 _anchor_matches 제거. ②submission_orchestrator: q_result.to_dict() 호출이 HarnessResult(as_dict 만 존재)에서 AttributeError→except 로 제출 리포트의 quality 가 항상 빈 dict 였음 → as_dict() 로 정정(품질 리포트 실제 채워짐). 검증: pytest 215 passed(신규 1+E2E quality 단언, 회귀 0). R1(제출완성도)은 이 리포트 정합으로 일부 개선, 잔여는 사용자 입력 영역(수치·체크박스) |
| 2026-06-18 | ultraqa 다각 감사(워크플로우 6차원→적대검증) 후 R11 교정 정합 4건 수정 | 수정 app/auto_write/services/{doc_quality_ops,usage_acceptance}.py / 테스트 app/tests/test_usage_acceptance.py(신규 2) | 읽기전용 다차원 감사가 R11 교정의 실제 결함 확정: ①normalize_colored_text_to_black 가 w:val="auto" 런을 _normalize_color_value('auto')='a' 로 오인해 검정 덮어씀(검출은 color.rgb=None 으로 통과) → 정규 6자리 hex 만 교정하도록 가드(`re.fullmatch([0-9a-f]{6})`)로 검출↔교정 역연산 정합 ②검출(check_residual_colored_runs)·교정 둘 다 머리글/바닥글/텍스트박스 미순회로 그 영역 유색 안내문구가 R11 게이트 통과 → 양쪽을 _iter_extra_paragraphs+_iter_textbox_paragraphs(ACC-9) 범위로 확장 ③자기삽입 블록 재교정 동작 docstring 정합 ④비-RGB(auto)·머리글 유색 회귀 테스트 추가. 검증: pytest 216→218 passed(신규 2, 회귀 0) |
| 2026-06-18 | selfdev 루프 #7: --submit-clean 게이트 우회(R7/R9 HIGH) 수정 | 수정 app/auto_write/services/submission_orchestrator.py / 테스트 app/tests/test_submission_pipeline.py(신규 1) / 원장 R7 근거 | ultraqa 6차원 감사가 확정한 최상위 HIGH: submission_orchestrator 의 --submit-clean 산출물 _정리본(clean_out)이 artifacts 목록에 미등재(102/121/159만) → 수용검사 fail 시 fail 분기 루프(for old in artifacts)가 최종본을 못 잡아 _DRAFT 마킹 누락 → 제출불가 문서가 깨끗한 '_정리본' 이름으로 유출(게이트 우회). 수정: fail 분기가 artifacts 에 더해 항상 현재 final_docx(draft_targets)를 포함하도록 보강(이 인스턴스+미래 유사 누락 차단). 회귀: --submit-clean+강제 fail→final 이 _DRAFT.docx·draft_marked=True·비DRAFT 잔존 0. 검증: pytest 219 passed(신규 1, 회귀 0). 잔여 HIGH 차순위=bizplan_autopilot 검사예외 시 _DRAFT 세탁(fail-open) |
| 2026-06-18 | selfdev 루프 #8: bizplan_autopilot fail-open 차단 (R9 HIGH) | 수정 app/auto_write/services/bizplan_autopilot.py·app/bizplan_autopilot.py / 테스트 app/tests/test_auto_write_apply.py(신규 1) / 원장 R9 근거 | 감사 HIGH: bizplan 의 내부 autopilot 수용검사가 예외로 죽으면(검사불능) acceptance_verdict='' 라 최종 복사 가드(verdict and not submittable)를 건너뛰어 autopilot 이 건 _DRAFT 마킹이 깨끗한 _bizplan 이름으로 세탁되던 fail-open. 수정: BizplanReport 에 acceptance_error/draft_mark_error 필드 추가·ap 에서 전파, 최종 가드를 ap.draft_marked/acceptance_error/draft_mark_error 기반 needs_draft 로 강제(verdict 공백 예외 경로도 fail-closed), _build_todo 에 검사불능 노출, CLI --strict 를 acceptance_error/draft_mark_error→exit 3 으로 정렬(autopilot/submit/self_diagnose 계약 일치). 회귀: run_acceptance monkeypatch 예외→output_docx _DRAFT·draft_marked·깨끗한 이름 미생성. 검증: pytest 220 passed(신규 1) |
| 2026-06-18 | selfdev 루프 #9: submit_clean+required_format '_제출용_DRAFT' 모순명 방지 (R13) | 수정 app/auto_write/services/submission_orchestrator.py / 테스트 app/tests/test_submission_pipeline.py(신규 1) / 원장 R13 근거 | 감사 medium: --submit-clean 통과 시 _정리본→_제출용 승격(6.5-final) 직후 형식 게이트(7.5)가 형식 불일치면 _DRAFT 를 덧붙여 코드 주석(L188)이 금지한 '_제출용_DRAFT' 모순명 생성. 수정: 승격 조건에 format_ok(요구형식 미지정이거나 확장자 일치) AND — 불일치면 _정리본 유지 후 형식게이트가 _정리본_DRAFT 로 강등. 회귀: submittable+required_format=hwp→final 이 _정리본_DRAFT(_제출용 미승격). 검증: 신규 1 통과 |
| 2026-06-18 | selfdev 루프 #10: self_diagnose --json 저장 실패 시 종료코드 계약 오염 차단 (R9 low) | 수정 app/self_diagnose.py / 테스트 app/tests/test_usage_acceptance.py(신규 1) / 원장 R9 근거 | 감사 low: 진단(verdict) 산정·출력 후 --json write_text 가 나쁜 경로/권한으로 OSError 를 던지면 try 밖이라 미처리 예외→exit 1 로 0/1/2/3 계약 오염(진단은 이미 성공했는데). 수정: --json 저장을 try/except(OSError) 로 감싸 실패 시 stderr 경고만, 이미 산정된 종료코드(0/2) 그대로 반환. 회귀: 부모 폴더 없는 --json 경로→크래시 없이 rc∈{0,2}. 검증: 신규 1 통과 |
| 2026-06-18 | selfdev 루프 #11: R11 하이퍼링크 내부 유색 run 검출·교정 누락 보강 | 수정 app/auto_write/services/{usage_acceptance,doc_quality_ops}.py / 테스트 app/tests/test_usage_acceptance.py(신규 1) / 원장 R11 근거 | 감사 low: 검출(check_residual_colored_runs 의 p.runs)·교정(normalize_colored_text_to_black 의 findall(w:r))이 둘 다 단락 직계 run 만 봐서 <w:hyperlink> 로 감싼 파란 하이퍼링크형 안내문구가 R11 통째로 우회(검출·교정 같은 사각지대). 수정: 검출은 Run(_r_el,p) 로 p._p.findall(.//w:r) 순회, 교정은 para.findall(.//w:r) 로 확장(하이퍼링크/필드 안 run 포함). 회귀: 하이퍼링크 파란 run→검출 1·교정 1·교정후 0. 검증: 신규 1 통과 |
| 2026-06-18 | selfdev 루프 #12: 정규화기 표 셀 dedup id 재사용 버그 차단 (R11) | 수정 app/auto_write/services/doc_quality_ops.py / 테스트 app/tests/test_usage_acceptance.py(신규 1) / 원장 R11 근거 | 감사 #23: PR#29 에서 추가한 normalize_colored_text_to_black 의 셀 순회 _iter_all_paragraph_elements 가 비보호 id(cell._tc) 로 dedup → lxml proxy 참조 소멸 시 id 재사용으로 서로 다른 셀을 '이미 본 것'으로 오판(과소집계, 표 셀 유색 텍스트 누락 위험). 과거 검출기에서 겪은 동일 버그 클래스. 수정: 검출기 usage_acceptance._dedup_cells 와 동일하게 refs 리스트로 proxy 생존 유지(id 안정성)→검출↔교정 셀 순회 정합. 회귀: 표 셀 2칸 유색→검출 2·교정 2·교정후 0(감사 #22 표셀 미검증 갭 동시 해소). 검증: 신규 1 통과 |
| 2026-06-18 | selfdev 루프 #13: R12 분량 게이트(page_overflow) 실배선 — 죽은 코드 활성 | 수정 app/{self_diagnose,auto_write_autopilot}.py·app/auto_write/{submit.py,services/{autopilot_pipeline,submission_orchestrator}}.py / 테스트 app/tests/{test_usage_acceptance,test_auto_write_apply}.py(신규 2) / 원장 R12 근거 | 감사 #7: check_page_overflow 는 max_pages/ai_section_max 가 None 이면 비활성인데 실사용 진입점 3개(self_diagnose:83·autopilot_pipeline:296·submission_orchestrator:215)가 전부 AcceptanceConfig(blind_review=..)만 넘겨 분량 검사가 테스트 외 항상 죽은 코드 — 원장 R12'달성' 표기와 모순(사용자가 aijinjae 15p/2p 발동 수단 없음). 수정: 3개 CLI(self_diagnose/auto_write_autopilot/submit)에 --max-pages·--ai-section-max 추가 → run_autopilot·SubmissionPipeline.run·self_diagnose 시그니처 통해 AcceptanceConfig 로 전달. (page_overflow 는 SEV_WARN 이라 게이트 차단 아닌 경고 가시화.) 회귀 2(spy 로 CLI→config 전달 확인). 검증: 신규 2 통과 |
| 2026-06-18 | auto-dev: 감사 잔여 큐 처리(Q1~Q4) | 수정 app/auto_write/services/{bizplan_autopilot,usage_acceptance,autopilot_pipeline}.py·app/bizplan_autopilot.py / 테스트 {test_auto_write_apply,test_submission_pipeline}.py(신규 2) / 원장 R13 | auto-dev 오케 목표지정 모드로 ultraqa 감사 잔여 처리: ①Q1(#3/#12) bizplan 에 --required-format/--submit-clean 배선(시그니처+CLI+내부 run_autopilot 전달) → bizplan 경로도 형식게이트·정리 활성 ②Q2(#21) submit/SubmissionPipeline 형식게이트(required_format 불일치→_DRAFT) 회귀 테스트 ③Q3(#20) check_empty_table_rows 가 중첩 표(셀 안 표) 빈 행 미검출하던 것 _iter_all_tables 재귀로 보완 ④Q4(#19) autopilot ops_summary 에 유색→검정 정규화 건수 표기 추가. Q5(마스킹 영문 성명, uncertain)는 오탐 위험으로 사람검증 영역 분리. py-3.11 회귀 0 |
| 2026-06-19 | auto-dev: PR #30 병합 + 잔여 LOW(#18)·#24 수용 | 병합 PR #30(표셀 dedup·R12·bizplan·중첩표·R13테스트, master 7814b88) / 수정 app/auto_write/services/document_quality_orchestrator.py·원장 R11 | 검증된 열린 PR #30(228 passed) 병합으로 완료. #18: orchestrator report_md(사람용)에 단락서식통일·유색→검정 정규화 건수 표기 추가. #24(color 접근 except 침묵)는 FAIL 체크 오탐방지 방어동작이라 무변경 수용. Q5(마스킹 영문성명)·blind_review CLI 전파 회귀는 사람검증/코퍼스 영역 분리 |
| 2026-06-19 | docx↔hwp 변환 스킬 신규+오케 등록 | .claude/skills/docx-hwp-conversion·document-quality-orchestrator·CLAUDE.md | HWP 제출물 변환을 하네스 정식 단계로(평생목표=DOCX↔HWP 100% 일치도 측정→개선 루프). 기존 hwp_docx.py/hwp_docx_convert.convert 자산을 pushy 트리거 스킬로 래핑(3단 폴백·DOCX→HWP 한글 COM 대화형 전용·원본 미수정). 오케 데이터흐름에 입력단(HWP→DOCX)·출력단(DOCX→HWP) + 단계표 행 추가(doc-architect 변환시점 결정·doc-safety-guard 원본보존). 신규 에이전트·커맨드 없음. 문서만 수정(코드 무변경) |
| 2026-06-23 | selfdev 루프 #14(R14): US-3c 선도입 warn 3종 opt-in fail 승격 | 수정 app/auto_write/services/{usage_acceptance,autopilot_pipeline,submission_orchestrator}.py·app/{self_diagnose,auto_write_autopilot}.py·app/auto_write/submit.py / 테스트 app/tests/{test_usage_acceptance(신규 5),test_auto_write_apply(신규 1)}.py / 원장 R14 | 원장 R14: 괄호선택란(paren_choices)·라벨변형(empty_label_fields_ext)·빈그림칸(empty_image_slots) warn 3종 fail 승격. 단 '오탐 표면적 큼 — 음성 코퍼스 검증 후' 설계 주석대로 무조건 승격은 멀쩡한 문서를 거짓 제출불가로 만들 위험 → **AcceptanceConfig.strict_acceptance**(기본 False, 오탐 0 불변) + CLI **--strict-acceptance** opt-in 으로 구현(공고가 해당 항목 필수일 때만 하드 게이트). run_acceptance 사후 severity 승격(_PROMOTABLE_WARN_IDS 한정·property 동적 반영), self_diagnose/autopilot/submit 3 게이트 배선. 적대적 코드리뷰 SHIP(무회귀·범위한정·변이안전·스레딩 5축 PASS). py-3.11 **332 passed**(신규 6, 회귀 0). E2E: paren 결함 문서 기본 exit 0(제출가능)·--strict-acceptance exit 2(제출불가). 기본값 fail 승격은 음성 코퍼스 확보 후 차기 |
| 2026-06-23 | cross-form 자동채움: 이름(성명)류 필드 값-타입 가드 (실측 회귀) | 수정 app/auto_write/services/cross_form_autofill.py / 테스트 app/tests/test_cross_form_autofill.py(신규 6) | 실측(미래큐러스 A→오토라이트 B) 버그: 타깃 '대표자명'에 사람 이름이 아니라 역할서술 "기술개발, 특허전략 및 사업화 총괄"이 high 자동전사. 근본원인=소스 A 본문 "⑤ 사업 수행 체계"의 역할분담 서술 "대표자 : 기술개발…"을 `_extract_source` 본문 단락 보조추출이 `대표자=<역할>`로 추출→동의어 클러스터(대표자↔대표자명) high 매칭. 수정: match_fields high 경로에 이름 동의어 클러스터(rep=대표자) 타깃에 한해 값이 이름 모양 아니면(`_looks_like_name`: 20자 초과/콤마·및·가운뎃점·세미콜론·총괄·담당·수행·자문) `value_type` 강등→needs_confirm 노출(오매칭<빈칸). 비이름 필드(연락처 등)·실명·마스킹 ○○○는 무영향. 적대적 코드리뷰 SHIP(스코프·false-reject·데이터흐름·가시성 6축 PASS). py-3.11 337 passed(신규 6, 회귀 0). 실측 재검증: transcribed 3→2, 대표자명→needs_confirm(후보 대표자) |
| 2026-06-24 | cross-form 자동채움: 예시 플레이스홀더 빈칸승격 + 가짜타깃 필터 (recall, 멀티에이전트 설계·적대검증) | 수정 app/auto_write/services/cross_form_autofill.py / 테스트 app/tests/test_cross_form_autofill.py(신규 7) | 실측 진단(빈양식 B 27표 대조): B 신청기업표가 칸에 예시 플레이스홀더(`창업일=2000.00.00.`·`매출=000억원`·`출원=00건`)를 담고 있는데 find_target_fields 가 '칸이 완전히 비어야만' 타깃으로 봐(`if value_text: continue`) 예시문구 든 칸을 '이미 채워짐'으로 오인→영구 미충족(창업일↔A 개업연월일 등 채울 수 있는데 놓침). 또 표번호 '2/3/4'·예시라벨 '000 대표' 등 가짜타깃 잡음. 멀티에이전트 Workflow(4에이전트)가 플레이스홀더 판별규칙 설계·적대검증 — 치명결함(O마스크 OOO를 placeholder로 보면 GOOGLE/SOHO/O2O 영문 실단어 오판→실값 덮어쓰기) 발견·O마스크 제외 확정. 구현: `_is_obvious_placeholder`(3종만 — 불가능날짜 월·일둘다0/전부-0수량 `(?<![0-9,])`로 100억원·2,000명 배제/더미등록번호, **O마스크 제외**)로 PH칸 빈칸승격 + `_is_noise_label`(표번호·OOO·생략기호·안내문 드롭, R7 클러스터 라벨 절대보호) + 채움 직전 2중게이트(실값 절대 덮어쓰기 금지). 적대 코드리뷰 FIX_FIRST(수량라벨 오드롭·버전문자열 오판)→수정→재검증. py-3.11 345 passed(신규 7, 회귀 0). 실측 재검증: transcribed 2→3(창업일=2025년 03월17일 추가)·실값 덮어쓰기 0·잡음(2/3/4·000대표) 제거·미충족칸 정직표시(생년월일·매출 등 A에 값없어 빈칸=날조0). 날조0·오매칭<빈칸<덮어쓰기 불변 |
| 2026-06-24 | cross-form 자동채움: 선택칸(체크박스 □→■) 자동 체크 + 적대검증 보수화 (PR #44) | 수정 app/auto_write/services/cross_form_autofill.py·app/cross_form_fill.py / 테스트 app/tests/test_cross_form_autofill.py(신규 16) | 실측(미래큐러스 A→오토라이트 B): B '사업자 형태 □개인/□법인' 선택칸을 A 사업자구분='개인사업자'로 ■개인 자동 체크(기존엔 체크박스를 빈칸으로도 안 보고 무시). find_checkbox_targets(라벨+연속 □옵션 그룹 탐지)·match_checkbox_groups(보수 매칭)·_check_option_cell(□→■ run단위·멱등)·SYNONYMS 사업자형태 클러스터·CLI --no-checkbox·AutofillReport checkbox_checked/groups. 멀티에이전트 적대 코드리뷰(5차원→검증→종합) FIX_FIRST: 실제 결함 4건(부분문자열 매칭이 '개인정보보호'→개인·'법인영업'→법인·짧은값 '소'·예시값 '00법인' 오체크 / 하이퍼링크 □ 조용한 no-op) → 부분문자열 폐기·정규화 사전 환원 후 정확일치만·_is_obvious_placeholder 가드·.//w:r 순회로 수정. py-3.11 361 passed(신규 16, 회귀 0). 실측 ■개인 체크·□법인 보존·원본 미수정·transcribed 3 유지. 체크 기호 ■(사용자 선택) |
| 2026-06-24 | 하네스 신규: 빈 양식 자동완성·제출완성 (cross-form-submission) | .claude/agents/cross-form-filler.md(신규)·.claude/skills/cross-form-submission/SKILL.md(신규)·CLAUDE.md | 사용자 `/harness` 요청: 빈 new양식 + 완성본 A → 사실 항목 전사·검수해 즉시 제출 가능 완성(이미지=NotebookLM 프롬프트). Phase 0 감사로 기존 코드(cross_form_autofill·usage_acceptance·submission_orchestrator·image_apply·form_analyzer) 전부 재사용 확정 → 얇은 하네스 레이어만 신규. 신규 에이전트 cross-form-filler 1개(전사 전담) + 기존 6개 재사용(analyzer/quality-gate/postprocessor/safety-guard/architect/writer). 오케스트레이터 스킬 cross-form-submission(하이브리드: 결정론 CLI + 에이전트 판단, 5단계 분석→전사→보강→검수→완성·리포트). 사용자 설계 결정: '사실 재배열 전사' 먼저(날조0·즉시제출 직결), 서술 문장작성은 다음 단계 하네스([작성 필요] 칸이 그 작업큐). 요구사항 wiki .omc/wiki/cross-form.md 영구 저장 |
| 2026-06-28 | HWP/HWPX 원본 양식 '변환 왕복 없는' 직접 채우기 (PR #48 병합) | 신규 app/auto_write/services/{hwpx_fill,hwp_com_fill}.py·app/hwp_fill_direct.py·app/tests/{test_hwpx_fill,test_hwp_com_fill}.py | 사용자 요구 '원본 양식 훼손 없이 값만 입력'. HWPX(=ZIP/OWPML)의 section*.xml 값 칸 hp:t 텍스트만 수정하고 header.xml(서식)·BinData(이미지)·mimetype 바이트 보존→**양식 100% 유지**(한글 불필요·샌드박스 검증). 바이너리 .hwp 는 한글 COM 누름틀 PutFieldText(정직 degradation). 매칭은 cross_form_autofill 재사용(동의어·플레이스홀더·라벨가드)·날조0·실값/라벨 덮어쓰기금지·원본미수정(하드링크 samefile 차단)·원자적 쓰기. 적대검증 5렌즈→실결함 9건 수정(하드링크 out==in critical·cellAddr/colSpan 병합셀 값칸선택 high·replacements 보호·lxml proxy id 회피). py-3.11 395 passed(신규 34, 회귀 0) |
| 2026-06-28 | 표 양식 .hwp 원-커맨드 자동 파이프라인 (.hwp→hwpx→채움→.hwp) | 수정 app/auto_write/services/hwp_com_fill.py(fill_hwp_via_hwpx)·app/hwp_fill_direct.py(.hwp 기본 자동·--field 옵션)·app/tests/test_hwp_com_fill.py(신규 6) | selfdev: 실측—STAR·도보네비게이션 양식이 누름틀 0개 '표 양식'이라 .hwp 직접 필드채움은 0칸. 한글 COM 이 자기 네이티브 HWPX 로 저장/되돌리는 **무손실 변환**을 이용해 .hwp 하나만 넣으면 자동 변환→표칸 채움(hwpx_fill)→.hwp 복원. 원본미수정·원자적쓰기·구조보존 측정(표/행/셀 동일 확인). 실제 STAR.hwp E2E: 4칸 채움·표16/행40/칸121 동일·비어있지않은칸 67→71(정확히 +4)·출력 .hwp 에 값 4개 전부 보존·원본 미수정. py-3.11 신규 6(회귀 0) |