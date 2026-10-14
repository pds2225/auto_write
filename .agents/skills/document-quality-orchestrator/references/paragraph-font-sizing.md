---
name: paragraph-font-sizing
description: >-
  완성 DOCX(사업계획서·R&D계획서·보고서)의 문단 글자크기 이상치(너무 작거나 너무 큰 글씨)를
  표준 본문 크기로 표준화한다. 본문 글씨가 8pt 미만으로 깨알같이 작거나 18pt 초과로 과하게 크게
  섞여 있어 "글자 크기가 들쭉날쭉/일관성 없음/제각각/너무 작다/너무 크다"는 지적이 나올 때 사용.
  글자크기 일관성 점수(15점)가 낮거나 품질 게이트를 통과 못할 때, "글자크기 정리/폰트 크기 통일/
  글씨 크기 맞춰줘" 요청 시 사용. "다시/재실행/수정/보완해줘" 같은 후속 요청도 이 스킬로 처리.
  주의: 이 보정은 서식 손상 위험이 있어 기본 비활성이며 enable=True를 명시해야만 동작한다.
---

# paragraph-font-sizing

## 목적
완성된 DOCX 본문 문단의 글자크기 이상치를 표준 본문 크기로 보정한다.
쉽게 말하면, 문서 안에서 어떤 줄은 깨알같이 작고 어떤 줄은 과하게 큰 식으로
글씨 크기가 제각각일 때, 비정상 범위의 글씨만 골라 본문 표준 크기로 맞춰
"글자 크기 일관성" 점수를 끌어올린다.

핵심 함수: `auto_write.services.doc_quality_ops.normalize_font_sizes(doc, ...)`
- 이 함수는 **기본 비활성**이다. `enable=True`를 넘겨야만 실제로 동작한다.
- AI를 쓰지 않는 결정론적(규칙 기반) 보정이다. API 키 없이도 동작한다.

## 적용 대상
- 대상 문서: 사업계획서(business_plan), R&D연구개발계획서(rnd_plan),
  컨설팅·정책자금·인증·수출·현장클리닉 보고서, 발표평가(pitch_deck), 기타 제출문서(generic_submission).
  유형과 무관하게 본문 글자크기 보정이 필요한 모든 완성 DOCX에 적용 가능하다.
- 보정 범위: **본문(표 밖) 단락의 런(run)만** 대상. `_iter_body_paragraphs(doc)`로 순회하므로
  표(table) 내부 셀 단락, 머리글/바닥글은 건드리지 않는다.
- 입력: python-docx `Document` 객체. 오케스트레이터가 백업 후 전달한다.
- 원본 DOCX를 직접 수정하지 않는다(오케스트레이터가 백업본을 거쳐 출력 경로에 저장).

## 탐지 규칙
`normalize_font_sizes`는 다음 조건을 **모두** 만족하는 런만 이상치로 탐지한다.

1. 본문(표 밖) 단락의 `w:r`(런)일 것.
2. 런에 `w:rPr`(런 서식) 노드가 있을 것. 없으면 건너뜀.
3. `w:rPr` 안에 `w:sz`(글자크기) 노드가 명시되어 있을 것. 없으면 건너뜀
   (= 스타일에서 상속받는 글씨는 손대지 않는다).
4. `w:sz`의 `w:val` 값을 숫자로 변환할 수 있을 것. 변환 실패 시 건너뜀.
5. 실제 포인트 크기가 표준 범위 `[min_pt, max_pt]`를 벗어날 것.

중요한 단위 규칙(헷갈리기 쉬움):
- DOCX의 `w:sz` 값은 **half-point(절반 포인트)** 단위다. 코드가 `pt = half_pt / 2.0`로 환산한다.
  예: `w:val="22"` → 11pt(정상), `w:val="14"` → 7pt(너무 작음), `w:val="40"` → 20pt(너무 큼).
- 기본 임계값(함수 기본 인자):
  - `min_pt = 9.0` → 9pt **미만**이면 이상치(작은 글씨).
  - `max_pt = 16.0` → 16pt **초과**면 이상치(큰 글씨).
  - 즉 9pt~16pt 범위 안의 글씨는 정상으로 보고 손대지 않는다.
- 역할/연결 기준의 "8pt 미만 / 18pt 초과"는 더 보수적으로 보정하고 싶을 때의 권장 운영값이다.
  그렇게 운영하려면 호출 시 `min_pt=8.0, max_pt=18.0`을 명시한다(아래 수정 규칙 참고).

## 수정 규칙
탐지된 이상치 런에 대해서만 다음을 수행한다.

1. `enable=True`가 아니면 **아무것도 하지 않고 0을 반환**한다(안전 기본값).
2. 이상치 런의 `w:sz` 값을 본문 표준 크기 `body_pt`(기본 11.0pt)로 덮어쓴다.
   - 저장 형식은 half-point이므로 `str(int(body_pt * 2))`로 기록한다(11pt → `"22"`).
3. 같은 런에 `w:szCs`(복합 문자용 크기)가 있으면 동일 값으로 함께 맞춘다.
   없으면 새로 만들지 않는다(구조 최소 변경).
4. 보정한 런 개수를 정수로 반환한다. 오케스트레이터가 품질 리포트에 집계한다.

권장 호출 형태(코드 직접 호출 시):
```
from auto_write.services.doc_quality_ops import normalize_font_sizes
# 함수 기본 임계값(9~16pt)으로 보정
count = normalize_font_sizes(doc, enable=True)
# 더 보수적으로 8pt 미만 / 18pt 초과만 보정
count = normalize_font_sizes(doc, enable=True, min_pt=8.0, max_pt=18.0)
```

오케스트레이터/CLI 경유 시:
- `run_all(doc, ..., normalize_fonts=True)` 또는 CLI `--normalize-fonts` 플래그가 곧
  `normalize_font_sizes(doc, enable=normalize_fonts)` 호출로 이어진다.

## 예외 규칙 (건드리지 않는 것)
- `enable`이 False(기본)면 전부 미동작. 명시적 활성화 없이는 절대 글씨를 바꾸지 않는다.
- 표(table) 내부 셀 단락의 글씨: `_iter_body_paragraphs`가 본문만 돌므로 제외.
- `w:rPr`이 없거나 `w:sz`가 명시되지 않은 런(스타일 상속 글씨): 제외.
- `[min_pt, max_pt]` 범위 안의 정상 크기 글씨: 제외(제목·강조 등 의도된 크기 보존).
- `w:val`이 비정상 문자라 숫자 변환 실패하는 경우: 건너뜀(파괴적 변경 회피).
- 머리글/바닥글, 이미지/도형 자체 크기: 대상 아님.

## 테스트 방법 (실제 PowerShell 명령)
사전 준비: 시스템 Python 3.11, `app/`이 sys.path 기준.

```
cd D:\auto_write\app

# 1) 폰트 보정 포함 전체 후처리 실행 (백업→분류→후처리→점수→리포트)
python document_quality_orchestrator.py "C:\경로\문서.docx" --output 결과.docx --normalize-fonts

# 2) 보정 전후 문단/표 구조 덤프로 글씨 변화 육안 확인
python _build_chochang.py inspect "결과.docx"

# 3) 하네스 회귀 테스트 (정상 동작 확인)
python -m pytest tests/test_document_quality_harness.py -q
```

함수 단위 빠른 확인(선택):
```
cd D:\auto_write\app
python -c "from docx import Document; from auto_write.services.doc_quality_ops import normalize_font_sizes; d=Document(r'C:\경로\문서.docx'); print('normalized=', normalize_font_sizes(d, enable=True))"
```
- `--normalize-fonts`를 빼면 보정이 동작하지 않는다(기본 비활성)는 점을 함께 확인한다.

## 실패 시 롤백 기준
글씨 보정 후 서식이 깨지거나(제목이 본문 크기로 뭉개짐 등) 결과가 의도와 다르면 즉시 롤백한다.

- 롤백 명령(백업 디렉토리 → 대상 파일 복원):
```
cd D:\auto_write\app
python document_quality_orchestrator.py --rollback "..\results\backup\<YYYYMMDD_HHMMSS>" 결과.docx
```
- 백업 위치: `D:\auto_write\results\backup\<YYYYMMDD_HHMMSS>\` (후처리 전 자동 백업됨).
- 롤백 판단 기준:
  - 정상 의도로 키운 제목/강조 글씨까지 본문 크기로 깎인 경우 → 롤백 후 임계값을
    `min_pt=8.0, max_pt=18.0`처럼 더 보수적으로 좁혀 재실행.
  - 보정 건수가 비정상적으로 많아 문서 전반 글씨가 균일하게 뭉개진 경우 → 롤백.
- 원본은 절대 덮어쓰지 않는다. 출력 경로가 입력과 같으면 오케스트레이터가 ValueError로 차단한다.
- 백업 없이 원본을 수정하지 않는다.

## 품질 점수 반영
- 직접 영향 항목: **글자 크기 일관성(15점)**.
  `doc_quality_score.score_document(...)`의 100점 배점 중 글자크기 일관성 15점에 반영된다.
- 게이트 영향: 총점 게이트(90↑우수 / 85↑통과 / 70↑보완필요 / 70미만실패, `passed = 총점>=85`)에서
  글씨 일관성 부족으로 통과 못 할 때 이 보정으로 점수를 보강할 수 있다.
- 단, 기본 비활성이므로 점수 개선을 원하면 `--normalize-fonts`(또는 `normalize_fonts=True`,
  함수의 `enable=True`)를 명시적으로 켜야 한다.

## 연결 코드·CLI (실제 함수/명령)
- 핵심 함수: `auto_write.services.doc_quality_ops.normalize_font_sizes(doc, *, body_pt=11.0, min_pt=9.0, max_pt=16.0, enable=False) -> int`
- 통합 실행기: `auto_write.services.doc_quality_ops.run_all(doc, *, normalize_fonts=False, ...) -> QualityOpsReport`
  (`font_sizes_normalized` 필드에 보정 건수 집계)
- 오케스트레이터: `auto_write.services.document_quality_orchestrator.DocumentQualityOrchestrator.run(input_docx, output_docx=None, normalize_fonts=False, ...)`
- 점수: `auto_write.services.doc_quality_score.score_document(...)` (글자 크기 일관성 15점 항목)
- CLI 진입점: `app/document_quality_orchestrator.py` (플래그 `--normalize-fonts`)
- 래퍼: `scripts/run_document_quality_harness.py`
- 진단: `app/_build_chochang.py inspect <docx>` (문단/표 덤프)
- 재사용 헬퍼: `docx_ops._iter_body_paragraphs`(본문 단락 순회 — 표 제외)
