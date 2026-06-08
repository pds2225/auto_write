---
description: 인포그래픽·도식을 제안(기본)하거나 --apply 로 실제 차트/자리표시를 DOCX 에 삽입한다.
argument-hint: <입력DOCX경로> [--apply] [--out 결과.docx] [--max N] [--placeholder-only] [--json]
---

# /auto-write-images

## 사용 목적

완성된 DOCX 를 훑어 **어디에 / 어떤 시각화로** 인포그래픽·도식을 넣으면 좋은지 다룬다.
두 가지 모드가 있다.

- **기본(제안 모드, 읽기 전용)**: `infographic_suggest.suggest_images` 로 "이 위치에 이런
  그림" 을 표로 제안만 한다. 원본을 수정하지 않는다.
- **`--apply`(적용 모드, 실제 수정)**: `image_apply.apply_images` 로 제안 위치에 **실제로**
  시각화를 삽입한다.
  - 문서 **표에 명확한 (라벨, 숫자) 시계열**이 있으면 `chart_generator` 로 막대차트를 만들어 삽입한다(문서 원문 숫자만 사용).
  - 데이터가 없으면 **자리표시(placeholder)** 단락을 넣는다. 숫자는 절대 지어내지 않는다(빈칸 유지).

쉽게 말하면: 기본은 "여기에 이런 그림 넣어라" 추천, `--apply` 는 "실제로 그림(또는 그림 자리)을 넣어준다".

## 입력값

- `$1` (필수): 입력 DOCX 절대경로. 예) `C:\제출\사업계획서.docx`
- `--apply` (선택): 실제 삽입을 수행한다(미지정 시 제안만).
- `--out` / `-o` (선택, `--apply` 와 함께): 결과 DOCX 경로. 미지정 시 `results\<원본>_images.docx`.
- `--max N` (선택): 제안/적용 최대 개수. 기본 8.
- `--placeholder-only` (선택): 차트를 만들지 않고 자리표시만 삽입(가장 안전).
- `--json` (선택): 결과를 JSON 으로 출력.

규칙: **원본은 절대 덮어쓰지 않는다.** `--out` 을 입력과 같은 경로로 주면 `ValueError` 가 발생한다.

## 실행 워크플로우(단계)

1. 입력 경로 존재 확인. 없으면 "실행 막힘" 보고.
2. **제안 모드(`--apply` 없음)**: `suggest_images_docx(path, max_suggestions=N)` 실행 → 표/JSON 으로 정리.
3. **적용 모드(`--apply`)**: `apply_images(in, out, max_items=N, placeholder_only=...)` 실행.
   - 표 실측치가 있으면 차트, 없으면 자리표시. 결과 DOCX 와 삽입 집계(charts/placeholders)를 보고.
   - 원본 보존(out ≠ in). anchor 미발견 항목은 문서 끝에 추가됨을 보고.
4. 데이터바우처 등 이미지 장수 제한은 `qa_service` 담당임을 안내만 한다.

## 호출 에이전트

- `doc-analyzer`: 제안(`suggest_images`) 담당.
- `doc-postprocessor`: 적용(`image_apply.apply_images`) 담당(DOCX 변형).
- 전체 무인 파이프라인이 필요하면 `/auto-write-autopilot` 또는 `document-quality-orchestrator` 사용.

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 제안만 보기(읽기 전용)
python -c "import sys; sys.path.insert(0,'.'); from auto_write.services.infographic_suggest import suggest_images_docx; r=suggest_images_docx(r'C:\제출\사업계획서.docx', max_suggestions=8); print('기존이미지:', r.existing_images, '| 제안:', len(r.suggestions)); [print(f'- [{s.visual_type}] {s.caption} (키워드:{s.keyword})') for s in r.suggestions]"

# 2) 실제 삽입(표 실측치→차트, 없으면 자리표시). 원본 보존
python -c "import sys; sys.path.insert(0,'.'); from auto_write.services.image_apply import apply_images; r=apply_images(r'C:\제출\사업계획서.docx', r'D:\auto_write\results\사업계획서_images.docx'); print('차트', r.charts_inserted, '| 자리표시', r.placeholders_inserted, '| 출력', r.output_docx)"

# 3) 차트 없이 자리표시만(가장 안전)
python -c "import sys; sys.path.insert(0,'.'); from auto_write.services.image_apply import apply_images; r=apply_images(r'C:\제출\사업계획서.docx', r'D:\auto_write\results\사업계획서_ph.docx', placeholder_only=True); print('자리표시', r.placeholders_inserted)"
```

## 실패 시 처리

- 입력 경로 없음 → "실행 막힘" 보고, 절대경로 재요청.
- 출력=입력 동일 경로(`ValueError`) → `--out` 을 다른 경로로 지정 안내.
- 제안 0건 → 매칭 키워드(시장규모/추진일정/조직도/비즈니스모델/프로세스/경쟁사/매출)가 본문에 없음. 섹션 추가 작성 권장.

## 보고 형식

첫 줄에 상태 표시(`정상 실행 확인됨` / `수정만 완료` / `미검증` / `실행 막힘` / `수정 없음`).
- 입력 DOCX 경로(절대경로)
- (제안) 기존 이미지 수 + 제안 목록(시각화유형 | 캡션 | 키워드)
- (적용) 결과 DOCX 경로 + 차트 N건 / 자리표시 M건 + 백업/원본보존 여부
