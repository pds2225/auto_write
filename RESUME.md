# RESUME.md — auto_write 세션 체크포인트

## 현재 세션 체크포인트 — 2026-09-17

### 압축 후 갱신 — 2026-09-18

- AUTONOMOUS NIGHT RUN 재개: `origin/main`과 현재 branch/worktree/TASK/REQUEST_LEDGER를 재검증한 뒤 안전한 작업만 계속한다.
- P0 작업 worktree: `D:\auto_write\_work\codex-p0-addendum-20260918`, branch `codex/p0-addendum-20260918`.
- 완료된 P0: 공통 `hwpx_integrity_gate`, validator 실행 상태·severity 집계, 제출 경로 fail-closed, fixed-cell `REVIEW_REQUIRED`, cross-form gate-bypass 회귀. 기존 COM 2회 무응답으로 rendering은 `ENVIRONMENT_BLOCKED` 유지.
- 마지막 검증: P0 targeted `56 passed, 2 skipped`, gate/bypass `10 passed`, HWPX acceptance/cleanup `36 passed`. 기존 DOCX submission hang과 resume/private re-export 실패는 TASK followup으로 분리.
- 이번 재개 다음 액션: remote/main/TASK 상태 재확인 → T-20260918-01 잔여 독립 검증 → 사람이 가능한 AW-001/AW-008/AW-003 중 현재 TASK에 명시된 안전 작업만 별도 worktree/commit으로 처리.
- 금지: root master dirty 변경·기존 worktree 보존, main/master push·merge, PR 재시도(gh 401), COM 추가 재시도, AW-009 승인 전 코드, OAuth/secret/외부 전송.

### 야간 실행 실측 갱신 — 2026-09-18

- 재검증: `git fetch origin --prune` 완료. `origin/main=f220d2d`, root `master=2130493`는 `origin/master` 제거 상태이며 기존 dirty 변경을 보존했다. root `TASK.md`의 #0 LIST와 열린 AW-001/AW-003/AW-005/AW-008/AW-009 8-1, `docs/REQUEST_LEDGER.md` C1을 확인했다.
- P0 worktree `codex/p0-addendum-20260918`는 clean, 원격 push SHA `2ebf550`; gate/bypass 재검증 `10 passed`. Hancom COM 2회 무응답은 계속 `ENVIRONMENT_BLOCKED`; 추가 시도 금지.
- AW-001 별도 worktree에서 실제 caller를 확인했다. `run_to_final`은 autopilot/resume/domain facade에 연결되어 있고 E2E `26 passed`; 기존 `ProjectService.generate → _publish_results_bundle`는 gate 미연결이지만 AW-009 승인 전 웹앱 코드 금지와 겹쳐 수정하지 않고 PARTIAL/FOLLOWUP로 남겼다. 넓은 보조 회귀는 origin/main 기존 실패 10건(acceptance 전달/옵션 전달/private re-export 등)으로 확인했다.
- AW-008 별도 worktree 실측: registry 151건, `mechanized=66`, `judgment=84`, `gap=1(L050)`; L050은 rhwp/renderer 의존으로 partial이며 관련 회귀 `28 passed`. DETERMINISTIC 신규 전환 없음.
- AW-003 별도 worktree 실측: registry → `LRuleEnforcer` → `LRuleReport.to_json()` → 기존 CLI/operator console 구조가 이미 존재. evaluator/CLI 기반 회귀 `19 passed`, console 핵심 `3 passed`; 새 UI/중복 registry는 만들지 않음.
- 생성 worktree: `D:\auto_write\_work\overnight-aw-001-20260918`, `overnight-aw-008-20260918`, `overnight-aw-003-20260918` 모두 origin/main 기준 clean 조사 브랜치이며 아직 코드 commit/push 없음.
- 다음 재개: P0 TASK 상태·RESUME 최종 동기화 → root dirty/master 변경 없이 결과 보고. 추가 자동 수정 후보는 AW-001 ProjectService gate 연결이지만 AW-009 승인 없이는 착수하지 않는다.

### AUTONOMOUS CONTINUE — 2026-09-18

- 사용자 보정: AW-001의 기존 ProjectService 출력 경로 gate 연결은 신규 웹 UI가 아니라 기존 엔진의 fail-closed 수렴 작업인지 재판정하고, 안전하면 구현한다. AW-009 승인 제한은 신규 웹앱 기능 개발에만 적용한다.
- 현재 구현 worktree: `D:\auto_write\_work\overnight-aw-001-20260918`, branch `codex/overnight-aw-001-20260918`, base `origin/main`. root master와 기존 dirty 변경은 건드리지 않는다.
- 구현 목표: `ProjectService.generate → _publish_results_bundle`의 DOCX/HWPX 출력이 기존 LRule/Hash/Finalizer 공통 경로를 우회해 FINAL처럼 노출되지 않도록 최소 fail-closed gate와 bypass fixture/test를 추가한다. 실제 렌더 COM은 재시도하지 않는다.
- 이전 조사 결과: domain/autopilot/resume 경로는 이미 `run_to_final` 연결. ProjectService 결과 bundle은 gate 미연결. 이 분기를 이번 턴에 구현 가능성 기준으로 검증한다.
- 다음: caller 계약·ArtifactBundle·기존 테스트를 읽고 최소 패치 → targeted regression → 관련 E2E → commit/push. 실패 시 같은 원인 2회 이내로 분류하고 TASK/RESUME에 남긴다.

- 사용자 요청: 현재 작업지시 파일 `TASK.md` 내용 확인.
- 원격 기준: GitHub default branch `main`, `origin/main`=`f220d2d`; 원격 `TASK.md` blob=`ad37279`.
- 로컬 상태: `master`=`2130493`, `origin/master`는 제거됨. 작업트리에 기존 미커밋 변경과 열린 worktree가 있어 보존 중이며, 이번 조회로 코드 파일은 수정하지 않음.
- 원격 TASK 요지: AW-001~009와 T-20260814-02, T-20260816-03이 미완료; 원장 C 최우선, named 신청서 작성은 TASK 등록 금지, 웹앱 코드는 승인 전 대기.
- 다음: 사용자가 원하면 원격 TASK의 특정 열린 항목 8-1만 추가 확인. 구현·머지·정리는 별도 요청 전 하지 않음.
- 추가 요청(2026-09-18): P0 안정화 Addendum을 적용해 실제 개발 실행을 재개. 원격 `main` 기준으로 확인한 결과 rowAddr 격자 검출·교정은 이미 존재하므로 재작성하지 않음. 루트 `master`는 `origin/main`보다 16커밋 뒤처지고 dirty 상태라 보존했으며, 격리 worktree `D:\auto_write\_work\codex-p0-addendum-20260918`와 브랜치 `codex/p0-addendum-20260918`을 생성함.
- 현재 다음 단계: 격리 worktree에서 기존 P0 테스트·공통 gate·fixed-cell/rendering/gate-bypass 상태를 조사하고, 중복이 아닌 최소 독립 작업만 `origin/main` 기준 TASK에 등록·추적.

### 병행 세션 — 2026-09-18 (L규칙 재발방지 설계 검증, 코드 미수정)

- 사용자 요청: "같은 잘못을 반복하지 않게" → "설계만, 코드수정 금지" → 범위를 "전"(산출물게이트+화면노출+서브에이전트검증)으로 확정 → "설계 검증만, 코드/TASK.md/lessons registry 수정 금지"로 재검증.
- 코드/TASK.md/`app/tests/lessons_coverage.json` 전혀 수정하지 않음(요청대로 설계·검증만). 이 항목은 위 P0 addendum 격리 worktree 작업과 **무관한 별개 트랙**이다(파일 겹치지 않음).
- 핵심 발견(실측): ①`lessons_coverage.json` 151건(mechanized 44/gap 21/judgment 86) — `category`는 구현상태 단일축이고 "부분자동"은 `mechanizable` 필드에 별도로 있음. ②`top_gaps` 프리앰블 6건 중 4건(L040·L013·L046·L010)이 이미 mechanized로 승격됐는데 프리앰블만 stale. ③AW-003("L규칙 한 화면")은 TASK.md `[ ]`(미착수)로 보이지만 실제로는 `LRuleConsoleService`+`operator_main.py`(`/console/lrules`)로 registry↔UI 편집 절반이 이미 구현돼 있었고, `LRuleEnforcer.evaluate_all()`(런타임 PASS/FAIL 판정)만 그 콘솔에 안 붙어 있음. ④L167(서브에이전트 완료보고 미검증)형은 이 레지스트리에 없지만, 이 repo `.claude/settings.json` 에 이미 `PostToolUse: Agent|Task` 훅(전역 스킬 `omc_post_tool_remind.py`)이 걸려 있어 최소 방어선 확장은 전역 정책 수정 없이도 가능성 있음(단, tool_response에 실제 tool_uses 값이 들어오는지는 미검증).
- 산출물: 위키 `.omc/wiki/aw-003-aw-008-l167-2026-09-18.md`(신규) · 스킬 `~/.claude/skills/omc-learned/lessons-coverage-ssot-sync.md`(재검토용 사전점검 절 추가).
- 제안했으나 미승인(다음 세션 착수 가능): P0=`lessons_coverage.json`에 `enforcement_mode`/`implementation_status` 필드 **추가만**(기존 필드 보존)+top_gaps stale 4건 정리 / P1=gap 15건 중 impact=high(L032·L049·L151·L096·L097) 가드 구현.


## 현재 작업 — 2026-09-07 H 스타트업 신청서

- 대상: 박다솜 예비창업자, 아이템 `MarketGate`.
- 원본 HWPX는 보존하고 `제출\H스타트업_신청서_박다솜_마켓게이트_서명전.hwpx`와 PDF를 별도 생성함.
- 신청서·사업계획서(4쪽)·서약서·개인정보 동의서를 작성했고 한글 2022 열기, PDF 변환, 구조·필수칸 검사를 통과함.
- 서명 3곳은 고의로 비워 두었고, `2026.12.31.(예정)` 창업예정일과 동일·유사 아이템 수상 이력은 사용자 최종 확인 필요.
- 현재 재개 지점: 작성본을 한글로 열어 사용자 육안 확인 후 불필요한 빈 페이지를 최소화하고 최종 검증.

> 세션을 새로 시작하면 **이 파일을 먼저** 읽는다. 상세 트랙은 아래 링크.
> 최종 갱신: **2026-09-02** (일일 브리핑 갱신, 제품 코드 변경 없음)

## 한 줄 상태

`pds2225/auto_write` 단일 정본. 원격 `origin/main` @ `f220d2d` (default branch `main`, #177 반영). 로컬 `master` @ `2130493`, `origin/master` 추적명은 사라짐.
에이전트 입구 = **bizdoc-hub** / CLI 입구 = **auto_write_hub.py**. 맵: `docs/BIZDOC_HUB_MAP.md`.
로컬 `master`도 `2130493`이며 `origin/master` 추적명은 사라짐. 미커밋: 이 체크포인트와 A9 미제출 종료 원장 2개 문서(보존, 커밋 여부 결정 필요).

**밤샘 2026-08-19 → main #161:** AW-001 `[~]`. `run_to_final` + mechanized 가드(`build_lrule_guards`, unverifiable=0).
judgment/gap은 REVIEW_REQUIRED → FINAL 차단 유지. 웹앱·BPQ-00 제품 코드는 승인 전 대기. 공고+양식 오기 전 초안 대기.

**문서 작업:** 원장 A1~A7. A1 온랩 **접수**. A5 1인창조 **취소**. A6 STAR **선정**(6팀 멘토링, 상위2 지원금은 별도). 내비 KICXUP **선정**. 신청 원장=`docs/clients/user_applications.md`(채팅만, Google Docs 정리본 금지). 도보네비 카드=`docs/clients/dobonevi_card.md`.
**세션 마무리 신호:** `python scripts/session_closeout.py plant|status|sync-disk|ack|cancel`. 기본 커밋본 `due: false`.
**엔진:** T-20260814-02 명세+실행지시+BPQ-00 감사+#150 측정기+#155 git-sync(기준 브랜치=GitHub default/`main`)+#156(웹앱 사양·계획 보강·STEP 3A)+#161(DomainRouter→LRule→Hash→Finalizer 게이트)+#164(STAR 프레이밍 스킬)+#160(소셜벤처 본문)이 main에 있음. DOCX 정본=`core.docx.services`.
**열린 작업:** GitHub 열린 PR #174 1건 확인. AW-001·웹앱은 승인 전 대기, A9 미제출 종료 기록은 로컬 원장 2개에 미커밋 보존. Cursor 클라우드 PR은 기본 draft.
**머지 주의:** Cursor 클라우드 PR은 기본 draft. GitHub 자동머지는 draft에서 불가. 머지 요청 시 Ready for review 후 `gh pr merge --auto --squash`.
작업 시작 전: `git fetch` → `TASK.md` → 현재 구현 조사 → 그다음 작업.
목표 흐름: `LLM → StageResult(JSON) → 검증 → 다음 Stage → 렌더 → Finalizer`. 한 번에 최종 DOCX 금지.

P 개발 중에는 요청 한 장(지금은 Problem만. 끝나기 전 S/Sc/T 금지. 파일 오면 초안 1건). **P 완료 후는 최우선 사용 케이스.** 사업자등록증은 첫 화면 필수 아님.
웹앱 실행 정본=`웹앱 최종 요구사항_20260816`. 승인 전 웹앱 제품 코드 대기.

## 자동화 브리핑 — 2026-09-02

- 오늘 일정: 10:00 뉴키즈인베스트먼트 밋업, 14:00 SK텔레콤 밋업. `업무마감일`은 오늘 0건. SIW·대전창경 상담은 9/3까지.
- 보안: Google 계정 복구 뒤 2단계 인증 제거 안내가 unread. 본인 요청 확인 후 즉시 2단계 인증 재설정 또는 보안 진단.
- 운영·비용: `export-monitor`가 8/31 이후 4회 실패(최신 9/2 09:26). `walk` Vercel 실패 unread 50건. Google Cloud ₩8,965 결제 확인 필요.
- 구독·마감: Xiaomi MiMo 취소 예정일은 오늘이나 취소 확인 메일 없음. 한투AC는 9/3 이벤트 13:00/설명 17:00 충돌 → 13:00 안전 마감. 9/3 Kimi, 9/4 Claude Max, 9/6 Skywork 결제 일정.
- 다음 액션: 11:00 Google 보안 확인 → MiMo 해지 확인 → export-monitor 최신 오류 확인 → 14:00 SKT 밋업 준비.
- 산출물: `D:\v_up\worklog\briefings\2026-09-02.md`. Gmail/Calendar 읽기 전용, 제품 코드 수정 없음.

## 지금 세션 — 2026-08-23 마무리

| 항목 | 내용 |
|------|------|
| 한 일 | `tech-framing-provenance`가 뭔지 확인. (공고에 맞춰 붙인 기술 문장 vs 보유·이전. IR에서 단정 금지.) 코드 추가 없음. |
| 이미 이 브랜치에 있는 것 (08-20) | 위성항법 출처=프레이밍. 스킬 수확. `AGENTS.md` §7 훅=요청 원문 우선. 가드 테스트 8 passed |
| 스킬 한 줄 | 도보네비는 보행 길찾기. STAR에 GNSS/KASS/KPS를 붙인 것은 공고 맞춤 말. 항우연 기술이전 원문 없음. |
| 쓰지 말 것 | IR에서 위성항법을 보유·이전·라이선스처럼 단정. 국방경진 특허를 STAR 근거로 섞기. |

원장 A는 종료(이미 제출). 발표 IR은 **새 요청이 있을 때만**. 그때도 아래 STAR 표·스킬을 따른다.

## STAR-Exploration (A6)

| 항목 | 내용 |
|------|------|
| 사업 | 한국항공우주연구원 「2026 STAR-Exploration」 예비창업자 트랙 (경기도 스타기업 **아님**) |
| 운영 | 조슈아파트너스 `jp@jptnr.com` / **042-364-1002** |
| 사용자 상태 | **6팀 멘토링 선정됨.** 상위 2팀(지원금)은 **아직 미선정** (2026-08-20 사용자) |
| 지원금 | 상위 2팀만. 재료비·외주용역비. 뽑힌 뒤에 사업자등록+견적+사용계획. **지원기간 내 개인/법인 사업자등록 필수** |
| 발표평가 | 2026 공개 공고에 배점 숫자 없음. 공고 축 = 항공우주 기술 근거 · BM고도화 · 시장검증 · 시제품 구현 · IR · 창업일정 |
| 코드/양식 | 저장소에 공고·양식 없음. IR·평가표·견적 양식은 사용자 메일 |
| 위성항법 출처 (2026-08-20 확인) | **항우연 기술이전·논문 원문 없음.** 2026-06-29 마감 당일 도보네비(보행 길찾기)를 공고 분야③(항우연 보유기술 활용)에 맞춘 프레이밍. 위키 `star-exploration.md`. GNSS/SBAS/KASS/KPS/PNT/IMU/PDR은 공개지식 조립. 제품 실체는 스마트폰 GPS 게이팅. 같은 주 국방경진은 별도 특허(10-1974002 등)—STAR에 쓰지 말 것. 당일 저녁 사용자 지시로 「측위 공백」프레이밍 폐기·위성영상 주축으로 교체했으나 **제출 PDF 제목은 여전히 위성항법**. 문장은 이후 KICXUP(케이네비)에도 재사용 |

**다음:** 원장 A 종료(이미 제출). 발표·지원금은 새 요청이 있을 때만. 그때 IR에서 위성항법을 **보유 항우연 기술처럼 단정하지 말 것**(연계·실증 추진만).

## 최근 완료

| 날짜 | 내용 | 근거 |
|------|------|------|
| 2026-08-25 | 열린 draft #159+#162+#163+#165+#166+#167 합본. 충돌 없는 #164+#160은 먼저 squash | 이 체크포인트 |
| 2026-08-23 | 신청 원장: KICXUP 선정 · 온랩 접수 · 1인창조 취소. 플레이북·도보네비 카드. 채팅만(Docs 정리본 금지) | `docs/clients/user_applications.md` · `user-bizdoc-playbook` |
| 2026-08-23 | 세션 마무리. 스킬 `tech-framing-provenance` 의미 확인(공고 맞춤 문장≠보유기술). 추가 구현 없음 | 이 체크포인트 · 위키 `session-2026-08-23.md` |
| 2026-08-23 | 원장 A1~A6 종료(사용자: 이미 제출). 웹앱은 승인 전 대기. AW-001 #161 main | 이 체크포인트 · `9851ab3` |
| 2026-08-20 | K-네비 9장 PPT는 Skywork 이관(불합격 아님). 스킬 `ir-storyboard-pptx`. Cursor 카드덱 재작성 금지 | `.claude/skills/ir-storyboard-pptx` · `docs/KNEVI_KICKXUP_SKYWORK_PROMPT.md` |
| 2026-08-20 | 케이네비 MVP 컷시트·16.5초 하이라이트. 스킬 `k-navi-mvp-highlight`. 보이는 것만(랜드마크/KASS 금지) | Drive `1_BUufLAantULLQkHEQshEAHMgxAcjxqz` · `.claude/skills/k-navi-mvp-highlight` |
| 2026-08-20 | K-Navi 배너 EN/KO 16:9 artifact(미커밋). `session-resume` 스킬 신설. `promo-banner-localize` 일회성이라 철회 | `.claude/skills/session-resume` |
| 2026-08-20 | 세션 마무리. STAR 위성항법=프레이밍(원문 없음). 스킬수확 `tech-framing-provenance` + 훅 규칙 §7 | Drive 위키 · `.claude/skills/tech-framing-provenance` · `AGENTS.md` §7 |
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
| "업무 절차 / 그대로 실행 / 도보네비 카드" | 스킬 `user-bizdoc-playbook` + `docs/clients/dobonevi_card.md` |
| "뭐 신청했지 / 아이템별로" | 스킬 `user-applications-memory` + `docs/clients/user_applications.md`. 채팅만. Docs 정리본 금지 |
| IR/피치덱 스토리보드 → PPT | 스킬 `ir-storyboard-pptx` + Skywork. Cursor python-pptx 카드덱 금지 |
| PC·폴더 어디서든 채움·진단 CLI | `py -3.11 app/auto_write_hub.py env\|diagnose\|fill …` |
| 구 BizPlan Injector (JSON→DOCX) | `tools/injector/inject.py` / `run.sh` |
| 상세 라우팅표 | `docs/BIZDOC_HUB_MAP.md` |

## 남은 일 (우선순위)

0. **STAR-Exploration:** 원장 A6 종료(선정·재작성 금지). 상위2 지원금·발표자료는 **새 요청이 있을 때만**. 그때 IR 위성항법=공고 맞춤 프레이밍(미보유 기술) — 과대포장 금지
0a. **K-Navi 배너:** 16:9 한글/영문은 Cursor artifact. 재생성은 요청 시에만(스킬로 고정하지 않음). 저장소/슬라이드 삽입은 사용자가 원할 때만
0a2. **K-네비 9장 PPT (A8):** Skywork 결과 검수 대기. Cursor가 카드덱을 다시 그리지 말 것. 프롬프트=`docs/KNEVI_KICKXUP_SKYWORK_PROMPT.md`
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
3. **REQUEST_LEDGER A:** A1~A6 재작성 금지(A5는 취소). A7 소셜벤처 리그 사용자 확인. A8 Skywork PPT 검수 대기. 웹앱은 최종계획 승인 전 코드 대기
4. **보류**: HWPX 세로 라벨(c) — 코퍼스 수요 극소(AC6)
5. **보류**: SFT P3 후속·DOCX↔HWP 100% — 실사용에서 막힐 때
6. **원격 정리:** `main` + `backup/*` 2개. 이 합본이 머지되면 흡수 draft #159+#162+#163+#165+#166+#167 닫음. 닫힌 #139 충돌 표시는 무시.

## 재개 명령

```text
이어서: 스킬 `session-resume` + `RESUME.md`. 원장 A는 종료. 발표 IR은 새 요청이 있을 때만. 그때 위성항법을 항우연 보유기술처럼 쓰지 말 것(스킬 `tech-framing-provenance`, 2026-08-20 출처).
K-Navi: 16:9 한글/영문 배너는 Cursor artifact. 저장소에 넣을지는 사용자 확인. 재생성 요청이 오기 전에 스킬화하지 말 것.
스킬 훅: 만들게 한 요청 원문을 description 맨 앞. 스킬명만 부르면 효용 감소 (`AGENTS.md` §7).
엔진: T-20260814-02 + #150 측정기 + #155 git-sync(base=GitHub default/main) + #161 생산 게이트. main `9851ab3`. 합본 #156 squash `1001b76`. 세션핀 #158 `d6b96b8`.
P 개발 중=Problem만. P 완료 후=최우선 사용 케이스.
GitSync 기준 브랜치: AUTO_WRITE_GIT_BASE_BRANCH 없으면 origin/HEAD → ls-remote HEAD → main.
머지: draft면 자동머지 안 됨. Ready 후 gh pr merge --auto --squash.
```

```powershell
cd D:\auto_write
git checkout main && git pull origin main
# 테스트 (반드시 3.11 — PATH 기본 3.14 는 matplotlib 부재)
cd app
py -3.11 -m pytest tests/test_archived_commands_not_resurrected.py tests/test_hub_entrypoints.py tests/test_skill_request_hooks.py -q
py -3.11 auto_write_hub.py env
```

## 관련 문서

- 허브 맵: `docs/BIZDOC_HUB_MAP.md`
- 기술 프레이밍 vs 보유기술: `.claude/skills/tech-framing-provenance/SKILL.md` · 위키 `tech-framing-provenance.md`
- 스킬 훅=요청 원문 우선: `AGENTS.md` §7 · 위키 `skill-request-hooks.md`
- 이 세션 위키: `session-2026-08-23.md` (Drive)
- autowrite 통합: `docs/REPO_DUPLICATION_CHECK.md`
- HWPX 파리티(B 완결): `docs/RESUME_hwpx_parity.md`
- 실사용 원장: `docs/REQUEST_LEDGER.md`
- 신청 원장(채팅만): `docs/clients/user_applications.md` · 스킬 `user-applications-memory`
- 도보네비 카드·절차: `docs/clients/dobonevi_card.md` · 스킬 `user-bizdoc-playbook`
- K-네비 IR PPT: `.claude/skills/ir-storyboard-pptx/SKILL.md` · `docs/KNEVI_KICKXUP_SKYWORK_PROMPT.md`
- BPQ 정밀화 대기 지식: `docs/BPQ_PIPELINE_INSIGHTS_20260815.md`
- 웹앱 실행 정본: `docs/AUTO_WRITE_웹앱_최종_요구사항_20260816.md`
- 작업 규약: `CLAUDE.md` · `AGENTS.md`
- 세션 재개/마무리: `.claude/skills/session-resume/SKILL.md`
- 위치×AI 마무리 깃발: `.claude/skills/session-closeout-all/SKILL.md` · `scripts/session_closeout.py`

## 안전 불변

원본 미수정 · 날조 0 · fail 시 `_DRAFT` · 경로 광역 스캔 금지 · 테스트 `py -3.11`.

## 2026-09-18 LONG DEVELOPMENT RUN v2 — checkpoint

- START_TIME: 2026-09-18 02:04:28 +09:00. AW-001 구현 branch `codex/overnight-aw-001-20260918`에 실제 코드·테스트·TASK 변경을 적용하고 push했다.
- AW-001 commits: `da81c5a` (ProjectService 공통 final gate 연결), `2c316fe` (malformed gate fault-injection). 주요 검증: targeted 3 passed, domain/LRule 26 passed, finalizer/LRule/hash 23 passed, compileall exit 0. 넓은 보조 회귀는 origin/main에서도 재현되는 기존 실패 10건.
- AW-008 실측: registry total 151, mechanized 66, judgment 84, gap 1(L050). L005/L008은 사람 판단·정책 예외, L050은 rhwp/한글 renderer 의존으로 신규 CLOSED 0건. 관련 28 passed. 별도 TASK 기록 branch `codex/overnight-aw-008-20260918`, commit `6098240` push.
- AW-003은 registry/evaluator/JSON/report/CLI 구조가 이미 존재하여 UI·중복 abstraction을 만들지 않았다. 기존 핵심 console 3건 및 LRule 기반 19건 PASS 증거를 유지한다.
- P0 `T-20260918-01`: gate/bypass 10 passed, HWPX acceptance/cleanup 22 passed 2 skipped. Hancom COM은 기존 2회 무응답으로 `ENVIRONMENT_BLOCKED`; 재시도 금지. `gh` PR 401은 HUMAN_GATE.
- 현재 남은 자동 가능 작업: AW-001의 HWPX R9 수용검사와 P0 HWPX gate는 별도 계약/branch로 분리되어 있어 혼합하지 않고, 관련 baseline triage·최종 diff audit을 계속한다.
## 2026-09-18 LONG DEVELOPMENT RUN v2 — final checkpoint

- 구현 완료: AW-001 기존 `ProjectService.generate → _publish_results_bundle`에 `run_to_final` 공통 gate와 `final_gate_report.json`을 연결했다. 게이트 실행 오류·malformed report는 `DRAFT`/비제출로 남는다. 브랜치 `codex/overnight-aw-001-20260918`, commits `da81c5a`, `2c316fe`, remote 동기화 완료.
- 구현 완료: AW-003 기존 registry/evaluator/CLI 구조의 registry test subprocess timeout/start failure를 `RuleTestResult(ok=false)`로 보존한다. 브랜치 `codex/overnight-aw-003-20260918`, commits `449c5d1`, `48be026`, `d77767c`, remote 동기화 완료.
- AW-008 실측: total 151, mechanized 66, judgment 84, gap 1(L050). L005/L008은 judgment/정책·렌더 의존, 신규 deterministic CLOSED 0건. 브랜치 `codex/overnight-aw-008-20260918`, commit `6098240`.
- P0 재검증: HWPX gate/bypass/acceptance/cleanup `32 passed, 2 skipped`; 실제 Hancom COM/render는 기존 2회 무응답으로 `ENVIRONMENT_BLOCKED`, 추가 재시도 금지. P0 브랜치 `codex/p0-addendum-20260918` clean, `2ebf550`.
- AW-001 관련 회귀: 신규 targeted `3 passed`, domain/finalizer/LRule `49 passed`. 넓은 10건은 origin/main에서도 재현된 `BASELINE_FAILURE`이며 이번 변경 회귀가 아니다. registry integrity는 lessons.md의 L152-L167과 coverage 151 불일치 등 기존 실패가 남아 있어 해당 registry를 임의 확장하지 않았다.
- AW-003 추가: operator console 전체는 30초 내 완료 증거를 얻지 못해 무한 재시도하지 않았고, 핵심 console `3 passed`, 신규 failure handling 포함 `5 passed`, LRule 회귀 `19 passed` 및 compileall exit 0을 기록했다.
- Git 안전: main/master 직접 push·merge·force 작업 없음. PR 생성은 기존 GitHub CLI HTTP 401 `HUMAN_GATE`로 재시도하지 않았다. root dirty 변경과 기존 worktree는 보존했다.
- 다음 자동 실행: 사용자가 승인한 경우에만 PR/merge를 진행하고, 그 전에는 P0 Hancom COM 환경 차단을 해소한 뒤 실제 렌더 smoke를 1회 검증한다.

## 2026-09-18 LONG DEVELOPMENT RUN v2 — post-final checkpoint

- 이후 AW-003 구현을 추가 검증했다: `69cbbe2`에서 부분 출력이 있는 registry timeout을 다루는 회귀 테스트를 추가했고, timeout/start-failure/partial-output targeted `3 passed`; 브랜치 원격 동기화 완료.
- AW-001 최신 targeted `3 passed`, 관련 domain/LRule/finalizer `49 passed`, fail-draft invariant `9 passed`; AW-003 관련 LRule 회귀 `19 passed`, compileall exit 0. 중단된 넓은 pytest 프로세스는 이 세션이 시작한 정확한 PID만 종료했고 다른 세션 프로세스는 건드리지 않았다.
- 현재 feature worktree 4개는 모두 clean이며 각 원격 feature branch와 동기화되어 있다. root `master`는 기존 사용자 변경과 `_work/`를 계속 보존한다.
- 종료 전 상태: P0 Hancom COM/render `ENVIRONMENT_BLOCKED`, AW-001/AW-003 구현 branch는 push 완료, AW-008 deterministic CLOSED 0건, PR 생성 `gh` 401은 `HUMAN_GATE`, main 직접 push/merge 없음.

## 2026-09-18 LONG DEVELOPMENT RUN v2 — final execution checkpoint

- AW-001 추가 구현: baseline 테스트의 잘못된 compatibility-wrapper patch를 core 모듈 patch로 바로잡고, legacy wrapper의 `_find_anchor`, `_RESIDUAL_RE`, `_build_todo`, `_write_report`, `_scan_guide`, `_is_guide_text` 노출을 복구했다. `test_auto_write_apply.py` `45 passed`, 문서품질+finalizer `42 passed`, 제출 파이프라인 `18 passed`, 통합 `96 passed`.
- AW-001 최신 커밋: `da81c5a`, `2c316fe`, `2a5117b`, `a60327a`, `e0723af`; branch `codex/overnight-aw-001-20260918` remote push 완료. 관련 broad 회귀 `71 passed`, ProjectService 관련 `76 passed` 및 compileall exit 0.
- 최종 root TASK 동기화: AW-001/AW-003 결과와 `REQUEST_SOLVED=NO`/PARTIAL을 반영했다. AW-008은 151건(`66/84/1`) 유지, 신규 CLOSED 0건이다. P0는 `32 passed, 2 skipped`, Hancom COM/render는 기존 2회 timeout으로 `ENVIRONMENT_BLOCKED` 유지.
- 종료 전 feature worktree 상태를 재확인하고 main/master에는 push·merge하지 않는다. root 사용자 변경과 테스트가 만든 무시 임시폴더는 보존/정리 경계에 따라 건드리지 않는다.

## 2026-09-18 LONG DEVELOPMENT RUN v2 — closeout evidence

- 최종 추가 검증: AW-003 operator console `28 passed`; AW-001 한글 기본 출력 `19 passed`, service resilience `12 passed`, architecture boundary `3 passed`, document ingest `7 passed`.
- 남은 baseline: generation store `5 passed, 2 failed` — `core.docx.services`에 기존 `generation_store` shim이 없어 trace 기록 테스트가 실패한다. AW-001 final-gate 범위 밖이라 이번 branch에 섞지 않았다.
- 최종 원격 확인: `origin/main=f220d2d3004e058c7a167d2f38174bb6f2b385d0`; 네 feature branch 모두 clean/원격 동기화. `nightcopy` remote는 `D:\_night_pilot\auto_write-copy`가 repo가 아니어서 fetch 실패했으며, origin 동기화에는 영향이 없다.

## 2026-09-18 FOLLOWUP LONG RUN 2 — start checkpoint

- 목표 순서: generation_store compatibility shim → 실제 caller 회귀 → AW-001 fault injection → AW-008 deterministic 후보 → lessons coverage 불일치 → cp949 portability → 단계적 full pytest.
- 기준 상태: AW-001 ProjectService gate와 AW-003 registry failure handling은 원격 feature branch에 반영됨. AW-008은 151건(`66/84/1`), 신규 CLOSED 0건. P0 Hancom COM은 기존 2회 timeout으로 재시도 금지.
- 이번 실행 1순위 baseline: `app/tests/test_generation_store.py`의 2개 실패. 기존 canonical implementation은 `app/auto_write/services/generation_store.py`, core caller의 `.generation_store` import shim 누락이 의심되며 로직 복제 금지.
- 현재 branch/worktree는 작업 시작 전 `origin/main`, dirty 사용자 변경, TASK/REQUEST_LEDGER를 확인하고 별도 feature branch를 사용한다. main push/merge·COM 재시도·AW-009 웹앱 코드는 금지.
- 다음 재개 명령: `py -3.11 -m pytest app/tests/test_generation_store.py -q --tb=short` 후 canonical/shim caller를 확인하고, 수정마다 targeted → related regression → commit → push.

## 2026-09-18 FOLLOWUP LONG RUN 2 — restored checkpoint

- 컨텍스트 복원 후 확인: 이번 후속의 1순위는 `app/tests/test_generation_store.py`의 남은 2개 실패이며, 원인은 `app/core/docx/services/openai_client.py`가 참조하는 `core.docx.services.generation_store` 호환 경로 누락으로 기록되어 있다.
- 기존 canonical 구현(`app/auto_write/services/generation_store.py`)을 재사용하는 최소 shim만 검토한다. 로직 복제·새 저장소 엔진·테스트 우회는 금지한다.
- 다음 실행: 현재 시각/branch/status를 기록하고, canonical API와 기존 compatibility shim 패턴을 확인한 뒤 failing test를 재현한다.

## 2026-09-18 FOLLOWUP LONG RUN 2 — continued after accidental pause

- 사용자가 승인 대기 중단을 정정했다. `generation_store` 호환 shim과 관련 회귀 수정은 Secret/OAuth/결제/배포가 아닌 기존 엔진의 안전한 코드 작업이므로 별도 승인을 요구하지 않는다.
- 직전 명령은 `git fetch`와 pytest 시작뿐이며 GUI/COM 호출은 없었다. 실행 중인 pytest가 남았는지는 다음 상태 점검에서 확인한다.
- 즉시 다음 액션: 현재 branch/worktree와 pytest 상태 확인 → generation_store 실패 재현 → canonical implementation을 재사용하는 최소 shim 구현.

## 2026-09-18 FOLLOWUP LONG RUN 2 — CP2 generation_store complete

- 실제 재현: `app/tests/test_generation_store.py`에서 `core.docx.services.generation_store` ImportError로 2건 실패.
- 수정: `app/core/docx/services/generation_store.py`를 추가해 canonical `auto_write.services.generation_store`와 동일 모듈 객체를 alias한다. 로직 복제·새 저장소 구현 없음. import identity 회귀 테스트를 추가했다.
- 검증: generation store/SFT/ProjectService/fail-draft 관련 `56 passed, 23 subtests passed`; `py_compile` 성공; `git diff --check` 경고 없음(라인엔딩 안내만 있음).
- 커밋/원격: `24104fd fix(compat): alias core generation store to canonical`, `codex/overnight-aw-001-20260918` push 완료, worktree clean.
- 다음: generation_store 실제 caller audit 및 ProjectService final-gate fault injection으로 진행한다.

## 2026-09-18 FOLLOWUP LONG RUN 2 — CP3 AW-001 HWPX fail-closed complete

- ProjectService의 기존 DOCX는 내부 중간본으로 유지하고, 기본 사용자 산출물 HWPX 생성 결과를 별도로 확인하도록 `_publish_results_bundle` 순서를 보강했다. 두 gate report 기록 전 결과 DOCX를 공개 폴더에 복사하지 않으며, HWPX emit 실패 시 gate report를 `DRAFT`, `final_output_allowed=false`, `submittable=false`로 강등한다.
- 테스트는 core converter 경로의 `hancom_com_available`을 false로 고정해 실제 COM 창을 띄우지 않는 XML HWPX fallback을 검증한다. COM/Hancom 실제 smoke는 기존 `ENVIRONMENT_BLOCKED` 정책으로 재시도하지 않는다.
- 검증: generation store + ProjectService `36 passed, 23 subtests passed`; HWPX default output `19 passed`; GUI 프로세스 잔존 없음. 커밋 `bc64e96 fix(project): fail closed when Hangul output is unavailable`, AW-001 branch push 완료.
- 다음: AW-008 registry의 judgment deterministic 후보를 실제 코드 근거로 판별하고, 조건을 모두 만족하는 경우에만 최대 2개 mechanization을 구현한다.

## 2026-09-18 FOLLOWUP LONG RUN 2 — CP4 AW-008 census / source mismatch

- `app/tests/lessons_coverage.json` 실측: total 151, mechanized 66, judgment 84, gap 1(L050). judgment 중 `mechanizable != no` 후보는 L005/L008뿐이며 각각 픽셀 검증·서식 정책 의존 `partial`이라 guard + fixture + runtime/final gate + metadata + 차단 증거 5조건을 충족할 수 없어 신규 CLOSED 0건을 유지한다.
- 외부 정본 `D:\.omc\agent-learning\lessons.md`에는 L152~L167이 있으나 repo registry에는 없다. registry integrity 테스트는 `10 passed, 3 failed`로 재현되었고, L163/L164는 외부 정본 내부 중복도 확인됐다. L154~L156은 기존 lockdown 규약상 JSON 미수록 skill-only다. 이 PHASE는 `BASELINE_DATA_MISMATCH`로 기록하며 숫자 맞추기용 registry 확장은 하지 않는다.
- 조사 파일·GUI·임시 프로세스는 생성하지 않았고, 파일 삭제도 하지 않았다.
- 다음: cp949/UTF-8 portability의 실제 실패 테스트와 production 파일 I/O 경계를 확인한다.

## 2026-09-18 FOLLOWUP LONG RUN 2 — compression restore checkpoint

- 압축 후 최신 기준을 복원했다. root `master`의 기존 dirty 변경과 AW-001/AW-008 전용 worktree를 보존하며, `origin/main=f220d2d`와 실제 branch/commit 상태를 기준으로 계속한다.
- AW-001 실제 구현 커밋 `24104fd`(generation_store compatibility alias), `bc64e96`(HWPX emit fail-closed)는 별도 feature branch에 존재하고 관련 테스트 근거가 있다. Hancom COM은 재시도하지 않고 `ENVIRONMENT_BLOCKED`를 유지한다.
- 현재 실행 목표: TASK.md와 코드/RESUME 동기화 감사 → cp949/UTF-8 portability 실패의 production/test 경계 판정 → 안전한 경우 별도 branch에서 최소 수정 및 회귀 검증. AW-008은 deterministic 조건을 충족하는 후보가 없으면 0 CLOSED로 유지한다.
- 다음 실행: `TASK.md` 관련 항목을 실제 코드/커밋 상태에 맞게 갱신한 뒤, session-resume 관련 실패를 기본 인코딩 환경에서 재현한다.

## 2026-09-18 FOLLOWUP LONG RUN 2 — CP5 TASK sync / CP6 portability

- TASK 동기화 감사: AW-001은 최신 코드/커밋(`24104fd`, `bc64e96`)이 기존 상세 기록보다 앞서 있어 처음에는 `CODE_AHEAD_OF_TASK`였고, 기존 항목에 검증 근거를 추가했다. 이후 AW-001의 구조/fail-closed 범위는 MATCH이며, HWPX R9/LRule 및 실제 Hancom 렌더는 `PARTIAL`/`ENVIRONMENT_BLOCKED`로 유지한다.
- AW-008은 registry `151 = mechanized 66 + judgment 84 + gap 1`과 일치한다. 외부 lessons 정본 `D:\.omc\agent-learning\lessons.md`의 L152~L167 미편입 및 L163/L164 내부 중복은 `BASELINE_DATA_MISMATCH`로 기록했고 registry 숫자 맞추기용 변경은 하지 않았다. 관련 검사는 `15 passed, 3 failed`이며 실패 3건은 이 baseline 불일치다.
- cp949 재현: 기본 Windows 인코딩에서 `test_session_resume.py::test_close_prompt_injects_skill`가 Node UTF-8 출력 해석 오류로 실패했다. `subprocess.run(..., encoding="utf-8")`를 테스트 하네스에 최소 적용한 `04a4750 test(session): decode hook output as UTF-8`을 별도 branch `codex/overnight-encoding-20260918`에 커밋·push했다. 기본 인코딩에서 session-resume/closeout `11 passed`, py_compile 통과.
- AW-001 별도 branch 재검증: ProjectService safety `28 passed, 23 subtests passed`; generation_store `8 passed`; domain/LRule/finalizer `41 passed`. HWPX acceptance 재실행은 점 출력에서 종료 증거가 남지 않아 `UNVERIFIED/HANG`으로 분류하고 같은 명령을 반복하지 않는다. COM은 재시도하지 않았다.
- 다음: root dirty 변경을 보존한 채 최종 diff/status, branch push, 임시 테스트 프로세스 잔존 여부를 확인하고 최종 TASK/RESUME 상태를 보고한다.

## 2026-09-18 FOLLOWUP LONG RUN 2 — CP7 final audit

- 최종 root 상태: `master`는 `origin/main` 대비 `16 behind / 0 ahead`, 기존 dirty 파일과 `_work/`를 보존했다. main/master push·merge는 하지 않았다.
- feature branch 원격 증명: AW-001 `bc64e96`, AW-008 `6098240`, encoding portability `04a4750`, P0 `2ebf550`; 네 worktree 모두 clean이며 원격 SHA와 일치한다.
- AW-008 신규 CLOSED는 0건이다. LRule 관련 검사는 `15 passed, 3 failed`; 3건은 외부 lessons source와 repo registry의 baseline mismatch로 분류했다. deterministic 조건을 충족하지 않는 L005/L008은 HUMAN_GATE/정책 예외로 유지한다.
- 임시 `pytest`/HWP/Hancom/Word/LibreOffice 프로세스는 최종 점검에서 0건이었다. 파일 삭제 없이 정리했고, 실제 COM은 재시도하지 않았다.
- 최종 판정: AW-001 구조/fail-closed는 MATCH, 실제 Hancom 렌더는 `ENVIRONMENT_BLOCKED`, AW-008은 `PARTIAL`, 전체 상태는 `PARTIAL`이다.

## 2026-09-18 파일/창 정리 checkpoint

- 상태: 코드 작업은 완료 보고 상태이며 root `master`의 기존 dirty 변경, feature worktree, 생성 파일을 보존한다.
- 결정: 조사·검증용 임시 파일은 삭제하지 않고, 임시 프로세스/뷰어만 확인 후 불필요한 경우 종료한다. 사용자 원래 창과 저장되지 않은 변경은 닫지 않는다.
- 확인: `D:\auto_write` 관련 pytest/Hancom/Word/LibreOffice/미리보기 프로세스는 남아 있지 않았다. 기존 Chrome/Notepad 창은 사용자 원래 창인지 구분할 수 없어 닫지 않았다.

## 2026-09-18 HWPX R9 Acceptance / Common Final Gate — 시작 checkpoint

- 사용자 요청으로 R9 수용검사와 공통 HWPX final gate 연결을 non-COM fixture로 검증·보강한다. 기존 AW-001 fail-closed, P0 gate, COM `ENVIRONMENT_BLOCKED`, AW-008 baseline mismatch는 유지하고 재작업하지 않는다.
- 문서 작업 등록은 별도 branch `docs/task-hwpx-r9-20260918`의 커밋 `9ea814e`로 완료·push했다. 코드 작업은 P0 공통 gate가 포함된 별도 R9 feature worktree에서 진행한다.
- 현재 계획: R9 FAIL/PASS/bypass 회귀를 먼저 failing test로 고정하고, 필요한 경우 `SubmitReport`의 final/submittable 상태 전달만 최소 보강한 뒤 관련 gate 회귀를 실행한다.
- Hancom COM과 실제 HWP 시각 렌더는 이번 작업에서도 재시도하지 않는다. 임시 창/프로세스는 검증 후 점검하고 사용자 원래 창과 파일은 보존한다.
