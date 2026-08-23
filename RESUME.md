# RESUME.md — auto_write 세션 체크포인트

> 세션을 새로 시작하면 **이 파일을 먼저** 읽는다. 상세 트랙은 아래 링크.
> 최종 갱신: **2026-08-23** (세션 마무리. 이 클라우드 창 상태만 저장. 다른 창 대화는 저장하지 못함)

## 한 줄 상태

`pds2225/auto_write` 단일 정본. `origin/main` @ `d6b96b8` (#158 핀, 기능 끝은 #156 `1001b76`).
에이전트 입구 = **bizdoc-hub** / CLI 입구 = **auto_write_hub.py**. 맵: `docs/BIZDOC_HUB_MAP.md`.

**문서 작업:** 항우연 「2026 STAR-Exploration」 **선정됨**. 지원금은 최종발표 **상위 2팀만**. 공개 공고에 발표 배점표 없음 — 원장 A6.
**마켓게이트:** 중기부 공고 제2026-482호 「모두의 창업:사회혁신 소셜벤처 리그」 솔루션 제안서 본문 = PR **#160** (draft). 접수 마감은 **2026-08-19 18:00 KST** — 이 체크포인트 시점(2026-08-23) 기준으로 **마감 지남**. 접수 여부는 사용자만 확인 가능.
**세션 마무리 신호:** PR **#167** (draft). `python scripts/session_closeout.py plant|status|sync-disk|ack|cancel`. 지금 깃발 `due: true` (이 클라우드에서 plant). `git pull` 한 다른 위치·AI는 자기 창만 `RESUME.md`에 쓰고 `ack`.
**엔진:** T-20260814-02 명세+실행지시+BPQ-00 감사+#150 측정기+#155 git-sync(기준 브랜치=GitHub default/`main`)+#156(웹앱 사양·계획 보강·STEP 3A)이 main에 있음. DOCX 정본=`core.docx.services`.
**열린 PR:** draft #159~#167 (아래 표). 원격 `main`은 #158까지.
**머지 주의:** Cursor 클라우드 PR은 기본 draft. GitHub 자동머지는 draft에서 불가. 머지 요청 시 Ready for review 후 `gh pr merge --auto --squash`.
작업 시작 전: `git fetch` → `TASK.md` → 현재 구현 조사 → 그다음 작업.
목표 흐름: `LLM → StageResult(JSON) → 검증 → 다음 Stage → 렌더 → Finalizer`. 한 번에 최종 DOCX 금지.

P 개발 중에는 요청 한 장(지금은 Problem만. 끝나기 전 S/Sc/T 금지. 파일 오면 초안 1건). **P 완료 후는 최우선 사용 케이스.** 사업자등록증은 첫 화면 필수 아님.
웹앱 실행 정본=`웹앱 최종 요구사항_20260816`. 승인 전 웹앱 제품 코드 대기.

## 지금 세션 — 2026-08-23 마무리

| 항목 | 내용 |
|------|------|
| 이 창 | Cursor 클라우드 `bc-e80d8d26-1fe8-4380-b4ca-1682353dfbf8` (에이전트명: 기보 모두의창업소셜벤처작설) |
| 한 일 | ① 소셜벤처 리그 솔루션 제안서 본문(과제4, 공고 2026-482 근거) → PR #160 ② 위치×AI 공통 세션마무리 깃발 → PR #167 ③ 이 창 체크포인트(본 파일) |
| 못 한 일 | 다른 PC·다른 AI·다른 채팅의 대화 원문 저장. 상대가 `git pull` 하기 전 깃발 전달. `D:\` 디스크 깃발 직접 확인 |
| 깃발 | `.session/closeout_due.json` `due: true` · requested_from=`cursor-cloud`. 각 창은 자기 `(agent, location)` 이 acks에 없으면 RESUME 갱신 후 `ack` |
| 다음(사용자) | 항우연 메일(6팀 vs 상위 2팀, 평가표/IR). 마켓게이트 접수 여부 확인. draft 머지 필요하면 Ready 후 `--auto` |

## STAR-Exploration (A6) — 변함 없음

| 항목 | 내용 |
|------|------|
| 사업 | 한국항공우주연구원 「2026 STAR-Exploration」 예비창업자 트랙 (경기도 스타기업 **아님**) |
| 운영 | 조슈아파트너스 `jp@jptnr.com` / **042-364-1002** |
| 사용자 상태 | **선정됨** (6팀 멘토링 vs 상위 2팀 지원금인지는 메일 미확인) |
| 지원금 | 상위 2팀만. 재료비·외주용역비. **지원기간 내 개인/법인 사업자등록 필수** |
| 발표평가 | 2026 공개 공고에 배점 숫자 없음. 공고 축 = 항공우주 기술 근거 · BM고도화 · 시장검증 · 시제품 구현 · IR · 창업일정 |
| 코드/양식 | 저장소에 공고·양식 없음. IR·평가표·견적 양식은 사용자 메일 |

**다음:** 운영사 메일(6팀인지 상위 2팀인지 + 평가표/IR 양식·발표시간)을 주면 슬라이드·사용계획서. 없으면 `jp@jptnr.com`에 평가표 요청.

## 마켓게이트 제안서 (PR #160)

| 항목 | 내용 |
|------|------|
| 공고 | 중소벤처기업부 제2026-482호 「모두의 창업:사회혁신 소셜벤처 리그」 |
| 마감 | 2026-08-19 18:00 KST (**지남**) · Kibo ONE |
| 과제 | ☑ 4. AI를 활용한 소상공인·중소기업의 생산성 및 혁신역량 제고 |
| 본문 | `docs/marketgate/20260819_소셜벤처리그_솔루션제안서_본문.md` |
| 브랜치 | `cursor/marketgate-proposal-body-fbf8` |
| 자격 확인(사용자) | 붙임4 동시수행 불가 13번=재도전성공패키지. 타 공모 수상·공개 아이디어면 제외. 대필 금지(AI 초안은 본인 검토) |

## 최근 완료

| 날짜 | 내용 | 근거 |
|------|------|------|
| 2026-08-23 | 이 클라우드 창 세션 마무리. RESUME 갱신 + closeout 깃발 plant(cursor-cloud). 다른 창은 pull 후 스스로 저장 | 이 체크포인트 / PR #167 |
| 2026-08-20 | 세션 마무리 깃발을 GitHub 파일로 공유 (로컬/클라우드/GitHub × Cursor/Claude/Codex) | PR #167 `scripts/session_closeout.py` |
| 2026-08-19 | 소셜벤처 리그(공고 2026-482) 솔루션 제안서 본문 5쪽 이내 | PR #160 |
| 2026-08-18 | 세션 마무리. GitSyncService `master` 하드코딩 제거(#155 already on main). draft면 자동머지 불가 확인 | PR #155 `ddac657` / #158 |
| 2026-08-16 | 열린 draft #149+#152+#153+#154 합본 #156 squash `1001b76`. #155는 `ddac657` | T-20260816-08 / PR #156 |
| 2026-08-16 | #150 STEP 2 추출 Baseline 측정기 main 머지. 추출기 본체 아님 | PR #150 `0a8b262` |
| 2026-08-16 | #146 BPQ-00 감사 main 머지. 원격은 main+backup 2개 | PR #146 `9efd78e` |
| 2026-08-16 | #138+#133+#139 합본 main 머지 (gitignore, L154–L156, A6, BPQ 노트, 합친 RESUME) | PR #141 |
| 2026-08-16 | git-sync push 검증/롤백 main 머지 | PR #140 |
| 2026-08-15 | overnight A–H 체리픽 (LRule+Finalizer wiring, E2E 15) | PR #137 |
| 2026-08-15 | 배달앱+상권분석 단계형 파이프라인 인사이트 저장 (구현 대기) | `docs/BPQ_PIPELINE_INSIGHTS_20260815.md` |
| 2026-08-14 | 항우연 STAR-Exploration 선정 후 할 일·발표평가축 정리 (배점 미공개) | 원장 A6 |
| 2026-08-11 | RESUME.md 신설 + 허브 맵·bizplan-orchestrator 스킬·죽은 커맨드 참조 정리 | 이 체크포인트 원본 |
| 2026-08-09~ | 도메인 리팩터(CORE/BIZPLAN/RESUME)·P0 배선·E2E | PR #114~#119 |
| 2026-08-02 | autowrite 잔여 자산 흡수 → `tools/injector/` | PR #100 merged |

## 입구 (헷갈리면 여기만)

| 상황 | 쓸 것 |
|------|--------|
| "문서 도와줘 / 뭘로 처리해" (의도 불명) | 스킬 `bizdoc-hub` 또는 `/bizdoc` |
| 세션 마무리·다른 위치/AI도 저장 | `python scripts/session_closeout.py plant` → 커밋·푸시. 상세 `.session/README.md` |
| PC·폴더 어디서든 채움·진단 CLI | `py -3.11 app/auto_write_hub.py env\|diagnose\|fill …` |
| 구 BizPlan Injector (JSON→DOCX) | `tools/injector/inject.py` / `run.sh` |
| 상세 라우팅표 | `docs/BIZDOC_HUB_MAP.md` |

## 남은 일 (우선순위)

0. **STAR-Exploration (사용자 진행 중):** 최종발표 IR / 상위 2팀이면 사업자등록+견적+사용계획. 평가표·양식 경로 대기 (A6)
0b. **엔진 / STEP 2 추출기:** 실문서 D1–D3 HWP + `STEP2_EXTRACTION_GOLDEN_V1.json` 으로
   `python app/tools/step2_extraction_baseline.py --golden … --input-dir …`
   → `baseline_report`의 READ_MISS / STRUCTURED_EXTRACTION_MISSING / VALUE_ERROR / SOURCE_LOST 건수.
   Golden·HWP는 커밋 금지. Golden이 없으면 비교는 BLOCKED(41건 재구성 금지).
   D1·D2 Drive 제목 일치 확보, Linux `unhwp` ingest는 PARTIAL 아님. D3·Golden 없음 → 41건 카운트 BLOCKED.
   출력 JSON은 `Fact[]` / `NarrativeEvidence[]` / `Conflict[]` 계약에 맞출 것.
0c. **STEP 3A (합본에 포함, 합성 fixture):** matcher Golden + 한글 리포트.
   `python3 -m pytest app/tests/test_section_matcher.py app/tests/test_step2_output_contract.py app/tests/test_step3a_golden.py -q`
   다음이 아님: Writer, Preview UI, HWP 렌더, STEP 3B 실공고 Golden.
1. **owner 수동**: `pds2225/autowrite` GitHub Delete (이미 archived, admin 토큰 없음)
   → https://github.com/pds2225/autowrite/settings
2. **실측 1건** (추천 시나리오 중 하나):
   - HWPX: `py -3.11 app/hwpx_submit.py 양식.hwpx -o 결과.hwpx --identity identity.json`
   - DOCX 품질: `py -3.11 app/auto_write_autopilot.py 문서.docx --submit-clean --strict`
   - 인젝터: `cd tools/injector && python3 -m pytest tests/test_v2.py -q`
3. **REQUEST_LEDGER** 실제출 확인 대기(A1~A5) + A6 평가표/IR 양식 — 경로/제출 여부는 사용자만 확인 가능
4. **보류**: HWPX 세로 라벨(c) — 코퍼스 수요 극소(AC6)
5. **보류**: SFT P3 후속·DOCX↔HWP 100% — 실사용에서 막힐 때
6. **열린 draft (2026-08-23 fetch):** #167 세션마무리 방송 · #160 마켓게이트 제안서 · #159 소셜벤처리그 빌더 · #161 AW-001 · #162~#166 타 세션 핀. 머지는 사용자 요청 시에만.

## 재개 명령

```text
이어서: 항우연 STAR-Exploration. 메일에서 6팀인지 상위 2팀인지, 평가표·IR 양식·발표시간을 주면 발표자료부터.
마켓게이트 본문: PR #160 `docs/marketgate/20260819_소셜벤처리그_솔루션제안서_본문.md` (마감 지남 — 접수 여부는 사용자 확인).
세션 깃발: git pull 후 python scripts/session_closeout.py status
  due true 이고 이 창이 아직 ack 아니면 RESUME 갱신 → ack --agent <cursor|claude|codex> --location <local|cloud|github> → 푸시.
  로컬 Claude: python scripts/session_closeout.py sync-disk --agent claude --location local
엔진: T-20260814-02 + #150 측정기 + #155 git-sync(base=GitHub default/main) main `ddac657`. 합본 #156 squash `1001b76`. 핀 #158 `d6b96b8`.
P 개발 중=Problem만. P 완료 후=최우선 사용 케이스.
GitSync 기준 브랜치: AUTO_WRITE_GIT_BASE_BRANCH 없으면 origin/HEAD → ls-remote HEAD → main.
머지: draft면 자동머지 안 됨. Ready 후 gh pr merge --auto --squash.
```

```powershell
cd D:\auto_write
git fetch origin
git checkout cursor/session-closeout-broadcast-fbf8
git pull origin cursor/session-closeout-broadcast-fbf8
python scripts/session_closeout.py status
python scripts/session_closeout.py sync-disk --agent claude --location local
# 이 창 저장이 아직이면 RESUME.md 확인 후
python scripts/session_closeout.py ack --agent cursor --location local
# 테스트 (반드시 3.11 — PATH 기본 3.14 는 matplotlib 부재)
cd app
py -3.11 -m pytest tests/test_session_closeout.py tests/test_hub_entrypoints.py -q
```

## 관련 문서

- 허브 맵: `docs/BIZDOC_HUB_MAP.md`
- 세션 마무리 신호: `.session/README.md`
- autowrite 통합: `docs/REPO_DUPLICATION_CHECK.md`
- HWPX 파리티(B 완결): `docs/RESUME_hwpx_parity.md`
- 실사용 원장: `docs/REQUEST_LEDGER.md`
- BPQ 정밀화 대기 지식: `docs/BPQ_PIPELINE_INSIGHTS_20260815.md`
- 웹앱 실행 정본: `docs/AUTO_WRITE_웹앱_최종_요구사항_20260816.md`
- 작업 규약: `CLAUDE.md` · `AGENTS.md`

## 안전 불변

원본 미수정 · 날조 0 · fail 시 `_DRAFT` · 경로 광역 스캔 금지 · 테스트 `py -3.11`.
한 창은 다른 창 대화를 저장했다고 말하지 않는다.
