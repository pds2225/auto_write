---
description: 그림 위치를 제안(기본)하거나 --apply 로 NotebookLM 슬라이드 생성 프롬프트를 DOCX 에 삽입한다.
argument-hint: <입력DOCX경로> [--apply] [--out 결과.docx] [--max N] [--json]
---

# /auto-write-images

## 사용 목적

완성된 DOCX 를 훑어 **어디에 / 어떤 시각화로** 인포그래픽·도식을 넣으면 좋은지 다룬다.
제안은 **Claude(AI 키가 있으면)** 또는 **키워드 규칙(폴백)** 으로 만든다. 두 가지 모드가 있다.

- **기본(제안 모드, 읽기 전용)**: `infographic_suggest.suggest_images_ai` 로 "이 위치에 이런
  그림 / 이런 슬라이드 프롬프트" 를 표로 제안만 한다. 원본을 수정하지 않는다.
- **`--apply`(적용 모드, 실제 수정)**: `image_apply.apply_images` 로 제안 위치(anchor)에 **실제로**
  **NotebookLM 슬라이드 생성용 프롬프트 블록**을 삽입한다.
  - 차트(matplotlib)를 직접 그리지 않는다. 대신 그림 위치마다 "NotebookLM 에 붙여넣을 한국어
    프롬프트" 가 들어간다. 사용자가 그 프롬프트를 NotebookLM 슬라이드 생성에 붙여넣어 슬라이드를 만든다.
  - 프롬프트는 **문서에 실제로 있는 수치·항목만 쓰라**는 규칙으로 생성된다(숫자 날조 0).

쉽게 말하면: 기본은 "여기에 이런 그림 넣어라" 추천, `--apply` 는 "그 자리에 NotebookLM 슬라이드를
만들 프롬프트를 넣어준다". (NotebookLM 은 공개 API 가 없어 슬라이드 자동 생성까지는 못 하므로,
프롬프트를 넣어주는 반자동 방식이다.)

## 입력값

- `$1` (필수): 입력 DOCX 절대경로. 예) `C:\제출\사업계획서.docx`
- `--apply` (선택): 실제 삽입을 수행한다(미지정 시 제안만).
- `--out` / `-o` (선택, `--apply` 와 함께): 결과 DOCX 경로. 미지정 시 `results\<원본>_images.docx`.
- `--max N` (선택): 제안/적용 최대 개수. 기본 8.
- `--json` (선택): 결과를 JSON 으로 출력.

규칙: **원본은 절대 덮어쓰지 않는다.** `--out` 을 입력과 같은 경로로 주면 `ValueError` 가 발생한다.
참고: `--placeholder-only` 는 하위호환용 플래그로 남아 있으나 동작에 영향을 주지 않는다(항상 프롬프트 블록 삽입).

## 실행 워크플로우(단계)

1. 입력 경로 존재 확인. 없으면 "실행 막힘" 보고.
2. **제안 모드(`--apply` 없음)**: `suggest_images_ai_docx(path, openai_service=..., max_suggestions=N)`
   실행 → 표/JSON 으로 정리(위치·유형·슬라이드 프롬프트). AI 키 없으면 키워드 규칙으로 폴백.
3. **적용 모드(`--apply`)**: `apply_images(in, out, max_items=N, openai_service=...)` 실행.
   - 그림 위치마다 NotebookLM 슬라이드 프롬프트 블록을 삽입. 결과 DOCX 와 삽입 집계(prompts_inserted)를 보고.
   - 원본 보존(out ≠ in). anchor 미발견 항목은 문서 끝에 추가됨을 보고.
4. 사용자에게 "각 프롬프트를 NotebookLM 슬라이드 생성에 붙여넣고, 안내 블록은 삭제" 라고 안내한다.

## 호출 에이전트

- `doc-analyzer`: 제안(`suggest_images_ai`) 담당.
- `doc-postprocessor`: 적용(`image_apply.apply_images`) 담당(DOCX 변형).
- 전체 무인 파이프라인이 필요하면 `/auto-write-autopilot` 또는 `document-quality-orchestrator` 사용.

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 제안만 보기(읽기 전용, 키 없으면 키워드 폴백)
python -c "import sys; sys.path.insert(0,'.'); from auto_write.services.infographic_suggest import suggest_images_ai_docx; r=suggest_images_ai_docx(r'C:\제출\사업계획서.docx', max_suggestions=8); print('기존이미지:', r.existing_images, '| 제안:', len(r.suggestions)); [print(f'- [{s.visual_type}] {s.caption}\n  프롬프트: {s.slide_prompt}') for s in r.suggestions]"

# 2) 실제 삽입(그림 위치에 NotebookLM 슬라이드 프롬프트). 원본 보존
python -c "import sys; sys.path.insert(0,'.'); from auto_write.services.image_apply import apply_images; r=apply_images(r'C:\제출\사업계획서.docx', r'D:\auto_write\results\사업계획서_images.docx'); print('프롬프트', r.prompts_inserted, '| anchor미발견', r.anchors_missing, '| 출력', r.output_docx)"
```

> AI(Claude) 제안을 쓰려면 `openai_service` 를 만들어 인자로 넘긴다(키 없으면 자동 폴백). 무인
> 파이프라인(`run_autopilot`)은 가용 시 자동으로 Claude 를 사용한다.

## 실패 시 처리

- 입력 경로 없음 → "실행 막힘" 보고, 절대경로 재요청.
- 출력=입력 동일 경로(`ValueError`) → `--out` 을 다른 경로로 지정 안내.
- 제안 0건 → (키워드 폴백 시) 매칭 키워드(시장규모/추진일정/조직도/비즈니스모델/프로세스/경쟁사/매출)가
  본문에 없음. 섹션 추가 작성 권장. (AI 제안 시) 시각화가 필요한 섹션이 부족할 수 있음.

## 보고 형식

첫 줄에 상태 표시(`정상 실행 확인됨` / `수정만 완료` / `미검증` / `실행 막힘` / `수정 없음`).
- 입력 DOCX 경로(절대경로)
- (제안) 기존 이미지 수 + 제안 목록(시각화유형 | 캡션 | 슬라이드 프롬프트)
- (적용) 결과 DOCX 경로 + NotebookLM 프롬프트 N건 + 백업/원본보존 여부 + "NotebookLM 에 붙여넣기" 안내
