---
description: 문서 품질점수와 게이트 판정을 빠르게 실행하는 improve-doc-quality 짧은 별칭
argument-hint: <입력DOCX> [--output 결과DOCX] [--underline] [--json] [--rollback BACKUP_DIR TARGET]
---

# /auto-write-quality

## 사용 목적
- 완성된 DOCX 한 개를 받아 품질 후처리 파이프라인을 실행하고, 100점 만점 품질점수와 게이트 판정(우수/통과/보완필요/실패)을 빠르게 확인한다.
- `/improve-doc-quality`의 짧은 별칭이다. 옵션을 길게 고민하지 않고 점수와 통과 여부만 빠르게 보고 싶을 때 사용한다.
- 내부적으로 `DocumentQualityOrchestrator`를 그대로 호출한다(백업 → 유형분류 → 후처리 → PSST → 이미지제안 → 점수 → 게이트 → 보완루프 → 저장 → 리포트).
- 원본 DOCX는 절대 덮어쓰지 않는다. 후처리 전 반드시 백업한다. AI 키 없이도 전 단계가 결정론적으로 동작한다.

## 입력값
- 첫 번째 인자(필수): 처리할 입력 DOCX의 절대경로. 예: `C:\문서\사업계획서.docx`
- `--output` / `-o` (선택): 결과 DOCX 저장 경로. 생략하면 자동 파일명으로 저장한다. 입력 경로와 같으면 ValueError로 막힌다(원본 보호).
- `--underline` (선택): 주요 문장 강조 시 밑줄까지 적용한다(기본은 굵게만).
- `--json` (선택): 사람이 읽는 요약 대신 JSON 결과를 표준출력으로 받는다.
- `--no-emphasis` (선택): 주요 문장 강조 단계를 끈다.
- `--keep-guides` (선택): 안내문구 제거 단계를 끈다(기본은 제거).
- `--normalize-fonts` (선택): 글자 크기 일관화를 켠다(기본 비활성).
- `--no-report` (선택): md/json 리포트 파일 저장을 생략한다.
- `--rollback BACKUP_DIR TARGET` (선택): 잘못된 결과를 백업본으로 되돌린다.

## 실행 워크플로우(단계)
1. 입력 인자에서 DOCX 절대경로를 확인한다. 경로에 공백이 있으면 큰따옴표로 감싼다.
2. 작업 디렉터리를 `D:\auto_write\app` 으로 둔 상태에서 `document_quality_orchestrator.py` 를 호출한다.
3. 오케스트레이터가 다음을 자동 수행한다.
   - `backup_original()` 으로 `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` 에 원본 백업.
   - `document_type_classifier.classify_docx()` 로 9개 유형 중 하나로 분류.
   - `doc_quality_ops.run_all()` 로 결정론적 후처리(안내문구 제거, 글머리표/문단 공백 정리, 표 내부 정리, 주요 문장 강조 등).
   - business_plan/pitch_deck 인 경우에만 `psst_check.check_psst()` 실행.
   - `infographic_suggest.suggest_images()` 로 시각화 제안.
   - `doc_quality_score.score_document()` 로 100점 채점 후 게이트 판정.
   - 85점 미만이면 최대 10회 보완 루프(수렴 시 조기 종료) 후 결과 저장.
4. 결과 DOCX와 리포트(md+json)가 `D:\auto_write\results` 하위에 저장된다.
5. 표준출력(또는 `--json`)에서 총점, 게이트 등급, passed 여부를 읽어 보고한다.
6. 점수가 낮거나 결과가 이상하면 `--rollback` 으로 원본을 복구한다.

## 호출 에이전트
- `quality-gate-agent` : 품질점수 산출과 게이트 판정(우수/통과/보완필요/실패) 해석을 담당한다.
- `documentation-agent` : md/json 리포트 내용을 사용자 보고 형식으로 정리한다.
- `document-type-classifier` : 입력 문서 유형 판별 결과를 확인한다.
- (별도 호출 없이 오케스트레이터 단일 실행만으로 충분하면 위 에이전트는 결과 해석 보조용으로만 사용한다.)

## 출력물
- 결과 DOCX: `--output` 지정 경로 또는 `D:\auto_write\results` 하위 자동 파일명.
- 품질 리포트: 같은 위치의 `.md` 와 `.json` (`--no-report` 시 생략).
- 원본 백업: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\`.
- 콘솔/JSON 요약: 문서유형, 총점(0~100), 게이트 등급, passed(총점>=85) 여부.

## 실패 시 처리
- 입력 경로가 없거나 DOCX가 아니면: 경로를 다시 확인하고 절대경로로 재실행한다.
- 출력 경로가 입력과 동일하면 ValueError 발생 → `--output` 에 다른 경로를 지정한다(원본 덮어쓰기 금지).
- 결과 품질이 기대보다 낮거나 잘못 처리된 경우: 콘솔에 찍힌 백업 폴더 경로를 사용해 즉시 롤백한다.
  - `cd D:\auto_write\app`
  - `python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" "결과.docx"`
- Python 실행 자체가 막히면 인터프리터 전체경로로 재시도한다.
  - `C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe document_quality_orchestrator.py "문서.docx"`
- Secret/API Key/.env 내용은 출력하지 않는다. AI 키가 없어도 정상 동작하므로 키 오류는 무시 가능하다.

## 예시 명령(실제 PowerShell)
기본 실행(점수+게이트 빠른 확인):
```
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\문서\사업계획서.docx"
```

결과 경로 지정 + 밑줄 강조:
```
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\문서\사업계획서.docx" --output "C:\문서\사업계획서_개선.docx" --underline
```

JSON으로 점수만 받기(스크립트 연동용):
```
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\문서\사업계획서.docx" --json
```

래퍼 스크립트로 실행(sys.path 자동 설정):
```
cd D:\auto_write
python scripts\run_document_quality_harness.py "C:\문서\사업계획서.docx"
```

잘못된 결과 롤백:
```
cd D:\auto_write\app
python document_quality_orchestrator.py --rollback "..\results\backup\20260605_143000" "C:\문서\사업계획서_개선.docx"
```

결과 DOCX 내부 점검(문단/표 덤프):
```
cd D:\auto_write\app
python _build_chochang.py inspect "C:\문서\사업계획서_개선.docx"
```

테스트:
```
cd D:\auto_write\app
python -m pytest tests/test_document_quality_harness.py -q
```

## 보고 형식
실행 후 아래 항목을 한국어로 짧게 보고한다.
1. 상태 표시(첫 줄): 정상 실행 확인됨 / 수정만 완료 / 미검증 / 실행 막힘 / 수정 없음 중 하나.
2. 문서유형: 분류 결과(예: business_plan).
3. 품질점수: 총점(0~100)과 게이트 등급(90↑우수 / 85↑통과 / 70↑보완필요 / 70미만실패).
4. 통과 여부: passed(총점>=85) true/false.
5. 결과 파일 경로(절대경로): 결과 DOCX, 리포트(md/json), 백업 폴더.
6. 다음 행동 제안: 통과 시 종료, 보완필요/실패 시 보완 포인트 또는 롤백 안내.
