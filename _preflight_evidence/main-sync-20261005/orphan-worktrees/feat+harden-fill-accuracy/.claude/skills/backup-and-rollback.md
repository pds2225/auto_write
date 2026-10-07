---
name: backup-and-rollback
description: >-
  DOCX 후처리(문서 품질 하네스) 실행 전 원본을 자동 백업하고, 게이트 실패·후처리 손상·사용자 요청 시 원본으로 복구하는 안전장치 스킬.
  다음 상황에서 적극적으로 사용하라: (1) document_quality_orchestrator 후처리/품질개선/정리 작업을 돌리기 직전, (2) "원본 백업해줘", "백업하고 돌려줘",
  "되돌려줘", "복구해줘", "롤백", "원래대로", "이전 파일로", "원본 망가졌어" 요청 시, (3) 후처리 결과가 이상하거나 점수가 떨어져 원래 문서로
  돌아가야 할 때, (4) 후속작업 키워드 "다시", "재실행", "수정", "보완"으로 후처리를 반복 실행하기 전(매 실행마다 새 백업 보장).
  원본 DOCX를 절대 덮어쓰지 않도록 강제하는 가드도 이 스킬이 담당한다.
---

## 목적

문서 품질 후처리는 원본 DOCX를 변형한다. 잘못되면 원본이 손상될 수 있으므로,
이 스킬은 두 가지를 강제한다.

1. 후처리 전 항상 원본을 타임스탬프 폴더에 백업한다.
2. 게이트 실패·후처리 손상·사용자 요청 시 백업본으로 원본/결과를 복구한다.

쉽게 말하면: "고치기 전에 사진부터 찍어두고, 잘못되면 그 사진으로 되돌린다."

## 적용 대상

- 입력: 후처리 대상 또는 이미 후처리된 결과 DOCX 파일.
- 백업 위치: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` (실행 시각 폴더).
- 복구 대상(target): 원본 경로 또는 임의의 출력 경로.
- 연결 코드: `app/auto_write/services/document_quality_orchestrator.py` 의
  `DocumentQualityOrchestrator.backup_original`, `DocumentQualityOrchestrator.rollback`.

## 탐지 규칙

아래 중 하나라도 해당하면 이 스킬을 발동한다.

- 후처리(`run`)를 실행하려는데 아직 백업 폴더가 없다.
- 출력 경로(`output_docx`)가 입력 경로(`input_docx`)와 동일하다 → 원본 덮어쓰기 위험.
  (orchestrator 는 이 경우 `ValueError` 를 발생시킨다. 절대 우회하지 마라.)
- 사용자가 "백업/복구/롤백/되돌려/원래대로/이전 파일" 류를 요청했다.
- 후처리 결과 점수가 이전보다 낮거나 문서가 깨졌다고 사용자가 보고했다.
- "다시/재실행/수정/보완"으로 같은 문서를 또 후처리하려 한다 → 직전 상태를 새 백업으로 남긴다.

## 수정 규칙

코드의 실제 동작과 정확히 일치시켜라.

- 백업 생성: `backup_original(input_path)` 호출.
  - `results\backup\` 아래에 `datetime.now().strftime("%Y%m%d_%H%M%S")` 폴더를 만든다.
  - 입력 파일을 `shutil.copy2` 로 그 폴더에 같은 파일명으로 복사한다.
  - 반환값은 생성된 백업 디렉토리 경로(`Path`). 이 경로를 사용자에게 그대로 보고한다.
- 정상 후처리: `orchestrator.run(...)` 는 내부적으로 백업을 먼저 수행하므로,
  CLI 로 후처리를 돌릴 때는 별도 백업 명령이 필요 없다(자동). 결과의 `backup_dir` 를 확인해 보고한다.
- 복구: `rollback(backup_dir, target_path)` 호출(정적 메서드).
  - `backup_dir` 안의 `*.docx` 중 첫 후보를 찾아 `target_path` 로 복사한다.
  - 백업 폴더에 docx 가 없으면 `False` 를 반환한다(복구 실패).
  - 복사에 성공하면 `True` 를 반환한다.
- 절대 금지: 원본 위에 후처리 결과를 직접 쓰기. 출력 경로는 항상 원본과 다른 경로로 지정.

## 예외 규칙

- 백업 폴더에 `.docx` 가 하나도 없으면 `rollback` 은 `False` 를 반환한다 → 복구하지 말고 실패를 보고한다.
- 같은 초(second)에 두 번 백업하면 타임스탬프 폴더명이 겹칠 수 있다.
  `mkdir(parents=True, exist_ok=True)` 로 폴더는 재사용되며 동일 파일명은 덮어쓴다 →
  연속 백업이 필요하면 실행 간 최소 1초 간격을 두거나 직전 백업 경로를 먼저 확인한다.
- 사용자가 "수정하지 마 / 계획만 / 원인만" 이라고 하면 백업·복구 명령을 실행하지 말고 절차만 설명한다.
- 백업은 원본을 읽기만 한다(`copy2`). 원본을 변형하지 않는다.
- target 경로가 원본일 때 복구는 정상 동작이지만, 후처리 출력 경로를 원본으로 지정하는 것은 금지(위 수정 규칙).

## 테스트 방법

PowerShell 에서 실제 실행으로 검증한다.

```powershell
cd D:\auto_write\app

# 1) 후처리 실행 → 백업 폴더가 자동 생성되는지 확인 (출력은 입력과 다른 경로)
python document_quality_orchestrator.py "C:\경로\문서.docx" --output "C:\경로\문서_정리.docx"

# 2) 생성된 최신 백업 폴더 확인
Get-ChildItem D:\auto_write\results\backup | Sort-Object Name -Descending | Select-Object -First 1

# 3) 롤백: 백업본으로 target 복구
python document_quality_orchestrator.py --rollback "D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>" "C:\경로\문서_정리.docx"
#  → 콘솔에 "[rollback] 성공: <backup_dir> -> <target>" 출력이면 정상

# 4) 하네스 단위 테스트(백업/롤백 포함)
cd D:\auto_write\app; python -m pytest tests/test_document_quality_harness.py -q
```

기대 결과: 후처리 실행 시 `원본 백업 : <backup_dir>` 가 출력되고, `--rollback` 시
`[rollback] 성공` 이 출력되며 target 파일이 백업본 내용으로 교체된다.

## 실패 시 롤백 기준

- 후처리 결과 게이트 실패(`passed=False`, 총점 85 미만)이고 사용자가 원본 유지를 원하면 →
  결과 파일을 버리고 원본을 그대로 둔다(원본은 미변형이므로 별도 복구 불필요).
- 후처리 결과 파일이 손상/오작동하면 → 해당 출력 경로를 target 으로 `rollback` 실행해 백업본으로 덮어쓴다.
- `rollback` 이 `False`(백업에 docx 없음)면 복구 실패로 간주하고, 다른 백업 타임스탬프 폴더를 찾아 재시도한다.
- 어떤 경우에도 원본 경로를 후처리 출력 대상으로 사용하지 않는다.

## 품질 점수 반영

이 스킬은 점수 산정 9개 항목(`doc_quality_score.score_document`)에 직접 점수를 더하지 않는다.
대신 점수 산정·게이트 통과 여부를 신뢰할 수 있게 만드는 안전 토대다.

- 후처리가 점수를 떨어뜨렸을 때 원복 가능 → 잘못된 결과가 최종 산출물로 남는 것을 방지.
- 게이트(90 우수 / 85 통과 / 70 보완필요 / 70 미만 실패) 미달 결과를 폐기하고 원본 기준으로 재시도하는 근거 제공.
- 보완 루프(최대 10회) 도중 악화 시 직전 백업으로 되돌려 손실을 막는다.

## 연결 코드·CLI

- 코드: `app/auto_write/services/document_quality_orchestrator.py`
  - `DocumentQualityOrchestrator.backup_original(input_path: Path) -> Path` (백업 디렉토리 반환)
  - `DocumentQualityOrchestrator.rollback(backup_dir, target_path) -> bool` (정적 메서드)
  - `DocumentQualityOrchestrator.run(input_docx, output_docx=None, ...)` (내부에서 백업 선행, 출력=입력이면 `ValueError`)
- CLI 진입점: `app/document_quality_orchestrator.py`
  - 후처리: `python document_quality_orchestrator.py "입력.docx" --output "결과.docx"`
  - 롤백: `python document_quality_orchestrator.py --rollback "BACKUP_DIR" "TARGET"`
- 래퍼: `scripts/run_document_quality_harness.py`
- 백업 경로: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\`
