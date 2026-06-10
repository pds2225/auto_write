# CLAUDE.md — auto_write 프로젝트 작업 지침

> `D:\auto_write` 전용. 정부지원사업 문서 자동생성 + 문서 품질 개선 하네스 프로젝트.
> 공통 지침(글로벌 CLAUDE.md)과 충돌 시 이 repo-local 규칙을 우선한다.
>
> **🔄 세션을 새로 시작했다면 `RESUME.md` 를 먼저 읽어라** — 진행 상태·남은 일·재개 명령이 있다.
> 작업을 잠시 멈추거나 컨텍스트가 무거워지면 "체크포인트 저장"으로 RESUME.md 를 갱신하고,
> 새 세션에서 "이어서"로 복원한다(session-resume 스킬).

## 프로젝트 개요

- 핵심: 양식 DOCX 분석 → AI 작성 → DOCX 렌더링 → 검수(`app/auto_write/services/`).
- 실행: 시스템 Python 3.11~3.13(venv 없음). `app/` 이 import 기준. AI 키 없어도 동작.
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
# 테스트
python -m pytest tests/test_document_quality_harness.py -q
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
`/auto-write-psst` · `/auto-write-images` · `/auto-write-finalize`

### 핵심 코드 (`app/auto_write/services/`)

doc_quality_ops · document_type_classifier · psst_check · infographic_suggest ·
doc_quality_score · document_quality_orchestrator (진입: `app/document_quality_orchestrator.py`,
`scripts/run_document_quality_harness.py`)

### 품질 게이트

100점 만점, 9항목(안내문구15/글머리표10/문단공백10/글자크기15/표10/강조10/유형구조15/PSST10/이미지5).
**90 우수 / 85 통과 / 70 보완 / 미만 실패.** 미달 시 최대 10회 보완 루프, 수렴 시 조기종료 후 수동확인 항목 명시.

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
