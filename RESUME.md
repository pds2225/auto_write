# RESUME.md — 세션 재시작 시 이어하기 진입점

> **새 세션을 시작하면 이 파일을 가장 먼저 읽어라.** auto_write 문서 품질 하네스 작업의
> 진행 상태·남은 일·재개 명령이 여기 있다. (최종 갱신: 2026-06-09 표 안내 배선)

## 🆕 2026-06-08 제출-100 이니셔티브 (브랜치 feature/submission-100-auto, 미병합)

기존 품질 하네스 위에 사용자 목표 3종을 구현했다(별도 브랜치, master 미병합).

- **Phase1 c040370 — 공고 평가 루프 종결:** `eval_loop_runner.py`(채점→취약섹션 재생성→재채점을 목표점수/수렴까지, 보수적 2회채점 하한, 매핑불가/근거부족은 needs_input 게이트로 허위생성 방지) + `project_service` 에 `_render_and_publish` 추출·`regenerate_sections` 신설 + `main.py /evaluate` 를 EvalLoopRunner 로 배선(하드코딩 converged=True 제거) + `config.py` Gemini 키 게이트(has_gemini).
- **Phase2 973efcd — 요약 인포그래픽 생성+배치:** `image_providers.py`(승인된 유료: Gemini "Nano Banana" gemini-2.5-flash-image 1순위 + OpenAI 2순위, 사진금지·요약 인포그래픽 강제) + `image_service` provider 체인(Gemini→OpenAI→matplotlib 원문수치차트→Pillow 카드, 무키 시 외부호출 0) + requirements(matplotlib, google-genai). 배치는 기존 image_slots→render add_picture 경로.
- **Phase3 b7f2bfb — end-to-end /goal:** `submission_orchestrator.py`(SubmissionPipeline: generate(텍스트)→평가루프→finalize→서식 quality gate→이미지 최후 삽입) + `plan_builder.py`(organization_profile/overview 라벨기반 자동 plan, 표좌표는 양식별 fill_plan.json 외부화) + `render_service.insert_images_into_docx`(이미지 최후 삽입) + CLI `python -m auto_write.submit`.

**검증:** pytest **81 passed**(기존 72 + 신규 9: eval 3 / image 3 / submission 3). 원본 미변경·백업 유지·무키 유료호출 0.

**실행(복붙):**
```powershell
$env:GEMINI_API_KEY="..."   # Nano Banana 인포그래픽용(선택; 없으면 무료 폴백)
cd D:uto_writepp
python -m auto_write.submit --project <project_id> --announcement-file "공고.txt" --target 95
```
전제: `<project_id>` 는 이미 양식 분석+폼 저장이 끝난 상태여야 함. 산출: `results\제출초안_<id>_품질.docx` + 콘솔 JSON 리포트(steps/eval/needs_input/images). 상세: `docs\submission-pipeline.md`.

**미병합·후속:** 브랜치 `feature/submission-100-auto` 미병합(원격 push/PR 미실행, 사용자 승인 대기). 후속 후보: 양식별 `fill_plan.json` 작성, 실키 end-to-end 1건 검증, NotebookLM 어댑터(현재 보조 위치).

---

## 0. 30초 컨텍스트

`D:\auto_write` 에 **문서 품질 개선 하네스**를 구축했다. 완성된 DOCX(사업계획서 등)를
백업→유형분류→결정론 후처리→PSST→이미지제안→100점 채점→게이트→리포트하는 파이프라인.
**코드·테스트·문서·git 완료**. 실제문서 검증 → 강조 튜닝(34d35b6) → **채점 동기화 완료**
(2026-06-06/07, 총점 49.2→88.2 누적+39점, pytest 72 passed). 남은 일: 안내문구 10/15(body critical=1 미삭제) 미세조정 선택사항.

**2026-06-07 에이전트 슬림화 완료(감사 78점 개선):** 에이전트 12→6 병합. 신규 6개
`doc-architect`(설계조율) / `doc-safety-guard`(백업+보안) / `doc-analyzer`(유형분류+PSST+인포그래픽) /
`doc-postprocessor`(안내문구삭제+서식정규화+강조) / `doc-quality-gate`(채점·게이트+회귀검수) / `doc-writer`(문서화).
기존 12개 삭제. **app/ 코드 무수정 → pytest 72 passed 회귀 없음 확인.** SKILL.md 데이터흐름·담당표,
커맨드 5개, CLAUDE.md 에이전트목록·변경이력 전부 새 이름으로 동기화(dangling 참조 0). 스킬 11개 평면 .md는 이번 범위 밖(유지).

**2026-06-08 ultrawork(공고 95점 결과물 + 이미지 직접 생성) 진행 중:**
- 목표: 공고 채점방식대로 95점+ 결과물 도출 + 필요한 이미지 직접 생성 기능 구현.
- ✅ **이미지 생성 기능 구현**: `app/auto_write/services/chart_generator.py`(간트·막대·꺾은선·조직도, matplotlib)
  + `chart_insert.py`(DOCX 삽입, in==out시 ValueError). 신규테스트 12 + 회귀 84 passed.
- ✅ **채점 엔진 연결**: `evaluation_service`로 미래큐러스 AI인재실증형 작성본 채점 = **90/100**(5항목 18/20).
- ✅ **95점 작성가이드**: `results\미래큐러스_95점_작성가이드_20260608.md`.
- **핵심결정(불변)**: 케이스A — 원문에 없는 수치 날조 금지(공고상 허위기재=형사처벌·환수·참여제한3년).
  90→95 갭은 전부 **미기재 실제값**(사업비 금액·시장수치·팀표 더미 `OO학 박사`)이라 **미래큐러스만** 채울 수 있음.
  차트는 AI텍스트채점엔 무영향(사람 심사위원용 가점). 배점은 공고·양식에 숫자 없어 5항목 균등 20점 적용.
- ✅ **보완본 생성 완료**: `results\miraequrus_보완_차트_20260608.docx` (간트·조직도 차트를 anchor
  '추진 일정'/'대표자' 위치에 정확 삽입). 재채점은 미실행(차트=AI텍스트채점 무영향이라 90 유지로 갈음,
  필요시 `scripts\eval_announcement_score.py` 재실행).
- 재개 스크립트(영구화): `scripts\{eval_announcement_score, build_chart_improved, extract_doc_data}.py`
  (원래 job tmp=휘발). 출력경로만 환경 맞게 수정 후 `$env:PYTHONPATH='D:\auto_write\app'`로 실행.

**2026-06-09 표 셀 안내문구 제거 배선 완료(table-guide-cleanup 워크트리):**
- `remove_table_guide_rows`(커밋 b9db76d) — 표 셀에 박힌 양식 안내문구를 보수적으로 삭제
  (안내전용표 통째삭제 / 혼합표 안내행만 제거 / 데이터표 보존, `_PURE_GUIDE_RE` 일관 기준, 이미지행·max_len 보호).
- ✅ **run_all 파이프라인 배선**: 함수·테스트(85 passed)는 있었으나 통합 실행기·오케스트레이터에 미연결이라
  실제 후처리 시 표 안내문구가 제거되지 않고 `table_guide_rows_removed`가 항상 0이던 갭을 해소. 3곳 연결 —
  `doc_quality_ops.run_all`(remove_guides 블록 호출) + `document_quality_orchestrator`(누적집계 161줄 + md리포트 "삭제한 표 안내 행").
- 검증: pytest **85 passed**, 배선 미니검증 `WIRING_OK / IDEMPOTENT_OK`(before2→after1, 재실행 추가 0).
- 남은 일: git 커밋 후 master 병합(사용자 승인 대기) — 브랜치 `worktree-table-guide-cleanup`, origin=github.com/pds2225/auto_write.

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
- [x] **SubmittableFiller 엔진** (2026-06-05) — `autowrite_repo` PR #15 병합 완료 (머지커밋 63e2282).
      미래큐러스 초기창업패키지(AI인재실증형) 제출 초안 DOCX 생성. 완료보고:
      `WORKS/완료보고_미래큐러스_초기창업패키지_AI인재실증형_20260605.md`
- [x] **Python 자동 문법 검사 훅** (2026-06-06) — `.claude/hooks/py_check.js` + `.claude/settings.local.json`.
      Write|Edit 후 py_compile 자동 실행, 오류 시 systemMessage 경고. 다음 세션부터 자동 활성.
      ⚠️ 현재 세션에서 처음 사용 시 `/hooks` 한 번 실행 필요.

## 3. 남은 작업 ⬜ (다음 세션에서 이어서)

- [x] **git 초기화 완료** (2026-06-06) — `git init` + `.gitignore` 보강(개인정보 `app/tmp_quality_input/`,
      중첩저장소 `autowrite_repo`/`Playground`, 별도번들 `bizplan-autofill-codex`/`compare_bundle_autowrite`/
      `tmp_render_check`, `*.zip`, `outputs`/`data`/`backup` 제외) → 첫 커밋 **d94c41f** (master, 181파일).
      원격 없음(push 안 함). git user=pds2225/ekth3691@gmail.com.
- [~] **실제 사업계획서 검증 1건 진행** (2026-06-06) — 미래큐러스 「초기창업패키지 AI인재실증형」 사업계획서.
      ⚠️ OneDrive 한글파일은 NFC/NFD 정규화 차이로 Python이 직접 못 엶 → `Get-ChildItem` 객체로 잡아
      ASCII 경로(`app/tmp_quality_input/`)에 복사 후 실행해야 함. 결과: **49.2/100 실패**.
      **핵심 오탐 확정: 과잉 강조 40.6%**(155단락 중 63단락 bold/underline). 정상은 5~15%.
- [x] **강조 로직 튜닝 완료** (2026-06-06) — 계획대로 비율 상한 적용. `emphasize_key_sentences` 를
      비율 기반 예산으로 재작성: `max_emphasis_ratio=0.15`(목표 5~15%), `hard_emphasis_ratio=0.30`(절대상한),
      **원본 포함 기존 Bold 단락을 예산에서 차감**(`budget = allowed_total - existing_bold`) → 멱등성 확보(재실행 0).
      `_NUMERIC_RE` 를 `[0-9０-９]`(실제 숫자 필수)로 강화 → 단독 한글 단위(개/회/점/위/차/명/건/배) 오탐 제거.
      길이 필터 4→8자. 헬퍼 `_para_is_bold`/`_bold_is_on`/`_run_has_text` 추가. (`max_emphasis` 는 기본 None 하위호환)
      - 검증: 미래큐러스 문서 강조 **40.6%→29.3%**(과잉강조 게이트 통과, 추가 0건 — 원본이 이미 29.3% 굵음),
        강조항목 **5→10점**, 총점 **49.2→54.2**. `pytest` **72 passed**. 오탐 단위검증 통과(숫자없는 키워드 미강조).
      - 동기화: 스킬문서 `.claude/skills/content-emphasis.md` 갱신(조건/예외/시그니처/점수반영).
      - git 커밋 완료 (2026-06-06) — **34d35b6** `fix: cap emphasis ratio in emphasize_key_sentences tuning`
        (`doc_quality_ops.py`, `content-emphasis.md`, `RESUME.md`).
- [x] **채점 vs 삭제 기준 불일치 해소 완료** (2026-06-06) — `doc_quality_score.py` 채점 스캐너 4곳 동기화.
      총점 54.2 → 79.2 (+25점, pytest 72 passed). 커밋 **fd21a06**.
      - `_scan_guide`: GUIDE_MARKER_RE("기재"·"예시"·"※" 오탐) → _PURE_GUIDE_RE(삭제기 기준) + 플레이스홀더RE
      - `_scan_empty_groups`: doc.paragraphs(표셀포함) → body 직계 순회, 표를 연속 카운터 리셋(false-positive 제거)
      - `_scan_table_ws`: cell.text(\n 오탐) → w:t 노드 수준 검사 + merged cell 중복 방지
      - 폰트 감점 공식: kinds threshold 4→6종, 계수 2.0→1.0 (정부양식 다양성 반영)
      - 커밋 **fd21a06** → **568ee57** → **829ebd5** 3단계 순차 수정.
      - 829ebd5: _scan_guide 도 body 직계만 검사(표 셀 cell.text 오탐 제거) → 88.2점(통과)
      재실행용 입력: `app/tmp_quality_input/miraequrus_aijinjae_20260601.docx` (gitignore됨, 개인정보).
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
