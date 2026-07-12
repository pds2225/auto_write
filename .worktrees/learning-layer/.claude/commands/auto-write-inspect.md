---
description: DOCX 구조를 진단(기본)하거나 --fix 로 발견된 서식 문제(안내문구·공백·강조)를 실제로 수정한다.
argument-hint: <docx경로> [--report] [--fix] [--out 결과.docx]
---

# /auto-write-inspect

## 사용 목적

DOCX 파일의 구조를 들여다보고, 필요하면 **바로 고친다**. 두 가지 모드가 있다.

- **기본(진단 모드, 읽기 전용)**: `_build_chochang.py inspect` 로 문단·표를 덤프한다.
  `--report` 시 검수 메시지(필수입력 누락·안내문구·플레이스홀더)도 요약한다. 파일을 바꾸지 않는다.
- **`--fix`(수정 모드, 실제 수정)**: 진단에서 드러난 서식 문제를 `document_quality_orchestrator.py`
  로 **실제 수정**한다(양식 안내문구 삭제 → 글머리표/표 공백 정리 → 빈 단락 삭제 → 핵심문장 강조).
  원본은 자동 백업되고, 결과는 새 DOCX 로 저장된다(원본 덮어쓰기 금지).

쉽게 말하면: 기본은 "문서 안에 뭐가 들었나" 진단, `--fix` 는 "문제를 발견하면 바로 정리해서
새 파일로 저장" 한다.

## 입력값

- `$1` (필수): DOCX 절대경로. 예: `D:\auto_write\results\결과.docx`
- `--report` (선택): 진단 시 검수 리포트(오류/경고 요약)도 출력.
- `--fix` (선택): 서식 문제를 실제 수정(품질 파이프라인 1회 실행).
- `--out` / `-o` (선택, `--fix` 와 함께): 결과 DOCX. 미지정 시 `results\` 자동 명명.

규칙: `--fix` 는 **원본을 덮어쓰지 않는다.** 백업이 `results\backup\<ts>\` 에 자동 생성된다.

## 실행 워크플로우(단계)

1. **경로 확인**: `$1` 이 실제 `.docx` 인지 확인. 없으면 중단하고 경로 재요청.
2. **진단(기본)**: `python _build_chochang.py inspect "<docx>"` 로 문단·표 덤프. `--report` 시 `analyze` 로 검수 요약.
3. **수정(`--fix`)**: `python document_quality_orchestrator.py "<docx>" [--output ...]` 실행.
   - 내부: 백업 → 안내문구 삭제 → 글머리표/표 공백 → 빈 단락 → 강조 → 점수/게이트 → 리포트.
   - 결과 DOCX·백업·총점·게이트 결과를 보고.
4. **요약 보고**: 문단 수, 표 개수/크기, (수정 시) 후처리 집계·점수·게이트.

## 호출 에이전트

- `doc-architect`: 구조 덤프 해석·진단 총괄.
- `doc-quality-gate`: `--report` 검수 요약 / `--fix` 시 점수·게이트 판정.
- `doc-postprocessor`: `--fix` 실제 서식 수정 담당.

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 구조만 진단(읽기 전용)
python _build_chochang.py inspect "D:\auto_write\results\결과.docx"

# 2) 진단 + 검수 리포트
python _build_chochang.py inspect "D:\auto_write\results\결과.docx"
python _build_chochang.py analyze

# 3) 발견된 서식 문제를 실제 수정(백업+새 파일 저장)
python document_quality_orchestrator.py "D:\auto_write\results\결과.docx" --output "D:\auto_write\results\결과_fixed.docx"
```

## 실패 시 처리

- 경로 없음/오타: "파일을 찾을 수 없습니다: <경로>" 안내 후 중단.
- `python` 미인식: `C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe` 절대경로 재시도.
- DOCX 손상: python-docx 예외 메시지 일부 + 쉬운 해석 보고.
- `--fix` 출력=입력 동일(`ValueError`): `--out` 다른 경로 지정 안내.

## 보고 형식

```
상태: 진단 완료(수정 없음) 또는 수정 완료(새 파일 저장)
대상: <docx경로>
구조: 문단 N개, 표 M개
검수(--report): 오류 E개 / 경고 W개
수정(--fix): 결과 DOCX 경로 / 백업 경로 / 총점·게이트 / 후처리 집계
다음 단계: 전체 무인 처리는 /auto-write-autopilot
```
