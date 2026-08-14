# RESUME.md — auto_write 세션 체크포인트

> 세션을 새로 시작하면 **이 파일을 먼저** 읽는다. 상세 트랙은 아래 링크.
> 최종 갱신: **2026-08-14** (항우연 STAR-Exploration 선정 후 할 일·발표평가)

## 한 줄 상태

**지금 문서 작업:** 항우연 「2026 STAR-Exploration」 **선정됨**. 사업화지원금은 최종발표 **상위 2팀만** (팀당 최대 1천만). 공개 공고에 **발표 배점표 없음** — 운영사 메일 평가표가 정본.
엔진 쪽: `pds2225/auto_write` 단일 정본. 입구 = **bizdoc-hub** / CLI = **auto_write_hub.py**.

## 지금 세션 (2026-08-14) — STAR-Exploration

| 항목 | 내용 |
|------|------|
| 사업 | 한국항공우주연구원 「2026 STAR-Exploration」 예비창업자 트랙 (경기도 스타기업 **아님**) |
| 운영 | 조슈아파트너스 `jp@jptnr.com` / **042-364-1002** |
| 사용자 상태 | **선정됨** (6팀 멘토링 vs 상위 2팀 지원금인지는 메일 미확인) |
| 지원금 | 상위 2팀만. 재료비·외주용역비. **지원기간 내 개인/법인 사업자등록 필수**. 예비트랙은 대행구매/위탁일 수 있음 |
| 발표평가 | 2026 공개 공고에 배점 숫자 없음. 공고 축 = 항공우주 기술 근거 · BM고도화 · 시장검증 · 시제품 구현 · IR · 창업일정. 2020 공고 작성축 = 팀역량 · 창의성/성장가능성 · 구현가능성 |
| 코드/양식 | 저장소에 공고·양식 없음. IR·평가표·견적 양식은 사용자 메일 |

**다음 세션에서 바로:** 운영사 메일(6팀인지 상위 2팀인지 + 평가표/IR 양식/발표시간)을 주면 슬라이드·사용계획서를 항목에 맞춰 작성. 없으면 `jp@jptnr.com`에 평가표 요청.

## 최근 완료

| 날짜 | 내용 | 근거 |
|------|------|------|
| 2026-08-14 | 항우연 STAR-Exploration 선정 후 할 일·발표평가축 정리 (배점 미공개) | 이 체크포인트 · 원장 A6 |
| 2026-08-02 | autowrite 잔여 자산 흡수 → `tools/injector/` | PR #100 merged |
| 2026-08-09~ | 도메인 리팩터(CORE/BIZPLAN/RESUME)·P0 배선·E2E | PR #114~#119 |
| 2026-08-11 | RESUME.md 신설 + 허브 맵·bizplan-orchestrator 스킬·죽은 커맨드 참조 정리 | 이 체크포인트 |

## 입구 (헷갈리면 여기만)

| 상황 | 쓸 것 |
|------|--------|
| "문서 도와줘 / 뭘로 처리해" (의도 불명) | 스킬 `bizdoc-hub` 또는 `/bizdoc` |
| PC·폴더 어디서든 채움·진단 CLI | `py -3.11 app/auto_write_hub.py env\|diagnose\|fill …` |
| 구 BizPlan Injector (JSON→DOCX) | `tools/injector/inject.py` / `run.sh` |
| 상세 라우팅표 | `docs/BIZDOC_HUB_MAP.md` |

## 남은 일 (우선순위)

0. **STAR-Exploration (사용자 진행 중):** 최종발표 IR / 상위 2팀이면 사업자등록+견적+사용계획. 평가표·양식 경로 대기 (A6)
1. **owner 수동**: `pds2225/autowrite` GitHub Delete (이미 archived, admin 토큰 없음)
   → https://github.com/pds2225/autowrite/settings
2. **실측 1건** (추천 시나리오 중 하나):
   - HWPX: `py -3.11 app/hwpx_submit.py 양식.hwpx -o 결과.hwpx --identity identity.json`
   - DOCX 품질: `py -3.11 app/auto_write_autopilot.py 문서.docx --submit-clean --strict`
   - 인젝터: `cd tools/injector && python3 -m pytest tests/test_v2.py -q`
3. **REQUEST_LEDGER** 실제출 확인 대기(A1~A5) + A6 평가표/IR 양식 — 경로/제출 여부는 사용자만 확인 가능
4. **보류**: HWPX 세로 라벨(c) — 코퍼스 수요 극소(AC6)
5. **보류**: SFT P3 후속·DOCX↔HWP 100% — 실사용에서 막힐 때

## 재개 명령

```text
이어서: 항우연 STAR-Exploration. 메일에서 6팀인지 상위 2팀인지, 평가표·IR 양식·발표시간을 주면 발표자료부터.
```

```powershell
cd D:\auto_write
git checkout master && git pull
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
- 작업 규약: `CLAUDE.md` · `AGENTS.md`

## 안전 불변

원본 미수정 · 날조 0 · fail 시 `_DRAFT` · 경로 광역 스캔 금지 · 테스트 `py -3.11`.
