---
description: 결과/입력 DOCX 구조 덤프 + 검수 리포트를 후처리 없이 진단만 수행한다
argument-hint: <docx경로> [--report]
---

# /auto-write-inspect

## 사용 목적

완성된 또는 입력 단계의 DOCX 파일을 **수정하지 않고** 구조만 들여다본다.
- `_build_chochang.py inspect`로 문단(빈 줄 제외)과 표 그리드를 그대로 덤프한다.
- 필요 시 `qa_service.QAService`의 검수 결과(필수입력 누락·안내문구·플레이스홀더 경고)를 함께 확인한다.
- 후처리(안내문구 삭제·강조·글머리표 정리 등)는 **절대 수행하지 않는다.** 원본 백업도 만들지 않는다(읽기 전용).
- 쉽게 말하면 "이 문서 안에 뭐가 들어있는지" 목록으로 보여주는 진단 전용 명령이다.

## 입력값

- `$1` (필수): 진단할 DOCX 절대경로. 예: `D:\auto_write\results\결과.docx`
- `--report` (선택): 구조 덤프에 더해 검수 리포트(오류/경고 요약)까지 출력한다. 생략 시 구조 덤프만 출력.

## 실행 워크플로우(단계)

1. **경로 확인**: `$1`이 실제 존재하는 `.docx`인지 확인한다. 없으면 즉시 중단하고 사용자에게 경로를 다시 묻는다.
2. **구조 덤프**: 아래 명령으로 문단·표를 덤프한다(읽기 전용, 파일 변경 없음).
   ```powershell
   cd D:\auto_write\app
   python _build_chochang.py inspect "<docx경로>"
   ```
   - 출력: `PARAGRAPHS (non-empty):` 아래 `000: ...` 형식의 문단 목록, `TABLES: N`, 각 표의 `-- Table ti (행x열) --` 그리드.
3. **(선택) 검수 리포트**: `--report`가 있을 때만 수행한다. `qa_service.QAService.build_report(...)`는 양식 프로파일·프로젝트 입력이 필요한 내부 API이므로, 표준 분석 경로인 `_build_chochang.py analyze`(현재 양식 기준 검수 메시지 출력)를 사용해 오류/경고를 확인한다.
   ```powershell
   cd D:\auto_write\app
   python _build_chochang.py analyze
   ```
   - 출력에서 `필수입력`·`안내문구`·`플레이스홀더` 관련 줄만 요약한다.
4. **요약 보고**: 문단 수, 표 개수/크기, (리포트 시) 오류·경고 개수를 사용자에게 정리한다. 파일은 변경하지 않았음을 명시한다.

## 호출 에이전트

- `doc-architect`: 구조 덤프 결과 해석 및 전체 진단 총괄.
- `doc-quality-gate`: `--report` 시 검수 메시지(필수입력 누락·안내문구·플레이스홀더) 요약.

## 출력물

- 콘솔 출력만 생성한다. **새 DOCX·백업·리포트 파일을 만들지 않는다**(읽기 전용 진단).
- 사용자에게 전달: 문단 목록 요약, 표 개수·크기, (`--report` 시) 오류/경고 요약.

## 실패 시 처리

- 경로 없음/오타: "파일을 찾을 수 없습니다: <경로>"로 안내하고 중단. 후처리로 넘어가지 않는다.
- `python` 미인식: `C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe _build_chochang.py inspect "..."` 절대경로 인터프리터로 재시도 안내.
- DOCX 손상/열기 실패: python-docx 예외 메시지 원문 일부 + "파일이 손상되었거나 .docx가 아닐 수 있습니다" 해석을 함께 보고.
- `analyze`가 양식 의존으로 실패하면 구조 덤프(2단계) 결과만이라도 보고하고, 검수는 건너뛴 사실을 명시한다.

## 예시 명령(실제 PowerShell)

```powershell
# 구조만 진단
cd D:\auto_write\app
python _build_chochang.py inspect "D:\auto_write\results\결과.docx"

# 구조 + 검수 리포트
cd D:\auto_write\app
python _build_chochang.py inspect "D:\auto_write\results\결과.docx"
python _build_chochang.py analyze

# python 미인식 시
C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe _build_chochang.py inspect "D:\auto_write\results\결과.docx"
```

## 보고 형식

```
상태: 진단 완료 (수정 없음 / 읽기 전용)
대상: <docx경로>
구조: 문단 N개, 표 M개 (각 표 행x열)
검수(--report 시): 오류 E개 / 경고 W개  ← 주요 메시지 3줄 이내 요약
변경 파일: 없음 (후처리·백업 미수행)
다음 단계 제안: 품질 개선이 필요하면 /auto-write-quality 또는 /improve-doc-quality 실행
```
