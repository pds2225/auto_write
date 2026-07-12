---
description: 초안/메모 DOCX 를 '제출 가능 사업계획서'로 생성·완성한다 - AI 근거명시 작성 → 품질 오토파일럿 → 공고 채점 → 목표점수까지 반복.
argument-hint: <초안DOCX경로> [--brief-file 브리프.txt] [--announcement-file 공고.txt] [--target-ratio 0.85] [--max-loops 3] [--output 결과.docx]
---

# /auto-write-bizplan

## 사용 목적

대충 쓴 초안/메모 DOCX 를 넣으면 **바로 제출에 가까운 완성도**까지 끌어올린다.
한 번 실행으로 다음을 목표 점수에 도달할 때까지 반복한다.

1. **AI 본문 작성/보강** — PSST 약점 영역을 AI 가 작성. 수치에는 **[산출근거: 출처·연도·계산]** 을
   병기하고, 출처를 댈 수 없는 핵심 수치는 지어내지 않고 **[확인필요]** 로 표시한다.
2. **품질 오토파일럿** — 서식 정리 + 이미지(표 실측치→차트, 없으면 자리표시) + (남은 영역)PSST 가이드 + 100점 채점/게이트.
3. **공고 채점** — 공고 평가기준을 주면 심사위원 관점으로 채점하고, 목표 충족률 미달 시 약점 영역을 보완해 다시 시도.

쉽게 말하면: 초안을 넣으면 **AI가 근거를 달아 본문을 채우고, 서식·그림을 정리하고, 공고 기준 점수가
목표에 닿을 때까지 스스로 고쳐서** 제출 직전본과 "사람이 확인할 것 목록"을 돌려준다.

## 안전 원칙 (불변)

- **원본 절대 보존**: 첫 단계에서 원본을 `results\backup\<ts>\` 에 백업. 출력=입력이면 `ValueError`.
- **근거 없는 날조 0**: 무출처 핵심 수치는 [확인필요] 로만 남긴다. 허위기재는 형사처벌·환수 대상.
- **점수 부풀리기 방지**: 채점은 별도 AI 패스로 독립 수행. 최종 수치 검증 책임은 사용자.
- AI 키가 없으면 본문 자동작성·채점은 생략되고 구조·서식 완성만 수행된다(안전 폴백).

## 입력값

- `input` (필수): 초안/메모 DOCX 경로.
- `--brief` / `--brief-file`: 사업 브리프(아이디어·팀·핵심수치) 텍스트 또는 파일. AI 작성 품질을 높인다.
- `--announcement-file`: 공고 평가기준 텍스트 파일. 있으면 채점·목표 반복을 수행한다.
- `--target-ratio`: 목표 충족률(기본 0.85 = 85%). 도달 시 조기 종료.
- `--max-loops`: 최대 반복 횟수(기본 3).
- `--output` / `-o`: 최종 출력 DOCX. 미지정 시 `results\<원본>_bizplan.docx`.
- `--placeholder-only`: 이미지를 차트 없이 자리표시만(가장 안전).
- `--no-ai`: AI 비활성(구조·서식만).
- `--json`: 결과 JSON 출력.

## 실행 워크플로우(단계)

1. 입력 DOCX 존재 확인. 없으면 "실행 막힘" 보고.
2. `cd D:\auto_write\app` 후 `python bizplan_autopilot.py "<초안>" [옵션]` 실행.
3. 산출물 확인: 최종 DOCX, 백업, 통합 리포트(md, 점수추이·근거출처·확인필요 To-Do).
4. 사용자에게 정리: 채점 추이/목표도달, 서식점수, 차트/자리표시, **[확인필요] 항목(수치 검증 필수)**.

## 호출 에이전트

- `doc-analyzer`: PSST 약점 영역 진단.
- `doc-postprocessor`: AI 본문 보강·서식·이미지 적용(DOCX 변형).
- `doc-quality-gate`: 품질 게이트 + 공고 채점 판정.
- `doc-safety-guard`: 백업/원본 보존.
- `doc-writer`: 통합 리포트·확인필요 To-Do 정리.

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 초안 + 브리프로 완성(공고 없이 1회 완성)
python bizplan_autopilot.py "C:\초안\사업계획서_초안.docx" --brief-file "C:\초안\brief.txt"

# 2) 공고 기준 목표 85%까지 자동 반복(최대 3회)
python bizplan_autopilot.py "C:\초안\초안.docx" --announcement-file "C:\공고\평가기준.txt" --target-ratio 0.85 --max-loops 3

# 3) 가장 안전(이미지 자리표시만) + 출력 지정
python bizplan_autopilot.py "C:\초안\초안.docx" --placeholder-only --output "D:\auto_write\results\사업계획서_최종.docx"

# 4) AI 없이 구조·서식만(키 없을 때)
python bizplan_autopilot.py "C:\초안\초안.docx" --no-ai --json

# 5) 문제 시 원본 롤백
python document_quality_orchestrator.py --rollback "D:\auto_write\results\backup\<ts>" "<결과DOCX>"
```

## 실패 시 처리

- 입력 없음 → "실행 막힘" 보고, 절대경로 재요청.
- 출력=입력 동일(`ValueError`) → `--output` 다른 경로 지정.
- AI 키 미연결 → 본문 자동작성/채점 생략 안내(구조·서식은 완성). 키 설정 후 재실행 권장.
- 공고 파싱 실패 → 채점 생략, 1회 완성으로 종료(공고 형식 확인 안내).
- 목표 미달(반복 소진) → 약점 섹션·[확인필요] 목록 보고, 사용자 보완 후 재실행 안내.

## 보고 형식

첫 줄 상태(`정상 실행 확인됨` / `수정만 완료` / `미검증` / `실행 막힘`). 이어서:
1. 최종 DOCX 경로 / 백업 / 통합 리포트(md)
2. AI 사용 여부 · 반복 횟수 · 공고 채점 추이(목표 도달 여부)
3. 서식 품질점수·게이트 / 차트·자리표시 / AI 보강 영역
4. **제출 전 [확인필요] 항목(핵심 수치·이력 검증)** — 반드시 사람이 확인
