---
description: 문서 내용을 분석해 인포그래픽·도식 삽입 위치를 제안하는 리포트를 생성한다(suggest_images, 실제 삽입 없음).
argument-hint: <입력DOCX경로> [--max N] [--json]
---

# /auto-write-images

## 사용 목적

완성된 DOCX(사업계획서·R&D계획서·컨설팅/정책자금/인증/수출/현장클리닉 보고서)를 훑어
**어디에 / 어떤 시각화 유형으로 / 어떤 캡션·생성 프롬프트로** 인포그래픽·도식을 넣으면 좋은지
**제안만** 한다. 실제 이미지는 삽입하지 않는다.

쉽게 말하면: "이 문장 근처에 이런 그림을 넣으면 보기 좋다"를 표로 알려주는 기능이다.
사용하는 핵심 코드는 `app/auto_write/services/infographic_suggest.py` 의 `suggest_images` 다.
결정론적(키워드 → 시각화 유형 매핑)이며 AI 를 호출하지 않는다.

## 입력값

- `$1` (필수): 입력 DOCX 절대경로. 예) `C:\제출\사업계획서.docx`
- `--max N` (선택): 제안 최대 개수. 기본 8. (`suggest_images`의 `max_suggestions` 인자)
- `--json` (선택): 결과를 JSON 으로 출력. 미지정 시 사람이 읽는 표 형태로 출력.

주의: 이 커맨드는 **읽기 전용**이다. 원본 DOCX 를 수정하거나 덮어쓰지 않는다.

## 실행 워크플로우(단계)

1. 입력 경로 존재 확인. 없으면 즉시 중단하고 "실행 막힘"으로 보고한다.
2. `doc-analyzer` 를 호출해 `suggest_images_docx(path, max_suggestions=N)`
   (내부적으로 `suggest_images(doc, max_suggestions=N)`)를 실행한다.
   - 문서 단락 + 표 첫 행(헤더) 텍스트를 앵커 후보로 수집한다.
   - 키워드 매칭으로 시각화 유형을 결정하되 **같은 유형은 1회만** 제안한다.
   - 기존 삽입 이미지 수(`existing_images`, `w:drawing` 카운트)를 함께 보고한다.
3. 결과(`InfographicReport`)를 표/JSON 으로 정리한다.
   각 제안 항목: `anchor_text`(제안 위치 단락), `visual_type`(시각화 유형),
   `caption`(문서 삽입용 캡션), `prompt`(이미지 생성 프롬프트), `keyword`(트리거 키워드).
4. 데이터바우처 등 이미지 장수 제한 경고는 본 커맨드 범위 밖(qa_service 담당)임을 안내만 한다.

## 호출 에이전트

- `doc-analyzer` (인포그래픽 제안 담당). `infographic_suggest.suggest_images` 호출 전담.
- 전체 품질 파이프라인(분류→후처리→PSST→이미지→점수→게이트)이 필요하면
  `/auto-write-quality` 또는 `document-quality-orchestrator` 스킬을 사용하라.

## 출력물

- 표준출력 리포트(제안 목록). 별도 파일을 생성하지 않는다.
- `--json` 지정 시 `InfographicReport.as_dict()` 구조의 JSON:
  `{ "suggestion_count", "existing_images", "suggestions": [ {anchor_text, visual_type, caption, prompt, keyword}, ... ] }`

> 전체 품질 하네스(`document_quality_orchestrator.py`)를 `--no-report` 없이 돌리면
> 이미지 제안 결과가 `D:\auto_write\results` 의 md/json 리포트에 함께 포함된다.

## 실패 시 처리

- 입력 경로 없음 → "실행 막힘" 보고, 올바른 절대경로 재요청.
- DOCX 가 아니거나 손상 → python-docx 로드 실패 메시지 원문 일부 + 쉬운 해석 제시.
- 제안 0건 → 매칭 키워드(시장규모/추진일정/조직도/비즈니스모델/프로세스/경쟁사/매출 등)가
  본문에 없다는 뜻. "수정 없음"으로 보고하고 해당 섹션 추가 작성을 권한다.

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 이미지 제안 리포트만 빠르게 보기(전체 파이프라인 미실행, 1줄 파이썬)
python -c "import sys; sys.path.insert(0,'.'); from auto_write.services.infographic_suggest import suggest_images_docx; r=suggest_images_docx(r'C:\제출\사업계획서.docx', max_suggestions=8); print('기존이미지:', r.existing_images, '| 제안:', len(r.suggestions)); [print(f'- [{s.visual_type}] {s.caption} (키워드:{s.keyword})\n  위치: {s.anchor_text[:60]}') for s in r.suggestions]"

# 2) JSON 으로 받기
python -c "import sys,json; sys.path.insert(0,'.'); from auto_write.services.infographic_suggest import suggest_images_docx; print(json.dumps(suggest_images_docx(r'C:\제출\사업계획서.docx').as_dict(), ensure_ascii=False, indent=2))"

# 3) 전체 품질 파이프라인 안에서 이미지 제안까지 한 번에(리포트 md/json 생성)
python document_quality_orchestrator.py "C:\제출\사업계획서.docx" --output 결과.docx

# 4) 진단으로 단락/표 먼저 확인(어떤 키워드가 있는지 점검)
python _build_chochang.py inspect "C:\제출\사업계획서.docx"
```

## 보고 형식

첫 줄에 상태 표시(`정상 실행 확인됨` / `미검증` / `실행 막힘` / `수정 없음`).
이어서 아래를 보고한다.

- 입력 DOCX 경로(절대경로)
- 기존 삽입 이미지 수(`existing_images`)
- 제안 건수와 각 제안: `시각화유형 | 캡션 | 트리거키워드 | 앵커 단락(앞 60자)`
- (`--json` 사용 시) 위 JSON 구조 그대로
- 본 커맨드는 원본을 수정하지 않으므로 항상 "수정 없음(읽기 전용)"을 명시한다.
