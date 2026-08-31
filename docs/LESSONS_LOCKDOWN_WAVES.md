# 교훈 잠금 계획 — A → B → C

> TASK: **T-20260831-01** (`TASK.md` LIST `[x]`). 사용자 요청(2026-08-31): 지금까지 난 오류를 **우선순위대로** 기계 가드로 닫는다.
> 기준: `app/tests/lessons_coverage.json` 151개 + 결함 코퍼스 D1–D6 + 스킬 L154–L156.
> 원칙: **151개 전부를 한 번에 재발 0으로 만들 수 없다.** 사람 판단(L005 눈검증, L009 날조)은 테스트가 대체하지 않는다.
> 기계화 4점(AW-008): **guard + test + coverage JSON + runtime wiring**. 하나라도 없으면 `mechanized` 표시 금지.

이어가기 프롬프트(복붙)는 파일 아래 「이어가기 프롬프트」 절. `+프롬프트` 요청의 정본이다.

---

## 이미 잠긴 것 (A에서 다시 구현하지 않음)

| ID | 가드 |
|----|------|
| D1 / L002 / L145 / L074 | `_set_cell_text`/`_splice_run_text`가 그 칸만 `linesegarray` 지움. 전역 strip은 한글 납품 cleanup만. |
| D2 / L031 / L033 | `validate_table_grid` / `repair_table_grid` / `hwpx_doctor` |
| D3 / L006 / L083 | 검정 클론 + `force_black_text` |
| D4 / L022 | `auto`/테마색 보존 |
| D5 | `merge_trailing_empty_value_cells` (다열표 보존) |
| L007 L010 L011 L012 L013 L021 L023 L024 L025 L034 L045 L076 L086 L087 L089 L090 L091 | 기존 테스트·엔진 |

아직 안 닫힌 **다른 종류**의 겹침: 고정 칸 높이 넘침(L097), 양식 컨트롤+텍스트 이중표시(L086은 텍스트 기입 거부로 일부 잠김), 한글 픽셀 눈검증(이 클라우드에는 한글 없음, L005).

---

## Wave A — 문서가 다시 깨지는 것 (지금)

한 세션 = 아래 6개. 닫을 수 없는 것은 표에 **BLOCKED**로 남긴다.

| 순 | ID | 할 일 | 닫는 방법 |
|----|----|-------|-----------|
| A1 | D1 잔여 | `SubElement`만 막던 가짜 `linesegarray` 금지 테스트를 `etree.Element`·문자열 XML 우회까지 확장. `fill`만 타고 `submit`을 안 타도 자간 -50% → -30% | 소스 스캔 테스트 + `fill_hwpx`가 header `clamp_letter_spacing` |
| A2 | **D6** | 양식 자리표시 이름(홍길동) 검출 **미구현·skip** | `count_template_dummy_names` + 수용검사 fail. identity 값이면 허용(실명 홍길동 오탐 방지). skip 해제 |
| A3 | **L097** | 한 줄 칸에 긴 값 → 문서 전체 밀림 | 셀 폭·높이 대비 글자 폭 추정. 채움은 유지(데이터 손실 금지), `overflow_cells`로 보고 |
| A4 | **L032** | 서명일을 채팅/JSON 낡은 날짜로 복사 | `canonical_sign_date(today=)` — 넘긴 과거 날짜 무시, 실행일 스탬프 |
| A5 | L001 세로 | 그림 크기 가로만 봄 | `picture_display_wh` — `sz` 가로·세로 둘 다 >0 강제. 약한 grep 테스트 교체 |
| A6 | L096 / L151 | JSON이 갭인데 가드는 이미 있음 | L096=`force_signature_pos treatAsChar=0`. L151=백업이 `/tmp`가 아니라 산출물 옆/`results/backup`. 4점 맞으면 `mechanized`로 재분류 |

**이번 Wave에서 안 닫는 것**

| ID | 이유 |
|----|------|
| L005 한글 픽셀 눈검증 | 이 환경에 한글 없음. judgment |
| L003 COM 프로세스 종료 | Windows COM 전용. spy 가드는 Wave D |
| L009 날조 | 마커 잔존은 이미 게이트. “없는 경력을 지어냄”은 사람 판단 |
| 고정 칸 높이의 한글 렌더 넘침 | L097은 XML 추정만. 픽셀은 L005 |

---

## Wave B — 점수·제출·cross-form

우선(계획 ID): **L040** 필수서식 누락 `_DRAFT` · **L059** 작업접미사 · **L048** 원본·중간본 혼입 · **L049** 공고 PDF를 양식으로 채움 · **L050** 한글 전용인데 DOCX만 · **L080** 라벨 칸 굵게 · **L095** 페이지 수 베이스라인.

구현 상태·JSON 매핑은 아래 「Wave B (구현됨)」. L008/L017은 규약(E). L009 날조 본문은 judgment.

---

## Wave C — 이력서·신청서

**L038/L060** 정량 컬럼 · **L039** 포트폴리오 마커 · **L043/L044** 슬래시 헤더·골격 · **L154** 최소 1섹션 샘플 · **L155** `#0000FF` 본문 금지 · **L156** 참고이미지 170×55mm · **L061** 출력 형식 확인.

구현 상태는 아래 「Wave C (구현됨)」. L035/L036은 사람 판단.

---

## Wave D·E — 변환·COM·에이전트

테스트보다 규약. 상세 표는 아래 「Wave D·E — 변환·COM·에이전트 (규약 + spy)」.
JSON 잔여: **L050** 동일명 HWP+PDF 병행 생성. 쌍 검사·BLOCKED 생성 시도는 코드. 생성 성공 없이 mechanized 금지.

---

## 성공 기준 (Wave A)

- [x] D6 skip 해제, 홍길동 잔존이면 수용검사 fail, identity 허용 시 pass
- [x] `fill_hwpx`만으로 자간 -50 → -30
- [x] 가짜 `linesegarray` Element/문자열 XML 생성이 테스트에 걸림
- [x] 한 줄 칸 긴 값이 `overflow_cells`에 기록되고 값은 들어감
- [x] JSON 낡은 서명일이 실행일로 바뀜
- [x] 그림 `sz` 세로 0이면 실패
- [x] `lessons_coverage.json` counts = 실제 분류. L032/L096/L097/L151이 4점일 때만 mechanized
- [x] 관련 pytest 통과. 한글 눈검증은 BLOCKED로 명시

---

## 이어가기 프롬프트 (복붙)

사용자가 `+프롬프트` / `승인요청하지않고 … 끝까지` 를 말한 이유: 다음 에이전트가 “다음 웨이브 할까요?” 를 묻지 않게 한다.

```
승인 요청 금지. docs/LESSONS_LOCKDOWN_WAVES.md 정본. TASK T-20260831-01.
닫힘은 머지가 아니다. PR draft를 머지할지 묻지 마라. 사용자가 "머지"라고 한 뒤에만 Ready+auto-merge.
A/B/C/JSON gap/D규약/E규약은 이미 이 브랜치에 있다. 재구현 금지.
이미 엔진에 있는 것(lineseg, rowAddr, 파란예시, auto색, 안내문구, 원본덮어쓰기금지, D6, L032, L097, L001세로, L096/L151, L037공고채움금지, L059작업접미사, L080괄호볼드, L095페이지기준선, L038/L060정량컬럼, L003 kill spy, L004·L014·L048·L049·L072·L105)은 재구현 금지.
기계화 4점(guard+test+coverage JSON+runtime wiring) 없으면 mechanized 표시 금지.
JSON 본문과 계획 ID가 다르면 JSON 요약을 따른다.
L005 한글 픽셀·L009 날조 본문은 judgment. L008 폰트 위계는 judgment(run_all normalize_fonts 기본 False).
L154–L156은 lessons.md에 없으면 coverage JSON에 넣지 말고 코드+테스트만.
AW-008과 합치지 않음. 원본 덮어쓰기 금지. git add -A 금지. py -3.11 pytest (이 클라우드 python3).
남은 일(Windows 한글 PC만): L050 동일 stem PDF를 한글/rhwp로 실제로 만들고 L005 픽셀 눈검증. 이 클라우드에서 생성 성공으로 mechanized 올리지 마라.
151개 재발 0 보고 금지. “다음 웨이브 할까요?” 금지.
```

---

## Wave B — 점수·제출·cross-form (구현됨, JSON은 정직)

계획 ID → JSON 매핑 ( mechanized 는 JSON 요약이 실제로 잠긴 것만 ):

| 계획 | JSON | 상태 |
|------|------|------|
| L040 `_DRAFT` | L040 | 이미 mechanized. 오케스트레이터 `--required-doc` 추가 배선 |
| L059 작업접미사 | L059 | mechanized. warn + `work_suffix` / `needs_input` |
| L048 원본·중간본 혼입 | L048 은 PDF 합본 | mix denylist + **`merge_pdfs`/`announcement_tuple_stem` mechanized** |
| L049 공고 PDF 채움 | L037 | mechanized (`assert_not_announcement_form`). JSON L049 폴더는 gap 웨이브에서 mechanized |
| L050 한글전용 DOCX | L050 은 HWP+PDF 쌍 | 형식게이트는 `infer_hangul_required`. JSON L050 생성은 **gap/BLOCKED** |
| L080 괄호 라벨 굵게 | L080 | mechanized |
| L095 페이지 기준선 | L095 | mechanized (XML 추정. 한글 렌더 쪽수는 L005) |

**성공 기준 (Wave B)**

- [x] 필수서식 누락 시 파이프라인 `_DRAFT` (`required_documents`)
- [x] `_converted` / `_노트북LM` 파일명 warn + 오케스트레이터 기록
- [x] `모집공고.hwpx`·공고 PDF 를 `fill_hwpx`/`ensure_template_docx` 가 거부
- [x] 공고문 “한글 전용” → DOCX 산출 `_DRAFT` (형식 게이트)
- [x] `ㅇ (문제인식)` 만 굵게, 문장 중간 괄호는 그대로, `run_all` 배선
- [x] `fill_hwpx` 리포트에 `pages_before`/`pages_after`
- [x] JSON counts = 분류. L048 합본·L049 `제출/` 는 이후 JSON gap 웨이브에서 mechanized. L050 생성은 gap

---

## Wave C — 이력서·신청서 (구현됨)

- [x] L038 업체수·합계 행 파싱 보존
- [x] L060 강의 `kind`(구분) 보존 (judgment→mechanized)
- [x] L039 포트폴리오 마커 / L043 슬래시 헤더 / L044 골격 / JSON L061 사진칸 — `resume_layout_warnings`
- [x] 계획 L061 `--confirm-output-plan` 은 기존 `test_cross_form_output_policy.py` (JSON L061과 다름)
- [x] L154–L156 코드+테스트만 (`require_sample_ok`, `safe_body_accent`, `REF_IMAGE_FRAME_MM`). JSON 미수록

---

## Wave D·E — 변환·COM·에이전트 (규약 + spy)

**닫힘은 머지가 아니다.** 가드가 브랜치 코드·테스트에 있으면 그 항목은 닫힌 것이다. `main` 반영은 사용자가 "머지"라고 한 뒤에만 한다. Cursor 클라우드 PR은 draft라 GitHub 자동머지가 안 걸린다.

### Wave D — 변환·COM (Windows 한글 PC)

| ID | 분류 | 이 클라우드 | Windows 한글에서 할 일 |
|----|------|-------------|------------------------|
| L003 | mechanized (spy) | Linux `kill_hangul_processes` no-op. `_dispatch_hwp` 직전 호출은 유닛 spy | `taskkill /F /IM Hwp.exe` 실측. 이 프로세스 PID 는 대상 아님 |
| L005 | **judgment / BLOCKED** | 한글 GUI 없음. pytest PASS ≠ 픽셀 검증. `l005_pixel_review_status()` | 산출물을 **한글 2022(한컴오피스)** 로 연다. 글자겹침·쪽수·표격자·그림크기를 화면에서 본다. 스크린샷을 남긴다. 로직 리뷰는 검증이 아니다 |
| L050 | **gap / BLOCKED** | `missing_pdf_pair` + `try_generate_sibling_pdf`(rhwp 없으면 BLOCKED). soffice 는 레이아웃이 달라 인정하지 않음 | 최종본(비 `_DRAFT`) HWP/HWPX와 **같은 stem PDF** 를 한글 저장 또는 `rhwp export-pdf` 로 만든다. 초안은 쌍 불필요. 생성이 실제로 되기 전에는 mechanized 금지 |

- [x] L003 spy 배선 (`test_lockdown_wave_bc.py`)
- [x] L005 규약 문서 + BLOCKED 상태 함수. 카테고리 judgment 유지
- [x] L050 쌍 검사 + 생성 시도가 도구 없으면 BLOCKED. 카테고리 gap 유지

### Wave E — 에이전트 규약

| 규칙 | 분류 | 가드 |
|------|------|------|
| L067 `git add -A` 금지 | mechanized | `.gitignore` `.omc/` + `test_gitignore_protects_session_artifacts.py`. 실행 스크립트/CI 명령 스캔=`test_lockdown_wave_de.py`. 파일 명시 add 는 사람 워크플로 |
| L008 폰트 크기 위계 | judgment | `run_all(..., normalize_fonts=False)` 기본. 공고 명시 크기가 우선. 전 문서 폰트 강제 통일 금지 |
| L017 NotebookLM 프롬프트 | mechanized | `image_apply` (재구현 금지) |
| 스킬 훅 = 요청 원문 | 규약 | `AGENTS.md` §7 + `test_skill_request_hooks.py` |
| 승인 질문으로 웨이브 정지 금지 | 규약 | 이어가기 프롬프트 본문. “다음 웨이브 할까요?” / “머지할까요?” 금지 |

- [x] L067 스크립트 `git add -A` 스캔
- [x] L008 기본 비활성 고정 테스트
- [x] 이어가기 프롬프트에 닫힘≠머지 · 승인 금지 유지

## JSON gap 웨이브 (구현됨, L050 제외)

| ID | 가드 | 상태 |
|----|------|------|
| L004 | `extract_tax_invoice_buyer` — `(법인명)` 2번째, 이름 필터 없음. `company_extract` 배선 | mechanized |
| L014 | `style_generated_table` / `add_generated_table`. `_render_unhwp_table` 만. 폼 채움 표는 호출 금지 | mechanized |
| L048 | `merge_pdfs` + `announcement_tuple_stem`. 파이프라인 `evidence_pdfs` | mechanized |
| L049 | `build_submit_layout_dir` → `YYYYMMDD 공고명/제출`. cross_form·파이프라인 `notice_folder` | mechanized |
| L072 | 품질 오케스트레이터 점수 열등이면 백업 원복 | mechanized |
| L105 | `skill_frontmatter` `yaml.safe_load`. `description: [한글]` 거부 | mechanized |
| L050 | `missing_pdf_pair` + `try_generate_sibling_pdf`. rhwp 없으면 BLOCKED. soffice 미인정 | **gap / BLOCKED** |
