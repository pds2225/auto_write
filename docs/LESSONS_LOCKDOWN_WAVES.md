# 교훈 잠금 계획 — A → B → C

> TASK: **T-20260831-01** (`TASK.md` LIST `[~]`). 사용자 요청(2026-08-31): 지금까지 난 오류를 **우선순위대로** 기계 가드로 닫는다.
> 기준: `app/tests/lessons_coverage.json` 151개 + 결함 코퍼스 D1–D6 + 스킬 L154–L156.
> 원칙: **151개 전부를 한 번에 재발 0으로 만들 수 없다.** 사람 판단(L005 눈검증, L009 날조)은 테스트가 대체하지 않는다.
> 기계화 4점(AW-008): **guard + test + coverage JSON + runtime wiring**. 하나라도 없으면 `mechanized` 표시 금지.

분류(사용자 확정): **문서가 다시 깨지는 것(A) → 제출·품질 게이트(B) → 이력서(C)**. D·E(COM·환경·작업방식)는 테스트로 못 막는 것이 많다.

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

## Wave B — 점수·제출·cross-form (다음)

우선: **L040** 필수서식 누락 `_DRAFT` · **L059** 작업접미사 제출폴더 오염(테스트만 있고 오케스트레이터 denylist 미배선) · **L016/L046** 자리표시 잔존 보강 · **L048** 원본·중간본 혼입 · **L049** 공고 PDF를 양식으로 채움 · **L050** 한글 전용인데 DOCX만 줌 · **L080** 라벨 칸 굵게 · **L095** 페이지 수 베이스라인.

L008/L017(테스트 없이 완료 보고)은 규약(E). L009 날조 본문은 judgment.

---

## Wave C — 이력서·신청서

**L038/L060** 정량 컬럼 유실 · **L039** 포트폴리오 이미지 마커 · **L043/L044** 슬래시 헤더·골격 · **L154** 최소 1섹션 샘플 · **L155** `#0000FF` 본문 금지 · **L156** 참고이미지 표 프레임 170×55mm · **L061** 출력 형식 사용자 확인.

L035/L036(키워드·자기기술서)은 사람 판단.

---

## Wave D·E — 변환·COM·에이전트

테스트보다 규약. L003/L026 COM, L004 왕복 일치도, L005 눈검증, L027–L030 추측패치, L067 `git add -A`, L105 스킬 훅 원문, L151 POSIX는 A6에서 코드 쪽만 잠금.

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
