---
description: 문서 품질 '수정'을 무인 연속 실행한다 - 백업+서식수정 → 이미지 실제 적용 → PSST 보강 → 점수/게이트 → 통합 리포트.
argument-hint: <입력DOCX경로> [--output 결과.docx] [--underline] [--placeholder-only] [--no-psst] [--max-images N] [--submit-clean] [--blind-review] [--required-format hwp] [--strict] [--no-acceptance] [--json]
---

# /auto-write-autopilot

## 사용 목적

완성된 정부지원사업 DOCX 를 **사람 개입 없이 한 번에 수정**한다. 진단만 하던 단계들을
실제 수정으로 잇는다.

1. **백업 + 서식 수정 + 점수/게이트** — `DocumentQualityOrchestrator`
   (양식 안내문구 삭제 · 글머리표/표 공백 정리 · 빈 단락 삭제 · 핵심문장 강조 · 100점 채점 · 85점 게이트)
2. **이미지 실제 적용** — `image_apply.apply_images`
   (표 실측치가 있으면 차트 생성·삽입, 없으면 자리표시 placeholder — 숫자 날조 없음)
3. **PSST 보강** — `psst_fill.apply_psst_scaffold`
   (누락/미흡 영역에 작성 뼈대 + 빠진 항목 체크리스트)
3.5 **(옵션) 제출 정리** — `--submit-clean`: NotebookLM 프롬프트를
   `<이름>_슬라이드프롬프트.md` 로 보존한 뒤 작업용 블록을 제거(손실 0)
4. **실사용 수용검사 게이트(R8)** — `usage_acceptance.run_acceptance`
   ([확인필요] 마커·자기삽입 블록·자리표시·미체크 선택란·공란 필수칸·유색 텍스트·
   폰트 혼용 등 **fail 결함이 1개라도 있으면 출력 파일명에 `_DRAFT` 를 강제**.
   `_DRAFT` = 제출불가 판정이니 그 이름 그대로/이름만 바꿔 제출하면 안 된다)
4.5 **(옵션) 산출 형식 게이트** — `--required-format hwp`: 최종 산출이 .docx 면
   `_DRAFT` 차단 + docx2hwp 변환 안내
5. **잔존 빈칸 스캔 + 통합 리포트(md/json)**

> ⚠ 수용검사·DRAFT 마킹으로 **최종 파일명이 `--output` 지정 경로와 달라질 수 있다**
> — 항상 리포트의 `output_docx` 를 최종 경로로 읽어라.

쉽게 말하면: 문서 하나를 넣으면 서식 정리·그림 삽입·빠진 작성 안내까지 알아서 해주고,
사람이 더 해야 할 일(To-Do)만 목록으로 돌려준다.

## 안전 원칙 (불변)

- **원본 절대 보존**: 1단계에서 원본을 `results\backup\<ts>\` 에 백업한다. 출력=입력이면 `ValueError`.
- **숫자 날조 0**: 문서에 있는 실측치만 차트화한다. 없으면 자리표시(빈칸)로 둔다.
- **점수는 서식 수정 기준**: 이미지/PSST 보강은 사람이 채울 '자리'와 'To-Do' 라서 점수를 부풀리지 않는다.
- 정부지원사업 문서 허위기재는 형사처벌·환수·참여제한 대상이므로 내용은 자동 생성하지 않는다.

## 입력값

- `input` (필수): 입력 DOCX 절대경로.
- `--output` / `-o` (선택): 최종 출력 DOCX. 미지정 시 `results\<원본>_autopilot.docx`.
- `--underline` (선택): 강조 시 밑줄 추가.
- `--no-emphasis` (선택): 핵심문장 Bold 강조 비활성.
- `--keep-guides` (선택): 양식 안내문구 삭제 비활성.
- `--normalize-fonts` (선택): 글자크기 이상치 보정 활성.
- `--max-images N` (선택): 이미지 적용 최대 개수(기본 8).
- `--placeholder-only` (선택): 차트 생성 없이 자리표시만(가장 안전).
- `--no-psst` (선택): PSST 작성 보강 생략.
- `--no-report` (선택): 통합 리포트(md) 생략.
- `--json` (선택): 결과 JSON 출력.
- `--submit-clean` (선택): NotebookLM 프롬프트를 md 로 보존 후 작업용 블록 제거(제출 정리).
- `--blind-review` (선택): 블라인드 공고 모드 — ○○○ 마스킹 허용 + 실명 잔존 검출(fail).
- `--required-format hwp` (선택): 요구 산출형식과 다르면 제출명 차단(_DRAFT)+변환 안내.
- `--strict` (선택): 종료코드 계약 — 0=제출가능 / 2=제출불가·게이트미달·형식불일치 /
  **3=검사불능(환경 문제 — 재시도·의존성 확인, 문서 수정 아님)**. 미지정 시 항상 0.
- `--no-acceptance` (선택): 수용검사 게이트(_DRAFT 마킹) 생략 — 작업 중간본 용도로만.

## 실행 워크플로우(단계)

1. 입력 DOCX 존재 확인. 없으면 "실행 막힘" 보고.
2. `cd D:\auto_write\app` 후 `python auto_write_autopilot.py "<입력>" [옵션]` 실행.
3. 산출물 확인: 결과 DOCX, 백업 폴더, 통합 리포트(md).
4. 통합 리포트의 총점·게이트·**수용검사 판정(제출가능/제출불가)**·차트/자리표시·
   PSST 보강·수동 To-Do 를 사용자에게 정리. 최종 경로는 리포트의 `output_docx`.

## 호출 에이전트

- `doc-architect`: 파이프라인 단계 조율.
- `doc-safety-guard`: 백업/롤백·원본 보존 확인.
- `doc-postprocessor`: 서식 수정·이미지 적용·PSST 보강(DOCX 변형).
- `doc-quality-gate`: 점수·게이트 판정.
- `doc-writer`: 통합 리포트·핸드오프 정리.

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 기본(서식+이미지+PSST 한 번에)
python auto_write_autopilot.py "C:\제출\사업계획서.docx"

# 2) 출력 지정 + 밑줄
python auto_write_autopilot.py "C:\제출\사업계획서.docx" --output "D:\auto_write\results\사업계획서_final.docx" --underline

# 3) 가장 안전(자리표시만, 차트 생성 안 함)
python auto_write_autopilot.py "C:\제출\사업계획서.docx" --placeholder-only

# 4) PSST 보강 생략 + JSON
python auto_write_autopilot.py "C:\제출\사업계획서.docx" --no-psst --json

# 5) 문제 시 원본 롤백
python document_quality_orchestrator.py --rollback "D:\auto_write\results\backup\20260608_120000" "D:\auto_write\results\사업계획서_final.docx"
```

## 실패 시 처리

- 입력 없음 → "실행 막힘" 보고, 절대경로 재요청.
- 출력=입력 동일(`ValueError`) → `--output` 다른 경로 지정 안내.
- 게이트 미달(70 미만) → 리포트 감점 사유 보고, 보완 후 재실행 안내.
- 수용검사 제출불가(`_DRAFT`) → fail 결함 목록 해결 후 재실행. NotebookLM 블록만
  원인이면 `--submit-clean` 으로 정리 후 재검사.
- `--strict` exit 3(검사불능) → **문서가 아니라 환경 문제**(의존성·파일잠금) — 재시도
  또는 `python self_diagnose.py` 수동 진단. exit 2 는 문서 결함(내용 수정).
- matplotlib/한글 폰트 경고는 치명적이지 않음(차트 None 이면 자리표시로 폴백).

## 보고 형식

첫 줄 상태(`정상 실행 확인됨` / `수정만 완료` / `미검증` / `실행 막힘`). 이어서:
1. 결과 DOCX 경로(절대경로)
2. 백업 폴더 경로
3. 통합 리포트 경로(md)
4. 총점·게이트(우수/통과/보완/실패)
5. **수용검사 판정(제출가능 / 제출불가(DRAFT) + fail 결함 목록)** — `_DRAFT` 면 제출 금지
6. 차트 N건 / 자리표시 M건 · PSST 보강 영역
7. 수동 보완 To-Do 목록
