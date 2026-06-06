---
description: 제출 직전 최종 처리 - 품질개선 실행 + inspect 검수 + 잔존 placeholder/가이드 확인
argument-hint: <입력DOCX경로> [--output 결과.docx] [--underline] [--keep-guides]
---

# /auto-write-finalize

## 사용 목적
한국 정부지원사업 문서(DOCX)를 제출 직전 최종 처리한다. 다음 3가지를 한 번에 수행한다.
1. 품질개선 파이프라인 실행 (`document_quality_orchestrator.py`)
2. 결과 DOCX 구조 검수 (`_build_chochang.py inspect`)
3. 잔존 placeholder/양식 안내문구 확인 후 보고
빈칸이 남아 있으면 `submittable_filler` 연계 작업으로 안내한다.

## 입력값
- `input` (필수): 처리할 입력 DOCX 절대경로. 예: `C:\제출\사업계획서.docx`
- `--output` / `-o` (선택): 결과 DOCX 경로. 미지정 시 `D:\auto_write\results\` 아래 자동 명명.
- `--underline` (선택): 핵심문장 강조 시 밑줄도 추가.
- `--keep-guides` (선택): 양식 안내문구 삭제 비활성(기본은 삭제).
- `--normalize-fonts` (선택): 글자크기 이상치 보정 활성(기본 비활성).
- `--no-emphasis` (선택): 핵심문장 Bold 강조 비활성.

규칙: 원본 DOCX는 절대 덮어쓰지 않는다. `--output` 을 입력과 같은 경로로 주면 `ValueError` 가 발생한다. 후처리 전 백업이 자동 생성된다.

## 실행 워크플로우(단계)
1. 입력 확인
   - 입력 DOCX가 실제로 존재하는지 확인한다. 없으면 즉시 중단하고 경로를 보고한다.
   - 작업 디렉토리를 `D:\auto_write\app` 으로 둔다(이 경로가 sys.path 기준).
2. 품질개선 실행
   - `python document_quality_orchestrator.py "<입력경로>" [옵션]` 실행.
   - 내부 파이프라인: 백업 → 유형분류(`document_type_classifier`) → `run_all` 후처리(`doc_quality_ops`) → PSST 점검(business_plan/pitch_deck만, `psst_check`) → 이미지제안(`infographic_suggest`) → 점수(`doc_quality_score`) → 게이트(통과=총점>=85) → 미달 시 최대 10회 보완루프(수렴 시 조기종료) → 결과 저장 → 리포트(md+json).
   - 출력 DOCX 경로와 리포트 경로(`D:\auto_write\results\` 아래)를 확보한다.
3. 결과 검수 (inspect)
   - `python _build_chochang.py inspect "<결과DOCX경로>"` 실행.
   - 문단/표 덤프를 받아 구조가 정상인지 확인한다.
4. 잔존 placeholder / 가이드 확인
   - inspect 덤프에서 채워지지 않은 빈칸 표식(예: `[ ]`, `___`, `OOO`, `(작성)`, `※ 작성` 류)과 양식 안내문구가 남아 있는지 확인한다.
   - 양식 안내문구는 `doc_quality_ops.remove_guide_paragraphs` 가 처리하지만, `--keep-guides` 를 준 경우 남아 있을 수 있으니 별도 보고한다.
5. 점수/게이트 판정 확인
   - 리포트(md/json)에서 총점과 게이트 결과(우수90↑ / 통과85↑ / 보완필요70↑ / 실패70미만)를 읽어 보고한다.
6. submittable_filler 연계 안내
   - 잔존 placeholder/빈칸이 있으면 `auto_write.services.submittable_filler` 로 빈칸 채움을 먼저 수행한 뒤 다시 `/auto-write-finalize` 를 실행하도록 안내한다.

## 호출 에이전트
- `executor` : 단계별 PowerShell 명령 실행 및 결과 수집.
- `verifier` : inspect 덤프와 리포트 점수를 대조해 잔존 placeholder/가이드 유무를 독립 검증(작성 패스와 분리).

## 출력물
- 결과 DOCX: `D:\auto_write\results\<자동명명 또는 --output 경로>.docx`
- 백업: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` (원본 보존)
- 리포트: 같은 results 경로의 품질 리포트 `*.md` + `*.json`
- 최종 요약: 총점, 게이트 결과, 잔존 placeholder/가이드 목록, 다음 조치(필요 시 submittable_filler).

## 실패 시 처리
- 입력 DOCX 미존재: 실행 중단, 경로 보고.
- 출력=입력 동일 경로(`ValueError`): `--output` 을 다른 경로로 지정하라고 안내.
- 게이트 미달(총점 70 미만 = 실패): 리포트의 항목별 감점 사유를 보고하고, 보완 후 재실행 또는 submittable_filler 연계를 안내.
- 보완루프 후에도 placeholder 잔존: 해당 위치(문단/표)를 보고하고 submittable_filler 로 채움 우선 처리 안내.
- 롤백 필요 시: `python document_quality_orchestrator.py --rollback "<백업폴더>" "<복원대상DOCX>"` 로 원본 복구.

## 예시 명령(실제 PowerShell)
```powershell
cd D:\auto_write\app

# 1) 기본 최종 처리 (결과는 results\ 자동 명명)
python document_quality_orchestrator.py "C:\제출\사업계획서.docx"

# 2) 출력 경로 지정 + 밑줄 강조
python document_quality_orchestrator.py "C:\제출\사업계획서.docx" --output "D:\auto_write\results\사업계획서_final.docx" --underline

# 3) 결과 DOCX 구조 검수
python _build_chochang.py inspect "D:\auto_write\results\사업계획서_final.docx"

# 4) 리포트 생략하고 JSON 결과만 받기
python document_quality_orchestrator.py "C:\제출\사업계획서.docx" --no-report --json

# 5) 문제 발생 시 원본 롤백
python document_quality_orchestrator.py --rollback "D:\auto_write\results\backup\20260605_120000" "D:\auto_write\results\사업계획서_final.docx"
```

## 보고 형식
첫 줄에 상태를 표시한다(정상 실행 확인됨 / 수정만 완료 / 미검증 / 실행 막힘 / 수정 없음). 이어서 아래 항목을 보고한다.
1. 결과 DOCX 경로 (절대경로)
2. 백업 폴더 경로 (절대경로)
3. 리포트 경로 (md/json)
4. 총점 및 게이트 결과 (우수/통과/보완필요/실패)
5. 잔존 placeholder/양식 안내문구 목록 (없으면 "없음")
6. 다음 조치 (예: submittable_filler 로 빈칸 채움 후 재실행 / 제출 가능)
