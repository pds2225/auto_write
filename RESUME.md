# RESUME.md — auto_write 세션 체크포인트

> 세션을 새로 시작하면 **이 파일을 먼저** 읽는다. 상세 트랙은 아래 링크.
> 최종 갱신: **2026-08-15** (BPQ 파이프라인 인사이트 저장, 다음 명령 대기)

## 한 줄 상태

`pds2225/auto_write` 가 단일 정본. `main` @ `9cffb24` (PR #137: autopilot LRule+Finalizer + E2E 15).
에이전트 입구 = **bizdoc-hub** / CLI 입구 = **auto_write_hub.py**. 맵: `docs/BIZDOC_HUB_MAP.md`.

**대기:** T-20260814-02 정밀화 지식 수신 중. 구현·TASK 본문 반영은 다음 명령. 저장본: `docs/BPQ_PIPELINE_INSIGHTS_20260815.md`.
핵심: 프롬프트가 아니라 `Facts → SectionContextPack → Draft → Self-check → QA → Approval → STALE 재검증 → Final`.
LRule ≠ QualityProfile ≠ PromptTemplate. 공란은 FactState. 비밀은 `.env`만.

## 최근 완료

| 날짜 | 내용 | 근거 |
|------|------|------|
| 2026-08-02 | autowrite 잔여 자산 흡수 → `tools/injector/` | PR #100 merged |
| 2026-08-09~ | 도메인 리팩터(CORE/BIZPLAN/RESUME)·P0 배선·E2E | PR #114~#119 |
| 2026-08-11 | RESUME.md 신설 + 허브 맵·bizplan-orchestrator 스킬·죽은 커맨드 참조 정리 | 이 체크포인트 |
| 2026-08-15 | overnight A–H 체리픽 main 머지 (LRule+Finalizer wiring, E2E 15) | PR #137 |
| 2026-08-15 | 배달앱 작성도구에서 단계형 파이프라인 인사이트 저장 (구현 대기) | `docs/BPQ_PIPELINE_INSIGHTS_20260815.md` |

## 입구 (헷갈리면 여기만)

| 상황 | 쓸 것 |
|------|--------|
| "문서 도와줘 / 뭘로 처리해" (의도 불명) | 스킬 `bizdoc-hub` 또는 `/bizdoc` |
| PC·폴더 어디서든 채움·진단 CLI | `py -3.11 app/auto_write_hub.py env\|diagnose\|fill …` |
| 구 BizPlan Injector (JSON→DOCX) | `tools/injector/inject.py` / `run.sh` |
| 상세 라우팅표 | `docs/BIZDOC_HUB_MAP.md` |

## 남은 일 (우선순위)

1. **owner 수동**: `pds2225/autowrite` GitHub Delete (이미 archived, admin 토큰 없음)
   → https://github.com/pds2225/autowrite/settings
2. **실측 1건** (추천 시나리오 중 하나):
   - HWPX: `py -3.11 app/hwpx_submit.py 양식.hwpx -o 결과.hwpx --identity identity.json`
   - DOCX 품질: `py -3.11 app/auto_write_autopilot.py 문서.docx --submit-clean --strict`
   - 인젝터: `cd tools/injector && python3 -m pytest tests/test_v2.py -q`
3. **REQUEST_LEDGER** 실제출 확인 대기(A1~A5) — 경로/제출 여부는 사용자만 확인 가능
4. **보류**: HWPX 세로 라벨(c) — 코퍼스 수요 극소(AC6)
5. **보류**: SFT P3 후속·DOCX↔HWP 100% — 실사용에서 막힐 때

## 재개 명령

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
- BPQ 정밀화 대기 지식: `docs/BPQ_PIPELINE_INSIGHTS_20260815.md`

## 안전 불변

원본 미수정 · 날조 0 · fail 시 `_DRAFT` · 경로 광역 스캔 금지 · 테스트 `py -3.11`.
