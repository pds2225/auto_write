---
description: 완성 DOCX의 품질 개선 전체 파이프라인(백업→분류→후처리→PSST→이미지제안→점수→리포트)을 1회 실행한다
argument-hint: <입력DOCX경로> [--output 결과.docx] [--underline] [--keep-guides] [--normalize-fonts] [--no-emphasis] [--no-report] [--json] [--rollback BACKUP_DIR TARGET]
---

# /improve-doc-quality

## 사용 목적

완성된 정부지원사업 문서 DOCX(사업계획서·R&D연구개발계획서·발표평가·컨설팅·정책자금·인증·수출컨설팅·현장클리닉 보고서 등)의 서식·구조·강조·시각화 품질을 자동으로 끌어올리고, 100점 품질점수로 게이팅한다.
`app/document_quality_orchestrator.py` 를 1회 실행해 다음 파이프라인을 수행한다: 원본 백업 → 문서유형 분류 → 결정론적 후처리(`run_all`) → PSST 구조검사(business_plan·pitch_deck 한정) → 인포그래픽 제안 → 품질점수 산정 → 게이트 판정 → (미달 시 최대 10회 보완 루프, 수렴 시 조기종료) → 결과 DOCX 저장 → 리포트(md+json) 생성.

## 입력값

- `input` (필수): 입력 DOCX 절대경로. 예: `"C:\제출\사업계획서.docx"`. (단, `--rollback` 사용 시에는 생략 가능)
- `--output`, `-o` (선택): 출력 DOCX 경로. 미지정 시 `D:\auto_write\results\` 아래 자동 명명. **입력과 동일 경로 지정 금지(ValueError 발생).**
- `--underline` (선택): 핵심문장 강조 시 Bold에 더해 밑줄도 추가.
- `--keep-guides` (선택): 양식 안내문구 삭제를 비활성(기본은 삭제).
- `--normalize-fonts` (선택): 글자크기 이상치 보정 활성(기본 비활성).
- `--no-emphasis` (선택): 핵심문장 Bold 강조 비활성(기본은 강조).
- `--no-report` (선택): 리포트(md/json) 생성 생략.
- `--json` (선택): 결과를 JSON 으로 출력.
- `--rollback BACKUP_DIR TARGET` (선택): 백업 디렉토리에서 TARGET 으로 원본 복구(별도 모드).

## 실행 워크플로우(단계)

1. 입력 확인: 사용자가 준 DOCX 경로가 실제로 존재하는지 확인한다. 경로에 공백이 있으면 큰따옴표로 감싼다.
2. 작업 디렉토리 이동: `cd D:\auto_write\app` (이 경로가 `app/` sys.path 기준).
3. 전체 파이프라인 실행: `python document_quality_orchestrator.py "<입력DOCX>"` 에 사용자가 요청한 옵션을 덧붙여 실행한다.
   - 내부적으로 `DocumentQualityOrchestrator.run(input_docx, output_docx=None, emphasize=True, underline=False, remove_guides=True, normalize_fonts=False, write_report=True)` 가 호출된다.
   - 백업: 후처리 전 원본을 `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` 에 복사한다(원본 절대 덮어쓰기 금지).
4. 게이트 판정 확인: 출력 표에서 `품질 점수`, `게이트 통과/미달`, `반복 N회` 를 확인한다.
   - 90↑ 우수 / 85↑ 통과 / 70↑ 보완필요 / 70미만 실패. `passed = 총점>=85`.
   - 미달이면 오케스트레이터가 자동으로 최대 10회 보완 루프를 돌고, 수렴 시 조기종료 후 `수동 확인` 항목을 출력한다.
5. 산출물 경로 보고: 출력 DOCX, 원본 백업 디렉토리, 리포트(md) 경로를 사용자에게 그대로 전달한다.
6. (선택) 결과를 눈으로 점검하려면 `python _build_chochang.py inspect "<결과DOCX>"` 로 문단/표를 덤프한다.
7. (선택) 결과가 만족스럽지 않으면 `--rollback <backup_dir> <target>` 으로 원본을 복구한다.

## 호출 에이전트

이 커맨드는 단일 CLI 실행이 핵심이며, 필요 시 다음 에이전트/스킬과 연계된다(허브: `document-quality-orchestrator`).

- document-type-classifier — 문서유형 분류
- template-cleanup-agent — 양식 안내문구 제거
- formatting-normalizer — 글머리표 공백·표 내부 공백 정리
- content-emphasis-agent — 핵심문장 강조
- psst-review-agent — PSST 4영역 구조검사
- infographic-suggestion-agent — 시각화 제안
- quality-gate-agent — 품질점수 산정·게이트 판정
- backup-rollback-agent — 백업·롤백

## 출력물

- 결과 DOCX: `--output` 지정 경로 또는 `D:\auto_write\results\` 아래 자동 명명 파일.
- 원본 백업: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` 의 원본 사본.
- 리포트: `--no-report` 미사용 시 결과 폴더에 `리포트(md)` + JSON 동시 생성.
- 콘솔 요약: 문서유형/신뢰도, 품질점수·등급·게이트·반복횟수, 후처리 건수(안내문구·글머리표·표셀·빈단락·강조), PSST 요약, 이미지제안 건수, 출력/백업/리포트 경로, 수동 확인 항목.

## 실패 시 처리

- 입력 DOCX 미지정/미존재: `입력 DOCX 경로가 필요합니다 (또는 --rollback 사용)` 안내. 경로 재확인 후 재실행.
- 출력=입력 동일 경로: `ValueError` 발생(원본 덮어쓰기 금지). `--output` 으로 다른 경로 지정.
- 게이트 미달(총점<85): 자동 보완 루프 후에도 미달이면 콘솔의 `수동 확인` 항목을 사용자에게 전달하고, 필요 시 옵션(`--underline`, `--normalize-fonts`)을 바꿔 재실행 제안.
- 후처리 결과가 잘못된 경우: `--rollback "<backup_dir>" "<target>"` 으로 원본 복구.
- AI 키 없음: 분류 보조 AI만 비활성될 뿐 전 단계는 규칙 기반으로 정상 동작(중단되지 않음).

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 전체 파이프라인 1회 (자동 명명 출력 + md/json 리포트)
python document_quality_orchestrator.py "C:\제출\사업계획서.docx"

# 2) 출력 경로 지정 + 강조에 밑줄 추가
python document_quality_orchestrator.py "C:\제출\사업계획서.docx" --output "C:\제출\사업계획서_개선.docx" --underline

# 3) 글자크기 보정 활성 + 안내문구는 유지
python document_quality_orchestrator.py 문서.docx -o 결과.docx --normalize-fonts --keep-guides

# 4) 결과를 JSON 으로 출력 (스크립트 연동용)
python document_quality_orchestrator.py 문서.docx --json

# 5) 결과 DOCX 문단/표 덤프로 눈으로 점검
python _build_chochang.py inspect "결과.docx"

# 6) 원본 복구 (별도 모드)
python document_quality_orchestrator.py --rollback "..\results\backup\20260605_120000" 결과.docx

# (래퍼) 프로젝트 루트에서 바로 실행
python D:\auto_write\scripts\run_document_quality_harness.py "C:\제출\사업계획서.docx"
```

## 보고 형식

실행 후 사용자에게 다음을 한국어로 간결하게 보고한다.

1. 상태 한 줄: `정상 실행 확인됨` / `게이트 미달(수동확인 필요)` / `실행 막힘` 중 하나.
2. 문서유형 + 신뢰도, 품질점수/등급, 게이트 통과여부, 보완 반복 횟수.
3. 후처리 건수 요약(안내문구·글머리표·표셀·빈단락·강조).
4. 산출물 절대경로 3종: 출력 DOCX / 원본 백업 디렉토리 / 리포트(md).
5. 게이트 미달 시: 콘솔의 `수동 확인` 항목과 재실행/롤백 명령 안내.
