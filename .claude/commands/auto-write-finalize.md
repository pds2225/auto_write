---
description: 제출 직전 최종 처리 - 오토파일럿(서식+이미지+PSST 수정) 실행 + inspect 검수 + 잔존 placeholder 확인
argument-hint: <입력DOCX경로> [--output 결과.docx] [--underline] [--keep-guides] [--placeholder-only] [--no-psst]
---

# /auto-write-finalize

## 사용 목적
한국 정부지원사업 문서(DOCX)를 제출 직전 최종 처리한다. 다음을 한 번에 수행한다.
1. **오토파일럿 실행** (`auto_write_autopilot.py`): 백업 → 서식 수정 → 이미지 실제 적용 → PSST 보강 → 점수/게이트.
2. 결과 DOCX 구조 검수 (`_build_chochang.py inspect`).
3. 잔존 placeholder/양식 안내문구 확인 후 보고.

> 과거에는 서식 품질개선만 수행했으나, 이제 **이미지 삽입·PSST 보강까지 실제로 수정**한다.
> 빈칸이 남아 있으면 `submittable_filler` 연계로 채운 뒤 다시 실행하도록 안내한다.

## 입력값
- `input` (필수): 처리할 입력 DOCX 절대경로. 예: `C:\제출\사업계획서.docx`
- `--output` / `-o` (선택): 결과 DOCX 경로. 미지정 시 `D:\auto_write\results\<원본>_autopilot.docx`.
- `--underline` (선택): 핵심문장 강조 시 밑줄도 추가.
- `--keep-guides` (선택): 양식 안내문구 삭제 비활성(기본은 삭제).
- `--normalize-fonts` (선택): 글자크기 이상치 보정 활성.
- `--placeholder-only` (선택): 차트 생성 없이 이미지 자리표시만 삽입(가장 안전).
- `--no-psst` (선택): PSST 작성 보강 생략.

규칙: **원본 DOCX 는 절대 덮어쓰지 않는다.** 출력=입력이면 `ValueError`. 후처리 전 백업이 자동 생성된다.

## 실행 워크플로우(단계)
1. 입력 확인: 입력 DOCX 존재 확인. 없으면 중단·보고. 작업 디렉토리를 `D:\auto_write\app` 으로 둔다.
2. 오토파일럿 실행: `python auto_write_autopilot.py "<입력경로>" [옵션]`.
   - 백업 → 서식 수정(안내문구·공백·강조) → 이미지 적용(표 실측치→차트, 없으면 자리표시) →
     PSST 보강(누락/미흡 영역 작성 가이드) → 점수/게이트 → 통합 리포트.
3. 결과 검수: `python _build_chochang.py inspect "<결과DOCX경로>"` 로 구조 확인.
4. 잔존 placeholder/가이드 확인: 빈칸 표식(`___`, `(작성)`, `※ 작성`)·양식 안내문구 잔존 여부 보고.
5. 점수/게이트 판정 확인: 리포트의 총점·게이트(우수90↑/통과85↑/보완70↑/실패70미만) 보고.
6. submittable_filler 연계 안내: 잔존 빈칸이 있으면 plan 데이터로 채운 뒤 재실행하도록 안내.

## 호출 에이전트
- `executor`: 단계별 PowerShell 명령 실행·결과 수집.
- `verifier`: inspect 덤프와 리포트 점수를 대조해 잔존 placeholder/가이드 유무를 독립 검증(작성 패스와 분리).

## 출력물
- 결과 DOCX: `D:\auto_write\results\<자동명명 또는 --output 경로>.docx`
- 백업: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` (원본 보존)
- 통합 리포트: `results\<원본>_autopilot_report.md` (총점·이미지·PSST·수동 To-Do)
- 최종 요약: 총점, 게이트, 차트/자리표시 수, PSST 보강 영역, 잔존 placeholder, 다음 조치.

## 실패 시 처리
- 입력 DOCX 미존재: 실행 중단, 경로 보고.
- 출력=입력 동일 경로(`ValueError`): `--output` 다른 경로 지정 안내.
- 게이트 미달(총점 70 미만): 리포트 항목별 감점 사유 보고, 보완 후 재실행 또는 submittable_filler 연계 안내.
- 보완 후에도 placeholder 잔존: 해당 위치 보고, submittable_filler 우선 처리 안내.
- 롤백: `python document_quality_orchestrator.py --rollback "<백업폴더>" "<복원대상DOCX>"`.

## 예시 명령(실제 PowerShell)
```powershell
cd D:\auto_write\app

# 1) 기본 최종 처리(오토파일럿 한 번에)
python auto_write_autopilot.py "C:\제출\사업계획서.docx"

# 2) 출력 경로 지정 + 밑줄 강조
python auto_write_autopilot.py "C:\제출\사업계획서.docx" --output "D:\auto_write\results\사업계획서_final.docx" --underline

# 3) 가장 안전(차트 생성 없이 자리표시만) + PSST 보강 유지
python auto_write_autopilot.py "C:\제출\사업계획서.docx" --placeholder-only

# 4) 결과 구조 검수
python _build_chochang.py inspect "D:\auto_write\results\사업계획서_final.docx"

# 5) 문제 발생 시 원본 롤백
python document_quality_orchestrator.py --rollback "D:\auto_write\results\backup\20260608_120000" "D:\auto_write\results\사업계획서_final.docx"
```

## 보고 형식
첫 줄에 상태 표시(정상 실행 확인됨 / 수정만 완료 / 미검증 / 실행 막힘 / 수정 없음). 이어서:
1. 결과 DOCX 경로(절대경로)
2. 백업 폴더 경로(절대경로)
3. 통합 리포트 경로(md)
4. 총점 및 게이트 결과(우수/통과/보완/실패)
5. 이미지(차트/자리표시) 수 · PSST 보강 영역
6. 잔존 placeholder/양식 안내문구 목록(없으면 "없음")
7. 다음 조치(submittable_filler 로 빈칸 채움 후 재실행 / 제출 가능)
