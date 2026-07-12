# 백업 / 롤백 규칙

본 문서는 `document_quality_orchestrator.py`의 `DocumentQualityOrchestrator.backup_original()` 및 `DocumentQualityOrchestrator.rollback()` 동작을 기준으로 한다. 원본 DOCX 보호와 안전한 복구 절차를 정의한다.

---

## 1. 절대 원칙

| 원칙 | 내용 |
|------|------|
| 원본 덮어쓰기 금지 | 출력 경로가 입력 경로와 같으면 `ValueError`를 발생시키고 중단한다. 원본을 절대 덮어쓰지 않는다. |
| 백업 선행 | 후처리(`run_all`) 시작 전에 반드시 원본 DOCX를 백업한다. |
| 결정론적 동작 | 백업/롤백은 AI 없이 파일 복사 기준으로만 동작한다. |
| 백업 없는 수정 금지 | 백업이 생성되지 않은 상태에서 원본을 수정하지 않는다. |

---

## 2. 백업 규칙

| 항목 | 값 |
|------|-----|
| 담당 함수 | `DocumentQualityOrchestrator.backup_original(path) -> backup_dir` |
| 백업 루트 | `D:\auto_write\results\backup\` |
| 백업 폴더 형식 | `results\backup\<YYYYMMDD_HHMMSS>\` (실행 시각 타임스탬프) |
| 백업 대상 | 입력 원본 DOCX 1개 |
| 실행 시점 | 파이프라인 시작 직후, 후처리(`run_all`) 이전 |
| 반환값 | 생성된 백업 디렉터리 경로(`backup_dir`) |

- 백업 폴더는 실행할 때마다 새 타임스탬프로 생성되므로 과거 백업이 덮어써지지 않는다.
- 백업 디렉터리 경로는 이후 롤백(복구)에 사용된다.

---

## 3. 롤백 규칙

| 상황 | 처리 방식 |
|------|----------|
| 후처리 실패 | 출력 파일을 만들지 않고 원본을 그대로 유지한다(원본 무변경). |
| 출력 생성 실패 | 원본 덮어쓰기를 하지 않는다. 출력 경로 = 입력 경로면 `ValueError`로 사전 차단된다. |
| 사용자 요청 복구 | `results\backup\<타임스탬프>\`의 원본을 대상 파일 위치로 복구한다. |

| 항목 | 값 |
|------|-----|
| 담당 함수 | `DocumentQualityOrchestrator.rollback(backup_dir, target) -> bool` |
| 호출 형태 | `@staticmethod` (인스턴스 없이 호출 가능) |
| 입력 | `backup_dir`(백업 폴더 경로), `target`(복구 대상 파일 경로) |
| 반환값 | 복구 성공 시 `True`, 실패 시 `False` |

---

## 4. 리포트 기록

- `.run(...)`은 `HarnessResult`를 반환하며 `write_report=True`(기본값)일 때 리포트(md + json)를 `results_root` 하위에 기록한다.
- 리포트에는 사용한 백업 디렉터리 경로(`backup_dir`)와 롤백 관련 내역이 함께 남는다.
- 복구가 필요할 때 리포트에 기록된 `backup_dir` 경로를 그대로 롤백 인자로 사용한다.

---

## 5. 파이프라인 내 위치

`DocumentQualityOrchestrator.run()` 실행 순서상 백업/롤백 위치는 다음과 같다.

```
백업(backup_original) → 유형분류 → run_all 후처리 → PSST → 이미지제안
→ 점수 → 게이트 → (미달 시 보완루프) → 출력 저장 → 리포트
```

- 백업은 가장 먼저 수행된다.
- 어느 단계에서 실패해도 원본은 백업과 별개로 무변경 유지되며, 출력=입력 시 `ValueError`로 차단된다.

---

## 6. PowerShell 복구(롤백) 명령 예시

표준 진입점(CLI)의 `--rollback` 옵션을 사용한다. `--rollback`은 백업 폴더 경로와 복구 대상 파일을 인자로 받는다.

```powershell
cd D:\auto_write\app

# 백업 폴더에서 결과 파일을 복구
python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx

# 절대경로 예시
python document_quality_orchestrator.py --rollback "D:\auto_write\results\backup\20260605_142530" "D:\경로\결과.docx"
```

복구 후 결과 확인:

```powershell
python _build_chochang.py inspect "결과.docx"
```

- `<YYYYMMDD_HHMMSS>` 자리에는 리포트에 기록된 실제 백업 타임스탬프 폴더명을 넣는다.
- 복구는 백업 폴더의 원본 DOCX를 대상 경로로 되돌리는 동작이며, 원본 백업 자체는 보존된다.
