# RESUME.md — auto_write 세션 체크포인트

> 세션을 새로 시작하면 **이 파일을 먼저** 읽는다. 상세 트랙은 아래 링크.
> 최종 갱신: **2026-08-31** (이지비건 종합완료보고서 작업 완료 + PR #171 발견. repo 엔진 상태는 08-28 기준)

## 한 줄 상태

`pds2225/auto_write` 단일 정본. 교훈 잠금 **T-20260831-01** Wave A+B+C 가드는 `cursor/lessons-wave-bc-e71f` (Wave A PR #172 포함). JSON mechanized **60**/151, gap 7. 이어가기 프롬프트=`docs/LESSONS_LOCKDOWN_WAVES.md`. LIST는 `[~]` (JSON L048/L049/L050 본문 gap + L005 BLOCKED).

## 지금 세션 — 2026-08-31 (교훈 잠금 Wave B/C + 이어가기 프롬프트)

| 항목 | 내용 |
|------|------|
| 요청 | `승인요청하지않고 웨이브C? … 끝까지` + `+프롬프트` |
| 한 일 | `submission_gates` + fill/submit/수용검사/이력서/COM kill spy. 테스트 `test_lockdown_wave_bc.py`. coverage 49→60 |
| 안 한 일 | JSON L048 PDF합본 · L049 `제출/` 폴더 · L050 HWP+PDF 쌍(한글 COM). L005 픽셀(이 클라우드 한글 없음) |
| 재개 | 계획 파일의 「이어가기 프롬프트」를 그대로 붙인다. 승인 질문 금지 |

`pds2225/auto_write` 단일 정본. `origin/main` @ `5edd4f5` (#171 hwpx linesegarray 겹침버그 정식 수정 — 로컬 master는 아직 `2130493`, 1커밋 뒤처짐, `git pull` 필요). 이전 주: #170 M4 `gpt-image-1` 누락 생성 경로. 이번 주 #160·#164·#168·#169·#170·#171 병합.
에이전트 입구 = **bizdoc-hub** / CLI 입구 = **auto_write_hub.py**. 맵: `docs/BIZDOC_HUB_MAP.md`.
로컬 `master`도 `2130493`이며 `origin/master` 추적명은 사라짐. 미커밋: 이 체크포인트와 A9 미제출 종료 원장 2개 문서(보존, 커밋 여부 결정 필요).

**⚠ 2026-08-31 발견 — PR #171 (`fix(hwpx): 글씨 겹침 — linesegarray를 텍스트 변경 함수에서 즉시 제거`):** 오늘 다른 세션이 `_set_cell_text`/`_splice_run_text` 등 텍스트-변형 primitive에서 `hp:linesegarray`를 즉시 무효화하도록 엔진 자체를 고쳤다(로컬 master에는 아직 없음, `git pull` 필요). 이번 세션에서 이지비건 문서를 손스크립트로 고칠 때 발견한 것과 **같은 근본원인**(L002)이며, 앞으로 HWPX 채움 스크립트를 새로 짤 때는 이 엔진 함수를 재사용하고 별도로 손패치하지 말 것.

**밤샘 2026-08-19 → main #161:** AW-001 `[~]`. `run_to_final` + mechanized 가드(`build_lrule_guards`, unverifiable=0).
judgment/gap은 REVIEW_REQUIRED → FINAL 차단 유지. 웹앱·BPQ-00 제품 코드는 승인 전 대기. 공고+양식 오기 전 초안 대기.

**문서 작업:** 원장 A1~A7. A1 온랩 **접수**. A5 1인창조 **취소**. A6 STAR **선정**(6팀 멘토링, 상위2 지원금은 별도). 내비 KICXUP **선정**. 신청 원장=`docs/clients/user_applications.md`(채팅만, Google Docs 정리본 금지). 도보네비 카드=`docs/clients/dobonevi_card.md`.
**세션 마무리 신호:** `python scripts/session_closeout.py plant|status|sync-disk|ack|cancel`. 기본 커밋본 `due: false`.
**엔진:** T-20260814-02 명세+실행지시+BPQ-00 감사+#150 측정기+#155 git-sync(기준 브랜치=GitHub default/`main`)+#156(웹앱 사양·계획 보강·STEP 3A)+#161(DomainRouter→LRule→Hash→Finalizer 게이트)+#164(STAR 프레이밍 스킬)+#160(소셜벤처 본문)+#171(hwpx linesegarray 정식수정, origin에만)이 있음. DOCX 정본=`core.docx.services`.
**열린 작업:** 열린 PR 0건(파악 시점 기준, #171은 이미 merge됨). AW-001·웹앱은 승인 전 대기, A9 미제출 종료 기록은 로컬 원장 2개에 미커밋 보존. Cursor 클라우드 PR은 기본 draft.
**머지 주의:** Cursor 클라우드 PR은 기본 draft. GitHub 자동머지는 draft에서 불가. 머지 요청 시 Ready for review 후 `gh pr merge --auto --squash`.
작업 시작 전: `git fetch` → `TASK.md` → 현재 구현 조사 → 그다음 작업.
목표 흐름: `LLM → StageResult(JSON) → 검증 → 다음 Stage → 렌더 → Finalizer`. 한 번에 최종 DOCX 금지.

P 개발 중에는 요청 한 장(지금은 Problem만. 끝나기 전 S/Sc/T 금지. 파일 오면 초안 1건). **P 완료 후는 최우선 사용 케이스.** 사업자등록증은 첫 화면 필수 아님.
웹앱 실행 정본=`웹앱 최종 요구사항_20260816`. 승인 전 웹앱 제품 코드 대기.

## 지금 세션 — 2026-08-31 (이지비건 인천TP 기술지원단 종합완료보고서, repo 밖 개인문서 작업)

> 폴더: `OneDrive\...\20260630 이지비건 인천TP기술지원단배정\기술지원단 컨설팅보고서_이지비건\` — auto_write repo와 무관한 개인 문서 작업. 코드 변경 없음.

| 항목 | 내용 |
|------|------|
| 완료 ① | `제출자료\기술지원단 종합완료보고_이지비건 v2.hwpx` — 8페이지, 8개 항목 채움 + 글씨겹침 수정 + 돋움12pt(내가 채운 부분만) 적용 완료. **회차 날짜가 구버전(아래 ⚠ 참조), 정정 필요** |
| 완료 ② | `종합보고서\인천TP 기술지원단 종합완료보고서_경영컨설팅_이지비건_박다솜_v2.hwpx` — 32페이지 정식 완료본. `종합보고서` 폴더 전체 자료 반영, 오늘자 일정정합성수정본 기준으로 회차 날짜·내용 정정 완료. `hwpx_doctor.py diagnose` PASS. 원본 `.hwp`·다른 소스 문서 전부 미수정 확인됨 |
| ⚠ 다음 즉시 할 일 | ①의 8p본 회차 날짜(구: 1회차7/3·2회차7/20·3회차8/3·4회차8/21·5회차8/26)를 ②와 같은 정정 날짜(1회차7/3·2회차7/20·3회차7/25·4회차8/3·5회차8/8, 3회차=구조설계만·4회차=19p초안작성·5회차=그 초안검수)로 맞춰야 두 파일이 일치함 |
| [확인 필요] (날조 안 함) | 매출액, 연락처, 연간기대비용효과 6개 수치(신규고용/특허실용신안/기술력향상/매출액증가/생산성향상비용절감/수출수입대체효과) — 소스 문서 어디에도 확정값 없어 비워둠. 사용자 확답 대기 |
| 자동화 아님 | 증빙사진 삽입은 사람이 직접(32p본에 `[이미지/캡처 붙임 위치]` 마커 28곳 표시해둠) |
| 위키 저장 | `.omc/wiki` — "파일명 '최종'만 믿지 말고 내부 안내문구 먼저 확인"(예: `최종보고서.hwpx`는 사실 붙여넣기용 원고였음) |

## 자동화 브리핑 — 2026-08-28

- 캘린더: 기본 캘린더는 오늘 0건. `업무마감일`에 `한경련 더하기 창업 마감` 1건이 있으며 이벤트 시각 15:00과 설명의 18:00이 충돌하므로 15:00 전 원문 확인이 최우선. 캘린더 목록 권한은 부족하지만 config에 확인된 보조 캘린더는 직접 조회함.
- 중요 미확인 메일: `mail` workflow 4시간 후 실패와 P0 7개 수집원 누락, `walk` Vercel preview 실패 22건, Cursor GitHub App 추가 권한 요청, Kimi·Zoom Google 접근 및 Claude 신뢰 기기 확인, OpenAI Plus·Cursor 결제 실패 확인 필요.
- 오늘 할 일: ① 한경련 마감 여부 결정 ② 키핀 비즈니스지원단(D-1) 30분 착수 ③ mail-monitor·walk 반복 실패 원인 확인 ④ 계정 접근·구독 상태 확인. SIW(9/1~3)는 관심 프로그램만 사전등록 검토.
- 경계: Gmail/Calendar 읽기 전용 유지. 읽음 처리·회신·발송·캘린더 수정·권한 승인·결제 변경 없음. 제품 코드 수정 없음.
- 주간 검토: 8/24~8/28 PR 5건 병합·`docs-gate` 전부 통과. 소셜벤처 본문, STAR 출처 가드, draft 6건 합본, M4 복구 TASK와 이미지 누락 생성 경로 반영. 서울 AI 허브 2기 신청서는 작성했으나 미제출 종료.
- 다음 액션: A9 원장 기록 커밋 여부 결정 → AW-001·웹앱 승인 상태 확인. 자동화 보고 외 제품 코드 작업 없음.

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
| 2026-08-31 | 이지비건 종합완료보고서 8p본 완성(겹침수정·폰트) + 32p 정식본 완성(일정정정 반영). 8p본 날짜정정 남음 | `SESSION_RECAP.md` · 이 체크포인트 |
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

00. **이지비건 8p본 날짜정정:** `제출자료\기술지원단 종합완료보고_이지비건 v2.hwpx`의 회차 날짜를 32p본과 동일하게(3회차7/25·4회차8/3·5회차8/8) 정정 — 다음 세션 최우선. 이후 매출액·연락처 등 [확인 필요] 값은 사용자 확답 오면 두 파일 모두 반영
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
7. **로컬 master ↔ origin/main 동기화:** 로컬이 origin보다 1커밋(#171) 뒤처짐. 다음 세션 시작 시 `git pull origin main` 먼저 (RESUME.md 자체는 로컬 미커밋 버전이 더 최신 내용을 담고 있으니 pull 전 diff 확인).

## 재개 명령

```text
이어서: 스킬 `session-resume` + `RESUME.md`. 교훈 잠금은 `docs/LESSONS_LOCKDOWN_WAVES.md` 이어가기 프롬프트를 그대로 붙여 T-20260831-01 남은 JSON gap을 닫는다. 승인 요청 금지.
최우선 개인문서 = 이지비건 8p본(제출자료\v2.hwpx) 회차 날짜정정(00번 참조).
원장 A는 종료. 발표 IR은 새 요청이 있을 때만. 그때 위성항법을 항우연 보유기술처럼 쓰지 말 것(스킬 `tech-framing-provenance`, 2026-08-20 출처).
K-Navi: 16:9 한글/영문 배너는 Cursor artifact. 저장소에 넣을지는 사용자 확인. 재생성 요청이 오기 전에 스킬화하지 말 것.
스킬 훅: 만들게 한 요청 원문을 description 맨 앞. 스킬명만 부르면 효용 감소 (`AGENTS.md` §7).
엔진: T-20260814-02 + #150 측정기 + #155 git-sync(base=GitHub default/main) + #161 생산 게이트 + #171 hwpx linesegarray 정식수정(origin에만, pull 필요). main `9851ab3`. 합본 #156 squash `1001b76`. 세션핀 #158 `d6b96b8`.
P 개발 중=Problem만. P 완료 후=최우선 사용 케이스.
GitSync 기준 브랜치: AUTO_WRITE_GIT_BASE_BRANCH 없으면 origin/HEAD → ls-remote HEAD → main.
머지: draft면 자동머지 안 됨. Ready 후 gh pr merge --auto --squash.
```

```powershell
cd D:\auto_write
git pull origin main   # #171 hwpx linesegarray 정식수정 반영
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
