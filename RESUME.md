# RESUME.md — auto_write 세션 체크포인트

> 세션을 새로 시작하면 **이 파일을 먼저** 읽는다. 상세 트랙은 아래 링크.
> 최종 갱신: **2026-08-16** (#150 STEP 2 측정기 main 머지 `0a8b262` + 계획 보강)

## 한 줄 상태

`pds2225/auto_write` 단일 정본. `origin/main` @ `0a8b262` (#150 extraction baseline runner).
에이전트 입구 = **bizdoc-hub** / CLI 입구 = **auto_write_hub.py**. 맵: `docs/BIZDOC_HUB_MAP.md`.

**문서 작업:** 항우연 「2026 STAR-Exploration」 **선정됨**. 지원금은 최종발표 **상위 2팀만**. 공개 공고에 발표 배점표 없음 — 원장 A6.
**엔진:** T-20260814-02 명세+실행지시+BPQ-00 감사+#150 측정기가 main에 있음. DOCX 정본=`core.docx.services`.
**다음 엔진 작업 = 실문서 3 HWP × Golden 41 Baseline** (CompanyMaster EXTEND가 다음이 아님. PR #150은 측정기, 추출기 본체 아님).
작업 시작 전: `git fetch` → `TASK.md` → 현재 구현 조사 → 그다음 작업.
목표 흐름: `LLM → StageResult(JSON) → 검증 → 다음 Stage → 렌더 → Finalizer`. 한 번에 최종 DOCX 금지.

P 개발 중에는 요청 한 장(지금은 Problem만. 끝나기 전 S/Sc/T 금지. 파일 오면 초안 1건). **P 완료 후는 최우선 사용 케이스.** 사업자등록증은 첫 화면 필수 아님.

## 지금 세션 — STAR-Exploration (A6)

| 항목 | 내용 |
|------|------|
| 사업 | 한국항공우주연구원 「2026 STAR-Exploration」 예비창업자 트랙 (경기도 스타기업 **아님**) |
| 운영 | 조슈아파트너스 `jp@jptnr.com` / **042-364-1002** |
| 사용자 상태 | **선정됨** (6팀 멘토링 vs 상위 2팀 지원금인지는 메일 미확인) |
| 지원금 | 상위 2팀만. 재료비·외주용역비. **지원기간 내 개인/법인 사업자등록 필수** |
| 발표평가 | 2026 공개 공고에 배점 숫자 없음. 공고 축 = 항공우주 기술 근거 · BM고도화 · 시장검증 · 시제품 구현 · IR · 창업일정 |
| 코드/양식 | 저장소에 공고·양식 없음. IR·평가표·견적 양식은 사용자 메일 |

**다음:** 운영사 메일(6팀인지 상위 2팀인지 + 평가표/IR 양식/발표시간)을 주면 슬라이드·사용계획서. 없으면 `jp@jptnr.com`에 평가표 요청.

## 최근 완료

| 날짜 | 내용 | 근거 |
|------|------|------|
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
| PC·폴더 어디서든 채움·진단 CLI | `py -3.11 app/auto_write_hub.py env\|diagnose\|fill …` |
| 구 BizPlan Injector (JSON→DOCX) | `tools/injector/inject.py` / `run.sh` |
| 상세 라우팅표 | `docs/BIZDOC_HUB_MAP.md` |

## 남은 일 (우선순위)

0. **STAR-Exploration (사용자 진행 중):** 최종발표 IR / 상위 2팀이면 사업자등록+견적+사용계획. 평가표·양식 경로 대기 (A6)
0b. **엔진 다음 (측정, 구현 명령 시):** 실문서 D1–D3 HWP + `STEP2_EXTRACTION_GOLDEN_V1.json` 으로
   `python app/tools/step2_extraction_baseline.py --golden … --input-dir …`
   → `baseline_report`의 READ_MISS / STRUCTURED_EXTRACTION_MISSING / VALUE_ERROR / SOURCE_LOST 건수.
   Golden·HWP는 커밋 금지. Golden이 없으면 비교는 BLOCKED(41건 재구성 금지).
   이 세션: D1·D2 Drive 제목 일치 확보, Linux `unhwp` ingest는 PARTIAL 아님. D3·Golden 없음 → 41건 카운트 BLOCKED.
   그 건수를 기준으로 STEP 2 추출기(ITEM/PROBLEM/SOLUTION/BM/TEAM/FINANCE, ACTUAL/PLAN, Conflict, source 위치) 개발.
1. **owner 수동**: `pds2225/autowrite` GitHub Delete (이미 archived, admin 토큰 없음)
   → https://github.com/pds2225/autowrite/settings
2. **실측 1건** (추천 시나리오 중 하나):
   - HWPX: `py -3.11 app/hwpx_submit.py 양식.hwpx -o 결과.hwpx --identity identity.json`
   - DOCX 품질: `py -3.11 app/auto_write_autopilot.py 문서.docx --submit-clean --strict`
   - 인젝터: `cd tools/injector && python3 -m pytest tests/test_v2.py -q`
3. **REQUEST_LEDGER** 실제출 확인 대기(A1~A5) + A6 평가표/IR 양식 — 경로/제출 여부는 사용자만 확인 가능
4. **보류**: HWPX 세로 라벨(c) — 코퍼스 수요 극소(AC6)
5. **보류**: SFT P3 후속·DOCX↔HWP 100% — 실사용에서 막힐 때
6. **열린 draft:** 계획 보강 브랜치 `cursor/step2-baseline-run-e248` (docs). 원격 정본 = `main` + `backup/*`. 닫힌 #139 충돌 표시는 무시.

## 재개 명령

```text
이어서: 항우연 STAR-Exploration. 메일에서 6팀인지 상위 2팀인지, 평가표·IR 양식·발표시간을 주면 발표자료부터.
엔진: T-20260814-02 + #150 측정기가 main `0a8b262`. 다음 실측은 3 HWP × Golden 41 Baseline.
P 개발 중=Problem만. P 완료 후=최우선 사용 케이스. 사업자등록증은 첫 화면 필수 아님.
```

```powershell
cd D:\auto_write
git checkout main && git pull origin main
# 테스트 (반드시 3.11 — PATH 기본 3.14 는 matplotlib 부재)
cd app
py -3.11 -m pytest tests/test_archived_commands_not_resurrected.py tests/test_hub_entrypoints.py -q
py -3.11 auto_write_hub.py env
```

## 관련 문서

- 허브 맵: `docs/BIZDOC_HUB_MAP.md`
- autowrite 통합: `docs/REPO_DUPLICATION_CHECK.md`
- HWPX 파리티(B 완결): `docs/RESUME_hwpx_parity.md`
- 실사용 원장: `docs/REQUEST_LEDGER.md`
- BPQ 정밀화 대기 지식: `docs/BPQ_PIPELINE_INSIGHTS_20260815.md`
- 작업 규약: `CLAUDE.md` · `AGENTS.md`

## 안전 불변

원본 미수정 · 날조 0 · fail 시 `_DRAFT` · 경로 광역 스캔 금지 · 테스트 `py -3.11`.
