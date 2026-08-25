# CLAUDE.md — auto_write 프로젝트 작업 지침

> `D:\auto_write` 전용. 정부지원사업 문서 자동생성 + 문서 품질 개선 하네스 프로젝트.
> 공통 지침(글로벌 CLAUDE.md)과 충돌 시 이 repo-local 규칙을 우선한다.
>
> **🔄 세션을 새로 시작했다면 `RESUME.md` 를 먼저 읽어라** — 진행 상태·남은 일·재개 명령이 있다.
> 작업을 잠시 멈추거나 컨텍스트가 무거워지면 "체크포인트 저장"으로 RESUME.md 를 갱신하고,
> 새 세션에서 "이어서"로 복원한다(session-resume 스킬).
>
> **현재 상태(2026-08-11):** RESUME.md 신설 + 허브 맵(`docs/BIZDOC_HUB_MAP.md`)·
> `bizplan-orchestrator` 스킬·`/bizdoc` 커맨드로 입구 정리. autowrite 흡수는 PR #100 완료
> (원격 삭제는 owner 수동). 테스트는 반드시 `py -3.11 -m pytest` (기본 3.14 는 matplotlib 부재).
>
> **스킬 훅(전역):** 스킬을 만들게 한 **요청 원문**을 `description` 훅 최우선으로 넣는다.
> 텍스트 프롬프트에 자동으로 안 걸리면 효용이 줄어든다. 상세 `AGENTS.md` §7.

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
**session-resume**(이어서/세션마무리/체크포인트. RESUME.md SSOT. 일회성 배너는 스킬 아님)

### 커맨드 (`.claude/commands/`)

**에이전트 입구:** `/bizdoc` (= `bizdoc-hub`). **CLI 입구:** `app/auto_write_hub.py`.
맵: `docs/BIZDOC_HUB_MAP.md` · 체크포인트: `RESUME.md`.

`/improve-doc-quality` · `/auto-write-inspect` · `/auto-write-psst` ·
`/auto-write-images` · `/auto-write-autopilot` · `/auto-write-bizplan` ·
`/auto-write-analyze` · `/auto-write-selfdev`
> ※ `/auto-write-quality`(→`/improve-doc-quality` 와 완전중복)·`/auto-write-finalize`(→`/auto-write-autopilot` 로 흡수)는
> 2026-07-16 통폐합으로 아카이브(`~/.claude/skills_archive/20260716-autowrite-consolidation/`). CLI(.py)는 보존.

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
**90 우수 / 85 통과 / 70 보완 / 미만 실패.** 동일 문서 자동 보완은 최대 2회.
2회 후 목표점수 미달이면 현재 최고 결과를 유지하고 NEEDS_MANUAL_REVIEW로 종료.
동일 테스트/명령/failure signature 재시도 최대 2회.

**⚠ 이중 게이트:** 점수 게이트는 '서식 품질'만 본다. 제출 가능성은 별도의
**수용검사 게이트(usage_acceptance, R7/R8/R9)** 가 판정한다 — fail 결함(마커·자기삽입
블록·자리표시·미체크 선택란·공란 필수칸·유색 텍스트·폰트 혼용 등) 1개라도 있으면
출력명에 `_DRAFT` 강제(제출 금지). 점수 99 라도 `_DRAFT` 면 제출불가다.
진단: `python self_diagnose.py` (exit 0=제출가능/1=입력오류/2=제출불가/3=검사불능).

### 동일 실패 재시도 한도 (공통 Retry/Loop Guard)

동일 명령·동일 테스트·동일 failure signature·동일 수정 접근·동일 verifier 결과의 재시도는
**최대 2회**. 2회 반복되면 같은 방식으로 다시 시도하지 않고 다음 중 하나로 분류한다:
CODE_BUG(다른 접근 1회 추가 후 그래도 실패면 BLOCKED) · BASELINE_FAILURE(BASELINE_FAIL 기록,
다음 독립 TASK) · ENVIRONMENT/EXTERNAL(BLOCKED, 다음 독립 TASK) · TEST_BUG(테스트 자체 문제일
때만 최소 수정, 무한 재실행 금지) · UNKNOWN(제한된 조사 후 BLOCKED).

모든 TASK는 `PASS` / `NEEDS_MANUAL_REVIEW` / `BLOCKED` / `BASELINE_FAIL` /
`SKIPPED_WITH_REASON` 중 하나로 종료한다. `IN_PROGRESS` 로 무한 유지하지 않는다.

"중간 승인 질문 없이 계속 진행"의 의미: **동일 실패를 성공할 때까지 반복한다는 뜻이 아니다.**
하나의 TASK가 BLOCKED되면 가능한 다른 독립 TASK를 계속 수행한다(계속 진행 ≠ 무한 retry).

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

## 하네스: 지원사업 문서 단일 진입점 (bizdoc-hub)

**목표:** 스킬이 많아 헷갈리는 문제 해소 — 문서 작업 요청의 **입구를 1개**로 통일하고,
의도(분석/작성/채움/다듬기/변환/제출)를 파악해 알맞은 기존 스킬·CLI 로 자동 라우팅한다.
기존 스킬을 대체하지 않는다(직접 지목 호출도 계속 가능).

**트리거:** "지원사업 문서 도와줘", "문서 도와줘", "사업계획서 도와줘", "공고부터 제출까지",
"이 문서 뭘로 처리해", "어떤 스킬 써야 해", "문서허브", "bizdoc", `/bizdoc` — 또는 공고/양식/사업계획서
요청인데 어느 단계인지 불분명할 때 `bizdoc-hub` 스킬 사용.

**연계 흐름:** 분석(announcement-form-analysis) → 본문 작성(bizplan-orchestrator) →
값 채움(cross-form-submission | HWPX 직접: hwp_fill_direct/hwpx_submit | `auto_write_hub.py fill`) →
품질·검수(document-quality-orchestrator | hwpx_submit 게이트) → 제출본.
상세 맵: `docs/BIZDOC_HUB_MAP.md`. HWPX 파리티는 PR #60(2026-07-05) 기준.

---

**변경 이력**

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-07-13 | SFT 데이터 레이어 P0~P2 + 기업 Master JSON P3(슬1) 구축 (PR #74~#77) | 신규 app/auto_write/services/{generation_store,sft_export,company_extract}.py·app/{sft_export,company_master}.py·app/auto_write/services/learning_store.py(feedback/generation_traces 추가)·project_service.py·openai_client.py / 테스트 3종(test_generation_store·test_sft_human_approved·test_sft_export·test_company_extract) | 사용자 요구 '현행 자동작성 유지 + AI 입력/생성답안/사람 수정본을 자동 저장해 LoRA SFT 데이터 축적 + 기업정보 자산화'. 계획 wiki `.omc/wiki/auto-write-sft-master-json-2026-07-13.md`(정찰 4에이전트+적대검증 2에이전트). **P0**(#74) 생성 계측: `_complete_text` fail-safe 훅(로깅 실패가 AI 호출 안 깸·재시도 attempt=2)→generation_traces.jsonl(큰 본문 gen_blobs/<sha1> 해시참조)·generate 초입 입력스냅샷·ai_draft_snapshot(AI원문↔반영본)·answers_provenance(user/docx_seed/psst/ai/fallback/needs_confirm). **P1**(#75) 사람수정 캡처: feedback.jsonl·_capture_human_edits(save_project_form에서 P0 ai_draft_snapshot.reflected와 대조, **첫 divergence 게이트**로 사람 v1→v2 오라벨 방지, edited/draft_rejected). **P2**(#76) 학습셋 변환기+소비자: sft_export→sft_dataset.jsonl(chat, **사람승인본 우선**·rejected제외·dedup·--mask)+learned_snippets.json→`_suggest_learned_snippets`가 항목 라벨정확일치로 **AI 컨텍스트에만** few-shot 주입(폴백/문서 직접삽입 제외). **P3 슬1**(#77) 기업 Master JSON: company_extract(라벨정규화=cross_form_autofill 동의어 재사용·**숫자 사실값 보존**[extract_source_fields는 숫자 폐기라 미사용]·항목단위 provenance{file,raw_label}·confidence high/medium/conflict·불일치=conflict candidates·없으면 missing·전부 confirmed=false·하이픈무시 거짓충돌방지)+company_master.py CLI. **날조0·부수효과 fail-safe·기존흐름 무변경(계측만 추가)** 불변. 저장 workspace/learning·<project>/sft·workspace/companies(gitignore). py-3.11 810→**845 passed**(신규 29, 회귀 0). 각 단계 CLI/무키 E2E exit 0. 남음: P3 후속(페이지마커·양식커버리지·검수루프·생성 2단분리)·P4(비전·시각자료)·미결 5건 |
| 2026-07-13 | hwpx-doctor: 안 열리는 한글 파일 진단·자동수정(표 격자 결함) + 엔진 예방 배선 + 스킬 | 신규 app/hwpx_doctor.py·.claude/skills/hwpx-doctor / 수정 app/auto_write/services/hwpx_layout_fix.py(repair_table_grid·repair_all_table_grids·check_hwpx_semantics·finalize repair_grid 배선) / 테스트 test_hwpx_layout_fix.py(신규 5) | 실측: 박다솜 프로필 v3~v7 hwpx가 한글에서 안 열림(불러오기도 실패). 지난번 zip/XML 구문검증만으론 '정상' 오판(오답노트 L033) → 심층 의미검증(itemCnt·ID참조·표격자)으로 **표 격자 결함 확정**: 수행 프로젝트 표(4×3) 마지막 행 rowAddr가 2로 중복 지정(정상=3)→row2 6칸 겹침·row3 텅 빔→한글 열기 거부. 원인=채움 스크립트가 행 추가 시 rowAddr 미증가(v3부터). 수정본 생성→한글에서 열림 확인(원인 확정). **재발방지**: P0 validate_table_grid(검출)에 repair(교정) 추가 + `finalize_layout_hwpx(repair_grid=True 기본)`에 배선 → hwpx_submit 등 제출·마감 경로가 저장 직전 깨진 격자 자동교정(병합표 rowSpan/colSpan>1은 보호·멱등·원본미수정). on-demand CLI `hwpx_doctor.py diagnose|repair`(exit 0/2) + 전역 스킬 hwpx-doctor(안 열림 자동발동). py-3.11 신규 5·회귀 0 |
| 2026-08-02 | autowrite 잔여 고유자산 흡수 완료(run/docs/tests) + 통합 문서 정리; 원격 삭제는 owner 수동 | tools/injector/{run.bat,run.sh,docs/,tests/} · REPO_DUPLICATION_CHECK · ONBOARDING · run_auto_loop_15.bat | 사용자 요청: autowrite에만 있던 기능 가져오고 autowrite 삭제. 코어는 상위호환·인젝터 잔여 7파일 이전·원격 admin권한 없어 삭제 절차 문서화 |
| 2026-08-11 | RESUME.md 신설 + 허브·중복 정리(A): BIZDOC_HUB_MAP·bizplan-orchestrator 스킬·/bizdoc·죽은 커맨드 참조 정리·입구 가드 테스트 | RESUME.md · docs/BIZDOC_HUB_MAP.md · .claude/skills/bizplan-orchestrator · .claude/commands/bizdoc.md · test_hub_entrypoints.py · HANDOFF/PROJECT_REPORT/CLAUDE/AGENTS | 사용자 요청 3·4순위. 입구 이중(에이전트 bizdoc-hub vs CLI auto_write_hub) 역할 분리 문서화. 문서가 가리키던 bizplan-orchestrator 스킬 부재 해소. 아카이브 커맨드(/auto-write-quality·finalize) 잔존 참조 제거 |
| 2026-08-20 | session-resume 스킬 신설. 배너 스킬/후크는 일회성이라 철회 | 신규 `.claude/skills/session-resume/SKILL.md` · `.claude/hooks/session_resume_hook.js` · 삭제 promo-banner-localize | CLAUDE.md 가 session-resume 을 가리키는데 파일이 없음 = 매 세션 빈손. K-Navi 배너 한/영은 다음 요청 0회 예상이라 스킬·GenerateImage 후크 철회. 후크는 「세션마무리/이어서」만 |

> **이전 이력 35건은 [docs/CHANGELOG.md](docs/CHANGELOG.md) 로 옮겼다**(2026-07-20).
> 이 표가 파일의 80%(42KB)를 차지했고, `CLAUDE.md` 는 매 세션 통째로 로드되기 때문이다.
> **지운 것은 없다** — 전체 40건이 그 파일에 그대로 있다. 새 이력은 여기 맨 아래에 추가하고,
> 5건을 넘기면 오래된 것부터 `docs/CHANGELOG.md` 로 옮긴다.
