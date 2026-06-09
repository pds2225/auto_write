# 제출용 사업계획서 자동 생성 (Submission Pipeline / "/goal")

> 2026-06-08 신규. 브랜치 `feature/submission-100-auto`. 기존 품질 하네스와 별개의 end-to-end 자동화.

## 무엇을 하나
하나의 명령으로 다음을 순서대로 자동 수행한다:
1. **generate** — 양식의 빈 내용칸을 AI(또는 폴백)로 채운 초안 생성(목차/표 보존, 텍스트만).
2. **평가 루프** — 공고문 평가기준을 파싱해 AI 심사위원으로 채점 → 취약 섹션만 다시 작성 → 재채점을 목표점수/수렴까지 반복. 근거가 없어 못 올리는 항목은 **지어내지 않고** `needs_input`(직접 입력 권장)으로 보고.
3. **finalize** — 일반현황/개요 표·잔여 더미 정리(제출 마감).
4. **서식 품질 게이트** — 안내문구 삭제·글머리표/표 공백·강조 등 100점 서식 점검(내부 백업).
5. **이미지 최후 삽입** — 주요내용 **요약 인포그래픽**을 생성해 양식의 이미지 자리에 배치.

## 이미지(인포그래픽) 생성
- 1순위: **Gemini "Nano Banana"**(`gemini-2.5-flash-image`) — `GEMINI_API_KEY` 환경변수 필요.
- 2순위: **OpenAI**(`gpt-image-1`) — `OPENAI_API_KEY`.
- 키가 없으면: **무료 로컬 폴백**(원문에 수치가 있으면 matplotlib 막대차트, 없으면 Pillow 요약 카드). 외부 유료 호출 0.
- 사진이 아니라 "핵심 요약 인포그래픽" 스타일을 강제한다. (NotebookLM 은 공개 이미지 API 가 없어 현재 보조/수동 위치.)

## 실행 (PowerShell)
```powershell
# (선택) 인포그래픽 유료 생성 키 — 없으면 무료 폴백
$env:GEMINI_API_KEY = "<your key>"
# $env:OPENAI_API_KEY = "<your key>"

cd D:\auto_write\app
python -m auto_write.submit --project <project_id> --announcement-file "C:\경로\공고.txt" --target 95
# 공고문을 텍스트로 직접:
python -m auto_write.submit --project <project_id> --announcement "평가항목: 차별성 20점, 사업성 30점 ..." --target 95
# 이미지 끄기:
python -m auto_write.submit --project <project_id> --no-images
```

### 인자
| 인자 | 설명 | 기본 |
|---|---|---|
| `--project` | 대상 project_id (필수, 이미 양식분석+폼저장 완료 상태) | — |
| `--announcement` / `--announcement-file` | 공고문 텍스트/파일(txt·docx·pdf). 없으면 평가 루프 생략 | "" |
| `--target` | 공고 평가 목표 점수(이 점수까지 보완 반복) | 92 |
| `--max-iter` | 평가 보완 최대 반복 횟수 | 3 |
| `--no-images` | 이미지 삽입 비활성 | off |
| `--fill-plan-dir` | 양식별 `fill_plan.json` 디렉터리(표 좌표 채움) | 없음 |

## 산출물
- `results\제출초안_<project_id>_품질.docx` — 최종 제출초안(이미지 포함).
- 콘솔 JSON 리포트: 진행 단계(steps), 평가 결과(eval/needs_input), 이미지 생성·삽입 수.
- `results\backup\<타임스탬프>\` — 품질 게이트 단계 원본 백업.

## "100점" 운영 기준
공고 채점은 AI 라 호출마다 점수가 흔들린다. 그래서 "무조건 100"을 통과 기준으로 쓰지 않고, **2회 채점의 하한이 목표(기본 92↑) 이상 + needs_input 0건 + 서식 ≥ 85** 를 "제출 가능"으로 본다. 100점은 달성 시 표기한다. (근거 없는 내용을 지어내 점수를 올리는 것은 심사 탈락 위험이라 금지 — 부족 항목은 사용자 입력으로 보완한다.)

## 전제 / 한계
- `project_id` 는 먼저 양식 업로드·분석·폼 저장이 끝나 있어야 한다(웹 UI 또는 기존 흐름).
- 표 좌표 자동 채움(row_rewrites)은 양식마다 달라 `fill_plan.json` 으로 외부 제공해야 한다(없으면 해당 표는 비움 — 허위 충전하지 않음).
- 문단 앵커형 이미지 슬롯은 텍스트 정리 후 앵커가 사라지면 삽입이 실패할 수 있다(표 셀형 이미지 슬롯은 안정적). 실패는 리포트의 images.errors 에 표시.
