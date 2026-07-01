---
name: cross-form-submission
description: >-
  빈 새 양식 + 완성된 기존 사업계획서 → 기존 내용을 새 양식의 유사 칸에 자동 전사하고
  검수해서 "즉시 제출 가능한 상태"로 완성하는 오케스트레이터. 표 칸·본문 빈칸·선택칸
  (체크박스 □→■)을 채우고, A 에 없는 칸은 [확인필요]/[작성 필요]로 정직하게 남기며,
  그림칸은 NotebookLM 프롬프트로 대체(이미지 직접 생성 안 함)하고, 제출가능성 게이트
  (usage_acceptance)로 판정한다. 입력은 항상 2개(완성본 A + 빈 양식 B). 다음 요청 시
  반드시 사용: "빈 양식 채워줘", "이 양식에 옮겨줘", "기존 사업계획서로 새 양식 작성",
  "양식 자동완성", "새 양식 제출본 만들어줘", "A 내용으로 B 채워 제출가능하게", "cross-form",
  "전사해서 제출본 완성". 재실행·다시·수정·보완·부분 재실행(전사만/검수만)·needs_confirm
  확정·다른 양식으로 재전사도 이 스킬로 처리. ※ 완성된 DOCX 한 개를 '다듬기/검수'만 하는
  것은 document-quality-orchestrator, 빈 문서에서 '처음부터 작성'은 bizplan-orchestrator
  담당 — 이 스킬은 "완성본 A 의 사실을 빈 양식 B 로 옮겨 제출가능하게" 전용이다.
---

# cross-form-submission — 빈 양식 자동완성·제출완성 하네스 오케스트레이터

**완성본 A** 의 내용을 **빈 새 양식 B** 의 유사 칸에 옮기고, 검수해서 **즉시 제출 가능한 B**
를 만든다. 이 하네스는 "**사실 항목 재배열 전사**"를 담당한다 — 글을 새로 쓰지 않고, 이미
있는 값을 정확한 칸에 옮긴다. 새 문장이 필요한 서술 칸은 `[작성 필요]`로 표시해 다음
단계(문장작성 하네스/사람)로 넘긴다.

## 불변 원칙 (전 단계 공통)
- **날조 0** — A 에 실제 있는 값만. 없으면 비우고 `[확인필요]`/`[작성 필요]`.
- **오매칭 < 빈칸** — high(정확일치·동의어 단일)만 자동 전사. 애매·충돌은 사람 확정 후보로.
- **원본 미수정** — A·B 절대 보존(출력=입력이면 ValueError). 중간본은 `_workspace/`.
- **이미지 = NotebookLM 프롬프트** — 차트·그림 직접 생성 금지. 그림칸엔 슬라이드 프롬프트 삽입.
- **이중 게이트** — 서식 점수와 별개로, **제출가능성**은 usage_acceptance 가 판정한다.
  fail 결함(마커·자리표시·미체크 선택란·공란 필수칸·유색 텍스트·폰트 혼용 등) 1개라도 있으면
  출력명에 `_DRAFT` 강제(제출 금지). 점수 99 라도 `_DRAFT` 면 제출불가.

## 실행 모드: 하이브리드 (결정론 코드 CLI + 에이전트 판단)
전사·검수·완성의 **핵심은 검증된 결정론 코드**(cross_form_autofill · usage_acceptance ·
submission_orchestrator)다. 에이전트는 코드가 못 하는 **판단**만 맡는다 — 어떤 소스를 쓸지,
needs_confirm 후보 중 무엇을 확정할지, 못 채운 칸을 어떻게 분류·안내할지, 사람용 리포트 작성.
단일 1회 처리는 오케스트레이터가 CLI 를 순서대로 호출해 끝내고, 팀은 **판단·보완이 필요할 때**
(needs_confirm 다수, 게이트 반복 미달) 구성한다.

데이터 흐름 (에이전트: 신규 cross-form-filler 1 + 재사용 6):
```
[입력] 완성본 A + 빈 양식 B (둘 다 .docx/.hwp/.hwpx; 사용자에게 경로를 직접 받는다)
  → doc-safety-guard  : A·B 원본 백업 · 출력≠입력 확인 · 보안 게이트
  → doc-analyzer      : 빈 양식 B 구조 분석(채울 칸·표·체크박스·이미지 슬롯·서술 영역 구분)
  → cross-form-filler : A→B 자동 전사(표칸·본문빈칸·선택칸 □→■) · needs_confirm/unmatched 산출
  → doc-postprocessor : 그림칸 NotebookLM 프롬프트 삽입 · 사실 빈칸 [확인필요] · 서술칸 [작성 필요]
                        · 유색→검정/서식 정규화 (결정론, image_apply·doc_quality_ops)
  → doc-quality-gate  : usage_acceptance 제출가능 판정(self_diagnose) → fail 시 _DRAFT
  → doc-safety-guard  : 게이트 실패·오류 시 백업 복구
  → doc-writer        : 제출가능본 + 사람용 리포트(채운 칸 / 직접 입력할 칸 / 작성 필요 칸)
[출력] 제출가능 B(또는 _DRAFT + 할 일 목록). HWP 제출 필요시 마지막에 DOCX→HWP(한글 COM 전용).
```

## Phase 0: 컨텍스트 확인 (항상 먼저)
1. **입력 2개** 다 있는가? 완성본 A(소스)와 빈 양식 B(타깃) **경로를 사용자에게 직접 받는다**
   (광역 자동 스캔 금지). 하나라도 없으면 요청하고 멈춘다.
2. `_workspace/` 에 이전 산출물이 있는가?
   - 있고 **부분 재실행**("전사만 다시", "검수만", "○○ 칸 확정") → 해당 Phase 만 재실행.
   - 있고 **새 입력** → 새 실행(이전 `_workspace/` 를 `_workspace_prev/` 로 이동).
   - 없으면 → 초기 실행(전체 파이프라인).
3. A 와 B 가 **같은 회사/사업인지** 확인(소스가 타깃과 무관한 사업이면 채울 값이 적다고 안내).

## 표준 실행 (PowerShell)
```powershell
cd D:\auto_write\app
# 1) 전사 (핵심) — A 의 값을 B 의 유사 칸에 자동 채움(체크박스 포함)
py -3.11 cross_form_fill.py --source "A.docx" --target "B.docx" -o "..\WORKS\02_filled.docx"
#    needs_confirm 후보 확정: --confirm "타깃라벨=소스라벨" (반복 가능)
#    선택칸 자동체크 끄기: --no-checkbox
# 2) 제출가능성 검수 (게이트) — exit 0=제출가능 / 2=제출불가 / 3=검사불능
py -3.11 self_diagnose.py "..\WORKS\02_filled.docx"
# 3) 제출 완성(보강+게이트, 선택) — 서식 정규화·NotebookLM·게이트까지 무인
py -3.11 auto_write_autopilot.py "..\WORKS\02_filled.docx" --submit-clean --strict
#    HWP 제출이 필요하면 마지막에:
py -3.11 hwp_docx.py "..\WORKS\최종.docx" -o "..\WORKS\최종.hwp"
```

## Phase 1~5 (요약)
1. **분석(doc-analyzer)** — B 의 채울 칸 목록, 선택칸, 이미지 슬롯, 서술 영역을 구분해 산출.
2. **전사(cross-form-filler)** — `cross_form_fill.py` 실행. high 자동전사 + needs_confirm/unmatched
   구분. 결과를 `_workspace/02_*` 에 저장.
3. **보강(doc-postprocessor)** — 그림칸 → NotebookLM 프롬프트(image_apply), 사실 빈칸 → [확인필요],
   서술 칸 → [작성 필요], 유색→검정 정규화(doc_quality_ops). **숫자·문장 날조 금지**.
4. **검수(doc-quality-gate)** — `self_diagnose` 로 제출가능 판정. fail 결함 → 출력명 `_DRAFT` 강제 +
   결함 목록. needs_confirm 이 남았으면 사람 확정 후보로 노출.
5. **완성·리포트(doc-writer)** — 제출가능본(또는 _DRAFT) + **사람용 리포트**: ①자동으로 채운 칸,
   ②사용자가 직접 입력할 칸([확인필요]), ③새로 작성할 서술 칸([작성 필요]), ④제출 판정.

## 데이터 전달 프로토콜
- **파일 기반**(기본): `_workspace/{phase}_{agent}_{artifact}` — 예 `01_analyzer_structure.json`,
  `02_filler_report.json`, `02_filled.docx`, `05_writer_report.md`. 중간본 보존(감사 추적).
- **반환값 기반**: 각 에이전트 결과 요약을 오케스트레이터가 수집해 다음 단계 입력으로.
- 최종 산출물만 사용자 지정 경로에 출력. 원본 A·B 는 절대 그 경로로 덮어쓰지 않는다.

## 에러 핸들링
- 전사 0건/타깃 빈칸 0건 → "성공"으로 보고하지 않는다(ok=False + 구조 불일치 안내).
  세로형·단일열·전부 마스킹 양식일 수 있음 → 사용자에게 구조 확인 요청.
- HWP 변환 실패(한글 COM 부재) → DOCX 보존 + 사람 할 일 안내(예외 전파 금지).
- 검수 게이트 예외(검사불능) → **fail-closed**: 제출본 이름 금지(_DRAFT) + needs_input.
- needs_confirm/unmatched 는 **삭제하지 않고** 후보·빈칸을 그대로 보고(사람이 판단).
- 1회 재시도 후 재실패 시 해당 단계 없이 진행하되 리포트에 누락 명시.

## 테스트 시나리오
- **정상 흐름**: 완성본 A(사업자형태=개인사업자, 기업명·대표자 채워짐) + 빈 양식 B(사업자형태
  □개인/□법인, 기업명 빈칸) → 전사 후 기업명·대표자 채워짐 + ■개인 체크, A 에 없는 생년월일은
  [확인필요], 서술 칸은 [작성 필요], self_diagnose 가 잔여 결함을 _DRAFT 로 판정 → 리포트에
  "직접 입력할 칸 N개" 명시. 원본 A·B 미수정.
- **에러 흐름**: B 가 세로형이라 전사 0건 → ok=False + "구조 불일치(세로형/마스킹) 가능" 안내,
  사용자에게 양식 구조 확인 요청(거짓 성공 보고 금지).

## 관련 / 경계
- 엔진·CLI: `cross_form_autofill`·`cross_form_fill.py`(전사), `usage_acceptance`·`self_diagnose.py`
  (검수), `submission_orchestrator`·`auto_write_autopilot.py`(완성), `image_apply`(NotebookLM),
  `form_analyzer`·`announcement-form-analysis`(분석), `hwp_docx.py`(HWP 입출력).
- 경계: '완성 DOCX 다듬기'=document-quality-orchestrator / '처음부터 작성'=bizplan-orchestrator /
  '공고·양식 분석'=announcement-form-analysis. 이 스킬은 **A→B 전사 후 제출완성** 전용.
- 다음 단계(별도 하네스): 서술 칸([작성 필요])의 **문장 새로 작성**(AI, [확인필요]·[산출근거]
  가드). 이 하네스의 [작성 필요] 목록이 그 하네스의 작업 큐가 된다.
- 영구 목표·규칙: wiki `cross-form.md`, 메모리 cross-form-value-autofill-goal·autowrite-fill-goal·
  image-gen-notebooklm·bizplan-writing-rules.
