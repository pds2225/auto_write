# auto_write 범용 엔진 — 사업계획서 작성 규칙 내장 개발 계획 (개정 v4)

> 상태: **계획만 작성(소스 미수정, read-only 분석 완료)**
> 작성일: 2026-06-22 / 개정: 2026-06-22 (v3→v4: 아키텍트·비평 3차 피드백 반영) / 대상: `D:\auto_write\app`
> v4 개정 사유: ralplan 합의 리뷰에서 **rule-5 채점 연동의 전제 충돌(MAJOR, '재사용'이 아니라 가중치 0→비0 '동작 변경')·중첩표 fixer REUSE 명문화 및 단위테스트 공백(MEDIUM)·루프-내부 배치의 거짓 정당화 근거(MEDIUM, underline은 새 run을 만들지 않음)·골든 입도 및 rule-3 None-vs-value 분기 단언 공백(MINOR)·기존 dominant의 표셀 비대칭 서술 혼동(MINOR)·수렴 종료 서술 부정확(LOW)**이 추가 검증되어, 구현자가 거짓 전제를 신뢰하거나 회귀가 골든에 은폐될 지점을 정정함.
> v3에서 이미 반영된 사항(아키텍트·비평이 '검증완료·무조치'로 확인): 게이트 속성 `submittable`(passed 아님)·② walker 범위가 검출기 `doc.paragraphs`+`_dedup_cells`와 일치·`_set_run_color_black_unless_preserved`의 highlight/shd 부수삭제 회피·품질 오케스트레이터 루프가 `run_acceptance` 미호출(사후 게이트 유지)·⑤ 마커 주입의 fail→fail 전환·⑦ warn 무게이트 — **변경 없이 유지**.
> 분석 범위: `document_quality_orchestrator.py`(앱루트 CLI + `auto_write/services/document_quality_orchestrator.py` 서비스 본체), `doc_quality_ops.py`, `docx_ops.py`, `usage_acceptance.py`, `infographic_suggest.py`, `submittable_filler.py`, `doc_quality_score.py`, `submission_orchestrator.py`, `autopilot_pipeline.py`, `_build_chochang.py`
> 실제 소스 위치 확인: 정본은 `D:\auto_write\app\auto_write\services\*.py` (앱루트 CLI는 `D:\auto_write\app\document_quality_orchestrator.py`). worktrees·`_night_pilot` 복사본은 대상 아님.

---

## 0. 핵심 발견 (한눈 요약) — 개정

쉽게 말하면 — **"검사하는 눈"은 이미 거의 다 있고, "고치는 손"이 군데군데 빠져 있다. 단, 그 눈과 손은 같은 루프 안에서 서로를 보고 있지 않다(별개의 두 단계다). 그리고 기존 '손' 하나(색→검정 변환기)는 색만이 아니라 형광펜·음영까지 같이 지우므로, 그대로 문서 전체에 풀면 정당한 강조까지 날아간다. 또 한 가지(v4) — ⑤ '채점 연동 강화'는 기존 경로 '재사용'이 아니라, 지금 가중치 0(점수 미반영)인 항목을 비0으로 켜는 '동작 변경'이라 골든의 점수 지표를 직접 흔든다.**

- `usage_acceptance.py`(수용검사 엔진)에는 대부분의 **탐지(gate)** 가 이미 존재: 파란글씨 잔존(`check_residual_colored_runs` L399-439=fail, **색만 검사** — highlight·shd는 안 봄), `[확인필요]` 마커(`check_unresolved_markers`=fail), 빈 필수칸(`empty_label_fields`=fail), 양식 자리표시(=fail), 자기삽입 블록(=fail), 폰트 혼용(=fail), 글자크기 분산(warn).
- **고치는 쪽(fixer)** 은 흩어져 있다: 색→검정 변환은 **채움 쓰기 경로**(`docx_ops._set_run_color_black_unless_preserved` L61)에만 붙어 있고, 이는 **단일 run 변환기**이며 문서를 순회하지 않는다. **중요**: 이 변환기는 `w:highlight`(L66-68)와 `w:shd`(L69-71)를 **함께 제거**한다. 채움 경로에선 "양식 강조 잔재 제거"가 의도였지만, **후처리 단계에서 전 문서 run에 그대로 적용하면 정당한 형광펜 강조까지 삭제**된다. 검출기는 highlight를 보지 않으므로 '검출기 범위 일치'만으로는 이 부작용을 못 잡는다.
- 글꼴/크기 통일은 `doc_quality_ops.unify_paragraph_formatting`(L716에서 `enable=True` **라이브** 호출). `normalize_font_sizes`는 `enable=False` 기본(L719, run_all `normalize_fonts=False` 기본 L696)으로 **죽어 있음** → ③ target_pt는 "죽은 함수를 켜는 것"이 아니라 **라이브 `unify`와 정면 충돌하는 새 경로**다.
- NotebookLM 프롬프트는 `infographic_suggest`.
- **(검증으로 확정된 구조적 사실)**:
  - 품질 오케스트레이터 서비스 `run()`(`document_quality_orchestrator.py:110`)의 루프(`while iterations < _MAX_ITERATIONS`, L151)는 **`dq.run_all`만 반복 호출**(L153)하고 **`run_acceptance`는 한 번도 호출하지 않는다**(grep 0). 따라서 "수정→재검출 루프"는 이 레이어에 **존재하지 않는다.**
  - `run_acceptance`(수용판정)는 `submission_orchestrator.py:213` / `autopilot_pipeline.py:296` 에서만 호출되는 **사후 게이트**다(수정이 끝난 뒤 별도 단계).
  - **게이트 속성은 `AcceptanceReport.submittable`**(L152-153, `SEV_FAIL`만 평가)이다. `passed`는 **`CheckResult`(L135)와 오케스트레이터 `HarnessResult`에만 존재**하며, `AcceptanceReport`에는 없다. 실제 게이트 호출부도 `acc.submittable`(`submission_orchestrator.py:221`·`autopilot_pipeline.py:300`)을 쓴다. **→ 구현자가 `AcceptanceReport.passed`를 찾으면 `AttributeError`.** (게이트 속성은 본 계획 전반에서 `submittable`으로 통일)
  - 따라서 ②③⑤를 오케스트레이터 루프에 넣으면, 그 루프는 **1차로 `score.passed`(L193)일 때, 2차로 `abs(score.total - prev_total) < 0.5`(L195) 수렴일 때** 종료된다 — 즉 **"합격(passed) 또는 점수 수렴"** 둘 중 먼저 만족하는 조건으로 종료한다(v4 LOW 정정 — v3의 "score.total 수렴으로만 종료" 표현은 부정확). acceptance 결과는 어느 쪽에서도 보지 않는다. **새 패스의 멱등성이 깨지면 passed에도 못 닿고 수렴도 안 돼 최대 `_MAX_ITERATIONS`(=10)회를 소진**할 수 있다.

---

## 1. 규칙별 현황 표 — 개정

| # | 규칙 | 현재상태 | 구현·변경 위치 (파일 · 함수 · 검증된 라인) | 변경범위 | 난이도 | 회귀위험 |
|---|------|---------|------------------------------|---------|--------|---------|
| ① | 원본 서식 보존 | **구현됨** | `doc_quality_ops.py` 설계원칙(런 단위·w:t만), `unify_paragraph_formatting`(L716에서 `enable=True` **라이브**, 지배값=실재값만), 오케스트레이터 `run()` 백업·덮어쓰기 거부 | 유지 — 단 ③과 **상호배타 분기** 신설 필요(아래 §4 참조) | 낮음 | 낮음 |
| ② | 파란 글씨→검정 변환 | **부분(고치는 손 누락)** | 단일 run 변환기 `docx_ops._set_run_color_black_unless_preserved`(L61) — 채움 쓰기에서만 호출, **문서 전체 walker 없음**. **단 이 변환기는 highlight(L66-68)·shd(L69-71)도 제거**. 탐지 `usage_acceptance.check_residual_colored_runs`(L399-439, =fail, **색만**)는 **`doc.paragraphs`(본문 L433-434)+`_dedup_cells`(표 L435-437, 셀 안의 표까지 재귀: `_iter_cells` L181-182)** 스캔 | 신규: `doc_quality_ops.normalize_text_color()` — **검출기와 정확히 동일 범위(본문+표 셀, 중첩표 포함)**. **검출기가 공개한 `usage_acceptance.dedup_cells`(L220)를 import해 그대로 REUSE**(v4 — 동일 시그니처 재작성 금지, 재귀 누락 재발 차단). **단 색만 검정화하고 highlight/shd는 절대 건드리지 않는 별도 경량 변환 사용**(`_set_run_color_black_unless_preserved` **재사용 금지**) | 중간 | **중간** (표/중첩표 미커버 시 잔존 회귀 + **highlight/shd 부수삭제** 회귀) |
| ③ | 본문 10pt 통일 | **부분(+기존 라이브 통일과 충돌)** | `unify_paragraph_formatting`(L716 `enable=True` 라이브, 단락 **지배값** 통일, 분기는 `if dom_sz is not None` L574 truthiness 기반), `normalize_font_sizes`(`enable=False` 기본·body_pt=11.0·**죽어 있음**). 탐지 `check_font_size_spread`(warn) | 신규: target_pt 모드 — **켜지면 본문에서 '지배값 통일'을 끄는 상호배타 분기**(§4-핵심). **한 함수에 dominant/target 두 모드 응집 → 복잡도·테스트 표면 증가(수용된 유지보수 비용, §2-D-③ 주의)** | 중간~높음 | **높음** (지배값 vs 고정값 동시적용 시 비결정·비멱등; None-vs-value 분기 누수 시 size 값 드리프트가 골든 카운트로 은폐) |
| ④ | NotebookLM 그림 프롬프트 자동제안 | **구현됨** | `infographic_suggest.py`(`suggest_images_ai`, 폴백 `suggest_images`), 오케스트레이터 호출·리포트 기록 | 없음(유지) | 낮음 | 낮음 |
| ⑤ | 날조 0 (`[확인필요]` 표기) | **부분 — 단, 순증 가치 얇음(재평가)** | 탐지 강함: `check_unresolved_markers`(=fail), `_MARKER_RE`. 빈칸 탐지 `empty_label_fields`(=fail, `_LABEL_FIELDS` **정확매칭**). 오케스트레이터가 이미 `_count_confirm_markers`+`manual_review`로 신호 노출. **채점은 `doc_quality_score.py` L291-293에서 `empty_required_cells`를 '참고용 표기만(가중치 0) — 게이트 점수 미반영'으로 명시 제외 중** | **축소 + 동작 변경 명시**: 신규 fixer가 아니라 **채점 연동 강화(가중치 0→비0)**. **이는 '재사용'이 아니라 '동작 변경'이며 골든 score 지표를 흔든다**(v4 MAJOR). 마커 주입은 옵트인. | 중간 | **중간~높음** (점수 동작 변경이 None 경로 점수까지 흔들 수 있음 → 하위호환 테스트·골든 score 고정 필수) |
| ⑥ | 미확정 항목 공란 처리 | **구현됨** | `submittable_filler._blank_guides`/`_blank_residual`, `_build_chochang` 금액칸 `""` 공란. 탐지 `empty_label_fields`(fail)/`empty_table_rows`(warn) | 없음(유지). ⑤와 정책 결합 문서화만 | 낮음 | 낮음 |
| ⑦ | 협업사/실적 사실 기반 | **없음(정책만)** | 전용검사 부재(grep 0). 인접 `check_masking_violation`(blind 전용) | 신규: `check_unverified_claims()` — **warn·기본 off**. `_ALL_CHECKS`에 추가 | 중간~높음 | **높음**(오탐) — warn·off로 디리스크 |
| ⑧ | 에이전트 역할경계 준수 | **부분(코드 밖 규약)** | 모듈 책임분리(infographic=제안만, doc_quality_ops=결정론·AI금지, orchestrator=AI 미호출). 단 **§2-E 배선이 ⑧과 충돌 가능** | 코드 변경 거의 없음 + 회귀 가드 테스트 | 낮음 | 낮음 |

> ②③은 **신규 작업의 핵심이자 최대 리스크**(②는 walker 범위(중첩표 REUSE) + **highlight 부수삭제** 두 축, ③은 dominant↔target 모순 + None-vs-value 분기), ⑤는 **축소 재평가 + 채점 '동작 변경' 명시(골든 score 영향)**, ⑦은 **보수적 추가**, ①④⑥⑧은 **유지·연결·문서화**.

---

## 2. 개발 계획 — 개정

### 2-A. 규칙 on/off 설정 체계 (변경 없음 — 범용 엔진 제어성의 핵심)

**신규 파일: `auto_write/services/quality_rules.py`**
```text
@dataclass BizplanRulesConfig:
    preserve_original_format: bool = True       # ① 항상 권장 True
    color_to_black:          bool = True        # ②
    body_font_pt:            float | None = 10  # ③ None이면 target_pt 모드 끔
    suggest_notebooklm:      bool = True        # ④
    enforce_confirm_marker:  bool = False       # ⑤ 기본 off(축소·아래 §2-D-⑤ 참조)
    score_empty_required:    bool = False       # ⑤ 채점 연동(가중치 0→비0). 기본 off(하위호환). v4 신규
    blank_undecided:         bool = True        # ⑥
    flag_unverified_claims:  bool = False       # ⑦ 기본 off(오탐 위험)→warn
    # ⑧은 코드 구조로 강제(런타임 플래그 아님)

PRESETS:
    "bizplan": BizplanRulesConfig(score_empty_required=True)  # 사업계획서 풀세트(③ target_pt=10, ⑤ 점수 연동 on)
    "report":  color_to_black=True, body_font_pt=None, enforce_confirm_marker=False, score_empty_required=False
    "minimal": color_to_black=False, body_font_pt=None, enforce_confirm_marker=False, blank_undecided=False, score_empty_required=False
    "off":     모든 규칙 False(score_empty_required=False 포함)  # 현행 동작 보존(= ruleset=None과 논리 동등, 점수 불변)
```
- 문서유형 자동분류(`document_type_classifier.classify_text`)와 연동. CLI `--ruleset {bizplan|report|minimal|off}` 강제 가능.
- **v4 신규 플래그 `score_empty_required`**: ⑤의 점수 연동은 '동작 변경'이므로 별도 플래그로 게이팅한다. `ruleset=None` 또는 `off`/`report`/`minimal`에서는 항상 False → **None 경로 점수 불변**(하위호환). `bizplan`에서만 True.

### 2-B. 파일별 변경/신규 함수 — 개정 (MAJOR·MEDIUM 수정 반영)

| 파일 | 변경 유형 | 함수/내용 (개정 포인트는 **굵게**) |
|------|----------|-----------|
| `auto_write/services/quality_rules.py` | **신규** | `BizplanRulesConfig`(v4: `score_empty_required` 추가), `PRESETS`, `resolve_ruleset(doc_type, override)` |
| `doc_quality_ops.py` | 신규 함수 | ② `normalize_text_color(doc, preserve={...}) -> int` : **검출기 `check_residual_colored_runs`(L399-439)와 동일 범위 순회 — `doc.paragraphs`(본문)+검출기가 공개한 `usage_acceptance.dedup_cells`(L220)를 import해 그대로 REUSE**(v4 MEDIUM: 동일 시그니처 새 순회를 작성하지 말 것 — `_iter_cells` L181-182의 중첩표(셀 안의 표) 재귀를 놓치면 '고쳤는데 검출' 재발). **각 run 변환은 색(`w:color`)만 검정화하는 신규 경량 헬퍼를 사용 — `_set_run_color_black_unless_preserved`(L61)는 highlight(L66-68)·shd(L69-71)를 함께 제거하므로 재사용 금지.** 보존색 화이트리스트(`_PRESERVE_COLORS`/`_COLOR_PRESERVE`)·000000은 스킵. **검출기가 보는 범위 = fixer가 도는 범위가 정확히 같아야 함**(불일치 시 '고쳤는데 검출' 회귀). **highlight/shd는 후처리에서 절대 건드리지 않음**(정당한 형광펜 강조 보존). |
| 〃 | **상호배타 분기** | ③ `unify_paragraph_formatting(..., target_pt: float | None = None)` : **`target_pt`가 주어지면 본문 단락에서 `_dominant()` 기반 지배값 통일을 비활성하고 `target_pt`를 적용**(둘은 같은 본문 run에 동시 적용 불가 — 상호배타). **현행 분기는 `if dom_sz is not None`(L574) 식으로 None-vs-value를 구분하므로, target_pt 경로도 `is None`/`is not None` 명시 분기로 작성하고(truthiness 의존 금지) 실제 size 값을 단위테스트로 단언**(v4 MINOR — 분기 누수 시 size 값 드리프트가 골든 카운트로 은폐되는 것 방지). 제목(`Heading*`/`Title`/`제목`)·표 셀·캡션은 둘 다 스킵(기존 스타일 스킵 계승). **target_pt 모드는 멱등(2회차 0건)이어야 함.** **주의: dominant/target 두 모드를 한 시그니처에 응집해 복잡도·테스트 표면이 늘어남(수용된 유지보수 비용, §2-D-③).** |
| 〃 | `run_all` 확장 | `run_all(doc, *, rules: BizplanRulesConfig | None = None, ...기존 bool 인자 유지)` — **`rules=None`이면 현행과 논리 동등(기존 bool 인자 경로 그대로).** 현 시그니처는 keyword-bool 인자만(`doc_quality_ops.py` L690-698). rules 적용 시 **`unify_formatting`(지배값)과 `target_pt`는 본문에서 상호배타**로 라우팅. 순서: 안내삭제→글머리표→표공백→빈단락→**②색검정**→**③크기(지배값 OR target_pt 택1)**→강조→폰트. **하위호환은 §2-C의 `run_all(rules=None)==레거시` count 동등성 단위테스트로 명시 고정**. |
| `submittable_filler.py` | **축소** | ⑤ 기본은 **마커 주입 fixer 미도입**. `enforce_confirm_marker=True`일 때만 `enforce_confirm_markers(doc) -> int`(빈 필수칸→`[확인필요]`). **단 이 주입은 `empty_label_fields`(fail)를 `unresolved_markers`(fail)로 치환할 뿐 acceptance 판정(`submittable`)을 단독으로 제출가능까지 올리지 못함**(§2-D-⑤). ⑥ 기존 `_blank_*` 유지. |
| `usage_acceptance.py` | 신규 검사 | ⑦ `check_unverified_claims(doc, config)` — **warn·기본 off**. `_ALL_CHECKS`에 추가. **`AcceptanceReport.submittable`은 `SEV_FAIL`만 보므로(L152-153) warn 증가는 게이트에 무영향**(아래 §2-D-⑦에 근거 못박음). |
| `document_quality_orchestrator.py`(서비스 본체) | 배선 | `run(..., ruleset=None)` 추가. 루프 안 `dq.run_all`(L153)을 rules 기반으로 교체. **새 패스(②③⑤)는 루프 멱등성 불변식을 지켜야 함**(§2-D-loop). 리포트에 적용 규칙세트·②색변환수·⑤마커주입수·⑤점수연동 on/off·**score.total** 기록. **acceptance를 루프에 끌어들이지 않음**(ADR Alt-1 참조 — ⑧ 역할경계·수렴안정성 위해 사후 게이트 유지). |
| `document_quality_orchestrator.py`(앱루트 CLI) | 인자 추가 | `--ruleset {...}`, `--body-pt 10`, `--no-color-black`. |
| `doc_quality_score.py` | **채점 동작 변경(v4 MAJOR)** | ⑤ **`empty_required_cells`를 현재 '가중치 0(참고용 표기만, L291-293) — 게이트 점수 미반영'에서, `score_empty_required=True`일 때만 비0 가중치로 점수에 반영하도록 변경**. **이는 기존 경로 '재사용'이 아니라 '동작 변경'이다**(v3 서술 정정). 항목5(`table_quality`) 또는 별도 항목 점수가 바뀌므로 `score.total`이 변한다. **`score_empty_required=False`(=ruleset None/off/report/minimal)에서는 현행과 동일(점수 불변)** — 하위호환 단위테스트로 고정(§2-C). 마커 주입수는 informational. |

> **하위호환 원칙(불변)**: `ruleset=None` → 현행과 **논리 동등**(서식 카운트 **및 점수** 모두). 이는 §2-C의 게이트로 보증한다 — (a) **직접 단위테스트** `run_all(rules=None)`의 `QualityOpsReport` 카운트가 오케스트레이터 L153의 레거시 호출과 동일, (b) **점수 단위테스트** `score_empty_required=False`일 때 `compute_quality_score`의 `score.total`이 변경 전과 동일(v4 MAJOR — ⑤ 채점 동작 변경이 None 경로 점수를 흔들지 않음을 독립 고정), (c) 골든 **count + score.total 기반 불변**(바이트 아님).

### 2-C. 테스트 (unit / 회귀) — 개정 (MAJOR·MEDIUM·MINOR 반영)

**unit (신규 `tests/test_quality_rules.py` — 현재 부재 확인, 신규 생성)**
- ② **본문 blue run + 표 셀 blue run + 셀 안의 표(nested cell) blue run 셋 다** → `normalize_text_color` 후 전부 000000, 흰색·보존색 유지, **멱등(2회차=0)**. (v4 MEDIUM: 중첩표 셀 케이스 추가 — `dedup_cells` REUSE가 재귀를 보존하는지 직접 검증. 검출기 범위 = fixer 범위 일치 검증)
- ② **highlight/shd 보존**: blue+`w:highlight` run, 그리고 `w:shd` 음영 run을 넣고 `normalize_text_color` 적용 → **색은 000000으로 바뀌되 `w:highlight`·`w:shd`는 그대로 남아 있음**을 단언. (`_set_run_color_black_unless_preserved` 미사용 = 형광펜 강조 비삭제 검증)
- ③ 9pt/12pt 섞인 본문 → `target_pt=10` 후 본문 10pt, **제목/표 셀 미변경, 지배값 통일이 본문에서 비활성됐는지(상호배타) 검증**, **멱등(2회차=0)**.
- ③ **None-vs-value 분기 단언(v4 MINOR)**: (a) 모든 run이 테마 상속(size 미지정, `dom_sz is None` 경로)인 본문에서 `target_pt=10` 적용 시의 동작을 명시 단언(target 모드는 명시 size를 부여하되, dominant 경로의 `is None`→보존 의미와 혼동 없게 분기 고정), (b) **실제 `w:sz` 값(= target_pt*2 half-point)** 을 단언(카운트가 아니라 size 값 자체). truthiness 의존 분기가 새도 값 드리프트를 잡도록.
- ③-충돌: `unify_formatting=True` + `target_pt=10` 동시 요청 시 **target_pt가 본문 우선·지배값 미적용**임을 단위테스트로 고정(분기 회귀 방지).
- **하위호환-서식**: `run_all(doc, rules=None)`의 `QualityOpsReport` 카운트가 **레거시 호출**(오케스트레이터 L153과 동일 인자: `remove_guides/emphasize/underline/normalize_fonts`)의 카운트와 **동일**함을 단언.
- **하위호환-점수(v4 MAJOR 신규)**: `score_empty_required=False`(=ruleset None)일 때 미입력 필수셀이 있는 문서의 `compute_quality_score(...).total`이 **현행 값과 동일**함을 단언(⑤ 채점 동작 변경이 None 경로 점수를 바꾸지 않음). 추가로 `score_empty_required=True`일 때는 동일 문서의 `score.total`이 **변한다(낮아진다)** 는 것을 별도 단언(동작 변경이 의도대로만 작동).
- ⑤(옵트인 주입): 빈 필수칸 → `[확인필요]` 주입수=빈칸수, **주입 후 acceptance가 `empty_label_fields`(fail)→`unresolved_markers`(fail)로 전환됨**을 명시 검증(`submittable` 상승 없음), **멱등(2회차=0)**.
- ⑦ "삼성전자와 협업(확정)" vs "협력 검토 중" → 전자만 **warn**, **`AcceptanceReport.submittable` 불변** 검증.
- 프리셋: `bizplan`/`report`/`minimal`/`off` 켜지는 규칙 수 검증(`score_empty_required`는 `bizplan`만 True 확인).

**회귀 (기존 스위트 — 변경 0 통과 필수)**
- `tests/test_docx_ops.py`, `test_document_quality_harness.py`, `test_usage_acceptance.py`, `test_auto_write_apply.py`, `test_submission_pipeline.py`, `test_psst_mapping.py`.
- **골든 회귀 — '바이트 동일' 폐기, count + 핵심 size/score 값 기반 불변으로 재정의(v4 입도 강화)**:
  - 근거: python-docx 재직렬화는 zip 엔트리 순서·타임스탬프가 비결정적이라 **바이트 동일 달성 불가** → day-one 거짓실패 위험.
  - 골든 문서 `미래큐러스_제출본_autopilot_FIXED_20260610.docx`(앱루트 존재 확인)를 `ruleset=None`으로 돌린 뒤, **결정론적 지표가 변하지 않음**을 단언:
    - acceptance 결함 카운트(검사별 fail/warn 개수), 총 run 수, ②색변환 수(=0, None이면 미동작), ②highlight/shd 잔존 수(불변), ⑤마커 주입 수(=0), 문단·표 셀 수.
    - **(v4 MINOR) 본문 대표 run의 `w:sz` 값 1건 이상**: rule-3가 `if dom_sz is not None`(L574) truthiness에 의존하므로, 분기가 새도 카운트 동일로 size 값 드리프트가 은폐될 수 있음 → 값 자체를 baseline에 고정.
    - **(v4 MAJOR) `score.total`(또는 항목5 점수)**: ⑤ 채점 동작 변경이 None 경로 점수를 흔들지 않음을 골든으로도 고정(하위호환-점수 단위테스트와 이중 보증).
  - **baseline 캡처 절차**: 위 지표를 **정렬된 JSON**(`tests/golden/bizplan_baseline.json`)으로 1회 캡처해 저장 → 회귀는 JSON 동등 비교. 골든 docx는 앱루트에 두되 baseline JSON은 `tests/golden/`에 둔다.
  - **주의**: baseline 캡처가 `ruleset=None` 동작에 의존하므로, 위 **`run_all(rules=None)==레거시` 직접 단위테스트 + 하위호환-점수 단위테스트**가 baseline의 전제(논리 동등·점수 불변)를 독립적으로 고정한다. 골든 count/score 게이트만으로는 이 전제를 보증하지 못함.
- 실행: `python -m pytest -q tests/test_quality_rules.py` (**단독 foreground** — MEMORY.md `auto_write 테스트 단독 실행 규칙` 준수, 동시 실행 시 MemoryError 거짓실패). 신규 스위트도 동일 제약 적용.
- 각 .py 수정 후 `python -m py_compile <파일>`.

### 2-D. 핵심 리스크별 명시 처리 (피드백 직접 대응)

**[CRITICAL·명칭] 게이트 속성은 `AcceptanceReport.submittable`** (v3 확정 — 변경 없음)
- 사실: `AcceptanceReport.submittable`(L152-153, `SEV_FAIL`만 평가)이 게이트. `passed`는 `CheckResult`(L135)와 오케스트레이터 `HarnessResult`에만 존재하며 `AcceptanceReport`에는 없음. 실제 게이트 호출부도 `acc.submittable`(`submission_orchestrator.py:221`·`autopilot_pipeline.py:300`).
- 조치: 본 계획 전반에서 게이트 속성을 **`submittable`으로 통일**. 구현·테스트는 `acc.submittable`을 사용한다(`AttributeError` 차단).

**[⑤·MAJOR(v4)] '채점 연동 강화'는 '재사용'이 아니라 '동작 변경'**
- 사실: `doc_quality_score.py` L291-293은 `empty_required_cells`를 **'참고용 표기만(가중치 0) — 게이트 점수에는 반영하지 않는다'** 로 명시 제외 중. 따라서 v3가 말한 "기존 `empty_required_cells` 경로 재사용"은 부정확하다 — 점수에 반영하려면 **가중치 0→비0으로 바꾸는 동작 변경**이 필요하고, 이는 항목5(`table_quality`) 또는 별도 항목을 통해 **`score.total`을 직접 흔든다**.
- 위험: 골든 baseline(v3)이 acceptance count는 잡아도 **score 변동은 안 잡았다**. 동작 변경이 None 경로 점수까지 흔들면 회귀가 은폐된다.
- 조치: (a) 동작 변경을 **`score_empty_required` 별도 플래그로 게이팅**(기본 off, `bizplan`만 on). (b) **하위호환-점수 단위테스트**로 `score_empty_required=False`일 때 `score.total` 불변을 고정(§2-C). (c) **골든 baseline에 `score.total`(또는 항목5 점수) 추가**로 None 경로 점수 불변을 이중 고정. (d) `score_empty_required=True`일 때 점수가 의도대로 낮아지는지 별도 단위테스트.

**[②·중첩표 REUSE·MEDIUM(v4)] 검출기-fixer 범위 일치는 'REUSE'로 명문화**
- 사실: 검출기 `_dedup_cells`→`_iter_cells`(L181-182)는 **셀 안의 표(nested cell)까지 재귀**한다. 공개 별칭 `dedup_cells`(L220)가 이미 존재한다("제거기가 검출과 같은 셀 순회를 쓰도록 공개 — 순회가 어긋나면 '지웠는데 검출됨' 재발"이라는 주석까지 달려 있음).
- 위험: v3는 walker를 "검출기와 동일 범위로 순회"한다고만 했고 **import REUSE를 명문화하지 않아**, 구현자가 동일 시그니처의 새 순회를 작성하면 중첩표 재귀를 놓칠 여지가 있었다.
- 조치: ② fixer는 **`from ... import dedup_cells`(L220)로 검출기의 순회를 그대로 import해 REUSE**한다(동일 시그니처 재작성 금지). **중첩표 셀 blue run 단위테스트 1건 추가**(§2-C)로 재귀 보존을 직접 검증.

**[loop·구조 GAP] 오케스트레이터 while-loop 멱등성/수렴 불변식 — 루프-내부 배치 채택 사유(거짓 근거 정정)**
- 사실: `run()`은 `while iterations < _MAX_ITERATIONS`(=10, L38·L151)로 `dq.run_all`(L153)을 반복, `iterations>=2`에 underline 보강(L157), **1차 `score.passed`(L193) 또는 2차 `abs(score.total - prev_total) < 0.5`(L195) 수렴**으로 종료.
- 규칙(런타임 계약): ②③⑤ 새 패스는 **2회차 호출 시 0건 변경(멱등)** 이어야 한다. 비멱등 패스는 passed에도 못 닿고 수렴도 못 해 `_MAX_ITERATIONS`를 소진한다.
- **루프-내부 배치 채택 사유(v4 MEDIUM 정정 — 거짓 근거 제거)**: v3는 "2회차 underline 보강 run이 비검정 색을 도입할 여지"를 근거로 들었으나 **이는 소스상 거짓**이다 — `emphasize_key_sentences(underline=True)`는 기존 run의 `rpr`에 **`w:u`만 append**할 뿐(doc_quality_ops.py L368-371) **새 run·새 색·새 크기를 만들지 않는다**. 따라서 "현재 underline 패스가 비검정 run을 만든다"는 전제는 폐기한다.
  - **정정된 실제 근거**: 루프-내부 배치는 **미래 패스 대비 순서 일관성 / 단일 정규화 상태 유지**를 위한 것이다. 색·크기 규칙이 매 반복마다 동일 정규화 상태를 보장하면, 향후 루프 내 다른 패스가 새 서식을 만들더라도 같은 기준으로 재정규화된다(현재 underline 패스가 그 문제를 만든다는 뜻이 아님).
  - **(v4 검증 권고)** 글머리표 정리·표 공백 정리 등 **다른 루프-내부 패스**가 새 run을 만들 가능성은 별도 검증 대상이다(정정 근거의 실제 후보). 이 검증은 Follow-up 5로 둔다.
- **안전장치를 멱등 강제로 이중화**: (a) 각 신규 패스 **멱등 단위테스트(2회차=0)** 필수(§2-C), (b) observability로 리포트에 패스별 변경수·반복 횟수 기록(§3) → 수렴 소진을 사후 즉시 진단. 향후 비멱등 패스 필요 시 그 패스만 루프 밖으로 빼는 것을 follow-up으로 둔다(ADR Follow-up 4).
- 결론: **루프-내부 + 멱등 강제(테스트+observability)**. 단발 구조 분리는 "기본값"이 아니라 "비멱등이 불가피할 때의 탈출구"로 문서화.

**[②·MAJOR] 검출기-fixer 범위 일치 + highlight/shd 부수삭제 방지**
- 범위: `normalize_text_color`는 `check_residual_colored_runs`(L399-439)가 보는 **본문(`doc.paragraphs` L433-434)+표(검출기 공개 `dedup_cells` L220, 중첩표 포함)** 를 정확히 같은 범위로 순회(REUSE). 표/중첩표 누락 시 fail 잔존 → 표·중첩표 단위테스트 포함(§2-C).
- **부작용(핵심)**: 범위 일치는 *필요조건일 뿐 충분조건이 아니다*. `_set_run_color_black_unless_preserved`(L61)는 색뿐 아니라 `w:highlight`(L66-68)·`w:shd`(L69-71)도 제거한다. 검출기는 highlight를 보지 않으므로 '검출기 범위 일치'만으로는 이 부작용을 못 잡는다. → walker는 **색(`w:color`)만 검정화하고 highlight/shd는 손대지 않는 신규 경량 변환**을 사용한다(L61 헬퍼 재사용 금지). highlight/shd 보존을 §2-C 단위테스트로 못박는다.

**[③] ①-vs-③ 핵심 충돌(사용자 최우선 질문) — 상호배타로 해소**
- 사실: `unify_paragraph_formatting`은 `run_all`에서 `enable=True`(L716)로 **라이브** 호출되어 본문/표 run을 `_dominant()` 지배값으로 이미 재작성 중. `normalize_font_sizes`는 `enable=False` 기본으로 **죽어 있음**. 따라서 target_pt는 "죽은 함수를 켜는 것"이 아니라 **라이브 `unify`와 정면 충돌하는 새 경로**다. 같은 본문 run에 '지배값 통일'과 '고정 10pt' 두 목표를 더하면 비결정·비멱등.
- 해소: **`target_pt`가 켜지면 본문 단락에서 지배값 통일을 비활성**(상호배타). 제목/표/캡션은 둘 다 스킵 유지. **분기는 `is None`/`is not None` 명시(L574 truthiness 패턴 답습 금지)로 작성하고, size 값 자체를 단위테스트로 단언**(v4 MINOR).

**[③·표셀 비대칭 명확화·MINOR(v4)] 현행 dominant의 표셀 처리 vs rule-3 target의 표셀 스킵 구분**
- 사실: 현행 `unify_paragraph_formatting`의 표 순회(L522-531)는 **2-level 루프 + `id(cell._tc)` dedup** 으로 **중첩표에는 재귀하지 않는다** — 검출기·`_dedup_cells`와 **비대칭**이다. 즉 현행 dominant 모드는 **표 셀(1-level)을 라이브로 처리 중**이다.
- rule-3(target_pt)는 **본문만 적용, 표 셀은 dominant·target 둘 다 스킵**으로 한정하므로 이 비대칭을 우회한다(rule-3 자체엔 무해). **다만 독자 혼동을 막기 위해 명확화한다**: "rule-3 target_pt는 표 셀에 적용하지 않는다(스킵)"는 **rule-3의 새 동작**이고, "현행 dominant 통일이 표 셀(1-level)을 라이브로 손댄다"는 **기존 동작**이다 — 둘은 별개다. rule-3가 표 셀을 스킵한다고 해서 기존 dominant의 표셀 처리가 사라지는 것은 아니다(현행 표셀 dominant 처리는 `target_pt`가 None일 때 그대로 유지).

**[⑤] 자기상충 + 과대범위 — 축소 + 채점 동작 변경 분리**
- 사실: `empty_label_fields`는 `_LABEL_FIELDS` 정확매칭만 잡고, 빈칸에 `[확인필요]` 주입 시 `check_unresolved_markers`(=fail)를 새로 유발 → **empty-cell fail이 marker fail로 치환될 뿐, `submittable`을 단독으로 제출가능까지 올리지 못함**. 오케스트레이터가 이미 `_count_confirm_markers`+`manual_review`로 동일 신호 노출.
- 결정: ⑤를 **신규 fixer 기본 도입에서 제외(마커 주입 기본 off)**. 우선은 **채점 연동(`score_empty_required`)** 으로 한정하되, 이는 위 [⑤·MAJOR]대로 **'동작 변경'으로 명시·플래그 게이팅·하위호환 테스트** 동반. 마커 주입은 `enforce_confirm_marker=True` 옵트인으로만, "fail→fail 전환"을 명시적 트레이드오프로 문서화.

**[⑦] warn 게이트 무영향 못박기**
- `AcceptanceReport.submittable`은 `SEV_FAIL`만 평가(L152-153)하므로 ⑦의 warn 증가는 **현재 게이트에 영향 없음**. 다운스트림이 warn 증가를 실패로 보지 않음을 계획에 명시(근거: L152-153).

**[⑧] §2-E 배선과 역할경계 충돌 방지**
- acceptance(검수)를 오케스트레이터(수정) 루프에 호출해 detect→fix를 강결합하려는 유혹이 있으나, 이는 §8 역할경계("검수기는 생성 안 함")와 상충하고 수렴 안정성도 해친다. → **acceptance는 사후 게이트로 유지**(ADR Decision). 회귀 가드 테스트로 "생성기↔검수기" 분리 고정. (검증: 품질 오케스트레이터 루프는 `run_acceptance`를 호출하지 않음 — grep 0.)

### 2-E. 단계 순서 (의존성 기반) — 개정

1. **[기반]** `quality_rules.py`(프리셋·플래그, **`score_empty_required` 포함**) 신설 + 문서유형↔프리셋 매핑. (회귀위험 0)
2. **[②]** `normalize_text_color`(**검출기 공개 `dedup_cells`(L220) REUSE + 색만 변환·highlight/shd 보존 경량 헬퍼**) + `run_all` 배선 + **본문/표 셀/중첩표 셀 + highlight·shd 보존 + 멱등** unit.
3. **[③]** `unify_paragraph_formatting(target_pt=)` **상호배타 분기(None-vs-value 명시)** + 충돌·멱등·**size 값 단언** unit.
4. **[하위호환-서식]** `run_all(rules=None)==레거시` count 동등성 unit 고정(②③ 배선 직후, 골든 캡처 전제 확보).
5. **[⑤채점 동작 변경]** `doc_quality_score`에 `score_empty_required` 게이팅 추가(가중치 0→비0). **하위호환-점수 unit(None일 때 score.total 불변) + on일 때 점수 하락 unit** 필수. 마커 주입은 옵트인 + fail→fail 트레이드오프 문서 + 멱등 unit.
6. **[배선]** 오케스트레이터 `run(ruleset=)` + CLI 인자 + 리포트 항목(②변환수·②highlight 잔존수·⑤마커수·**score.total**) + **count + size + score.total 기반 골든 회귀(baseline JSON)**. **루프 멱등 불변식 + 루프-내부 배치 사유(정정된 근거) 명시.** acceptance는 사후 게이트 유지.
7. **[⑦]** `check_unverified_claims`(warn·off) + warn-무영향(`submittable` 불변) unit.
8. **[④⑧]** 유지 확인 + ⑧ 역할경계 회귀 테스트 고정 + 문서화.

> **루프 멱등 불변식(2·3·5 공통)**: 각 신규 패스는 동일 문서 2회 적용 시 2회차 변경 0건. 위반 시 §2-D-loop의 수렴 소진 회귀가 발생하므로 단위테스트로 차단. 단발 구조 분리는 비멱등 불가피 시의 탈출구(ADR Follow-up 4).

---

## 3. RALPLAN-DR 요약 — 개정

**모드: DELIBERATE** (rule-5 채점 '동작 변경' 전제충돌 1[MAJOR]·중첩표 REUSE 공백 1[MEDIUM]·루프 거짓근거 1[MEDIUM]·골든 입도/None-vs-value 1[MINOR] 등 high·mid-severity 합의 → 사전부검·확장 테스트 동반)

### Principles (원칙) — 개정
1. **탐지·수정 범위 일치(단일 진실원천, REUSE) + 부작용 격리**: 수정기(`normalize_text_color`)는 검출기(`check_residual_colored_runs`)가 **보는 범위를 검출기 공개 `dedup_cells`(L220) import로 그대로 REUSE**(중첩표 재귀 보존)하되, **검출기가 보지 않는 속성(highlight/shd)은 절대 변경하지 않는다**(범위 일치=필요조건, 부작용 격리=충분조건). 오케스트레이터 루프는 acceptance를 호출하지 않으며 결합은 "같은 범위/같은 기준" 수준에서만 보장한다.
2. **날조 0 불변**: 없는 수치 생성 금지, 미확정은 공란 또는 `[확인필요]`. 어떤 플래그로도 끌 수 없음.
3. **하위호환·옵트인·점수 불변**: 신규 규칙은 명시적으로 켤 때만. `ruleset=None`은 현행과 **논리 동등(서식 카운트 + score.total 둘 다)** 이며, 이를 **직접 단위테스트(`run_all(rules=None)==레거시` count + `score_empty_required=False`일 때 score.total 불변) + 골든 count/size/score 불변**으로 이중 보증(바이트 아님). ⑤ 채점 연동은 '재사용'이 아니라 '동작 변경'이므로 별도 플래그로 게이팅.
4. **보수적·멱등·오탐0 우선**: 모든 신규 패스는 2회차 0건(멱등) — 루프 수렴(passed 또는 점수수렴) 보호. 정상 문서는 덜 고친다(특히 ⑦).
5. **결정론·역할경계**: AI 없이 동일입력→동일결과. 검수기(acceptance, `submittable` 게이트)와 생성/수정기(doc_quality_ops)는 같은 루프에서 섞지 않는다.

### Decision Drivers (top 3) — 개정
1. **회귀 안전성** — 골든 문서 불변(②③ 서식 충돌·**highlight 부수삭제**·**비멱등 수렴소진**·**⑤ 채점 동작 변경의 None 경로 점수 누수**·**rule-3 size 값 드리프트**가 최대 리스크). 게이트는 **count + size 값 + score.total + 직접 동등성 테스트**.
2. **범용 엔진 제어성** — 사업계획서 규칙의 무분별 적용 방지 → 프리셋/플래그(특히 ⑤ `score_empty_required` 게이팅) 필수.
3. **범위 일치(REUSE)·부작용 격리·중복금지** — 검출기 범위 = 수정기 범위(공개 `dedup_cells` REUSE로 중첩표 재귀 보존), **단 highlight/shd 비변경**, 색변환은 신규 경량 헬퍼(L61 재사용 금지)로 '고쳤는데 검출'·'강조 증발' 두 회귀 동시 차단.

### Viable Options (≥2)

**A. 기존 `doc_quality_ops` 확장 (함수 추가 + run_all 인자 확장) + 검출기 공개 순회 REUSE walker(색만 변환)**
- pros: 헬퍼·검출기 순회 최대 재사용, 변경면 작음, 회귀위험 최소, 중첩표 재귀 자동 보존.
- cons: 시그니처 비대화, ③ 상호배타 분기가 한 함수에 응집(§2-D-③ 비용).

**B. 새 규칙 모듈 분리 (`bizplan_rules.py` 독립 구현)**
- pros: 도메인 규칙 응집, ⑧ 역할경계 부합.
- cons: 색변환·폰트통일·셀 순회 재구현 시 **중복**(원칙3 위반) + **중첩표 재귀 누락 위험** → 결국 기존 헬퍼·`dedup_cells` import 필요, 실익 적음.

**C. 프리셋 규칙세트(`quality_rules.py` config/PRESETS, `score_empty_required` 포함) + A 결합** — **권고**
- pros: 제어성(드라이버2) 최적, A의 재사용 + on/off를 config로 분리, ③ 상호배타·멱등·⑤ 점수 동작 변경을 config 플래그 기준으로 테스트 가능.
- cons: config 1개 추가 배선 비용, 프리셋↔문서유형 매핑 별도 관리.

> **권고: C + A.** B의 "모듈 분리"는 신규 **검사(⑦)** 와 config에만 적용, **수정 로직은 기존 `doc_quality_ops` 확장(A) + 검출기 `dedup_cells` REUSE**로 중복·중첩표 누락 회피. 단 ② 색변환만은 **신규 경량 헬퍼**(L61 재사용 금지, highlight/shd 보존).

### Pre-mortem (실패 시나리오) — DELIBERATE 갱신
1. **'고쳤는데 계속 검출' 회귀**: `normalize_text_color`가 표/중첩표 셀을 빠뜨려 검출기는 fail 유지. → 완화: 검출기 공개 `dedup_cells`(L220) **REUSE**(동일 시그니처 재작성 금지), 표 셀 + **중첩표 셀** 단위테스트 필수.
2. **'강조 증발' 회귀**: walker가 `_set_run_color_black_unless_preserved`(L61)를 재사용해 정당한 형광펜·음영까지 전 문서에서 삭제. 검출기는 highlight를 안 보므로 게이트가 못 잡음. → 완화: 색만 바꾸는 신규 경량 헬퍼 + highlight/shd 보존 단위테스트.
3. **수렴 소진(10회 burn)**: 비멱등 ②/③/⑤가 매 패스 변경을 만들어 passed(L193)에도 못 닿고 `abs(score.total-prev_total)<0.5`(L195)에도 영영 도달 못함. → 완화: 모든 신규 패스 2회차=0 멱등 테스트 + observability. 비멱등 불가피 시 해당 패스만 루프 밖 단발로(Follow-up 4).
4. **하위호환 무성 회귀(서식)**: `run_all`에 `rules` 인자를 더하며 기본 경로 count가 미세 변동 → 골든 baseline이 그 변동을 "정상"으로 캡처해버려 회귀 은폐. → 완화: `run_all(rules=None)==레거시` 직접 count 동등성 단위테스트로 골든 캡처 전제를 독립 고정.
5. **⑤ 채점 동작 변경의 점수 누수(v4 신규)**: `empty_required_cells` 가중치를 0→비0으로 바꾸며 `score_empty_required=False`(None 경로)에도 점수가 미세 변동 → 골든 baseline(score 미포함 시)이 못 잡음. → 완화: **하위호환-점수 단위테스트(None일 때 score.total 불변) + 골든 baseline에 score.total 추가**로 이중 고정.
6. **rule-3 size 값 드리프트(v4 신규)**: `target_pt` 분기가 `if dom_sz`(truthiness)처럼 새도 실제 `w:sz` 값이 달라지는데 카운트만 보는 골든은 동일로 통과. → 완화: rule-3 단위테스트에 **None-vs-value 명시 단언 + size 값 단언**, 골든에 **본문 대표 run size 값** 추가.
7. **골든 게이트 day-one 거짓실패**: '바이트 동일' 단언이 zip 순서·타임스탬프 비결정성으로 실패. → 완화: count + size + score 기반 baseline JSON 비교로 재정의(§2-C).

### Expanded Test Plan — DELIBERATE 갱신
- **unit**: ②(본문+표 셀+**중첩표 셀**, 멱등) / ②(**highlight·shd 보존**) / ③(target_pt, 상호배타, 멱등, **None-vs-value 분기 + size 값 단언**) / **하위호환-서식(`run_all(rules=None)==레거시` count)** / **하위호환-점수(`score_empty_required=False`일 때 score.total 불변 + True일 때 하락)** / ⑤주입(fail→fail 전환, `submittable` 불변, 멱등) / ⑦(warn·`submittable` 불변) / 프리셋(`score_empty_required`는 bizplan만 True).
- **integration**: 오케스트레이터 `run(ruleset='bizplan')` 1회 → acceptance 사후 게이트(`submittable`) 통과/실패 분기, 리포트 항목(②변환수·②highlight 잔존수·⑤마커수·**score.total**) 기록.
- **e2e(회귀)**: 골든 docx `ruleset=None` → baseline JSON **count + 본문 대표 run size 값 + score.total** 동등(바이트 아님).
- **observability**: 리포트에 적용 규칙세트·반복 횟수·②③⑤ 변경수·**score.total**·⑤점수연동 on/off 기록 → 수렴 소진/범위 누락/강조 증발/점수 누수를 사후 진단 가능.

---

## 4. 규칙 간 상충 처리 (① 서식보존 vs ②③ 정규화) — 개정

핵심 긴장: **①"원본 서식 보존"** vs **②"색→검정"·③"본문 10pt 통일"**.

조정 규칙(우선순위 명시):
1. **"보존" 범위 재정의** — ①이 보존하는 것은 *문서 골격*(구조·제목 위계·강조 Bold/밑줄/**형광펜·음영**)이지 *양식 안내용 색/크기*가 아니다. ②③은 "양식 잔재 정규화" → ①과 상보.
2. **보존색 화이트리스트 + highlight/shd 보존 우선** — ②는 보존색(`_PRESERVE_COLORS`/`_COLOR_PRESERVE`)·000000을 건드리지 않으며, **`w:highlight`·`w:shd`는 색 정규화와 무관하게 항상 보존**(채움 경로의 L61 헬퍼와 달리, 후처리 walker는 색만 변경).
3. **스타일 경계 존중** — ③ target_pt는 `Heading*`/`Title`/`제목`·표 셀·캡션을 제외(스타일 스킵 계승).
4. **★③ 본문 내부 모순 해소(핵심)** — **본문 단락 안에서 '지배값 통일'과 '고정 target_pt'는 상호배타**다. `target_pt`가 켜지면 본문에서 `_dominant()` 지배값 통일을 끄고 target_pt만 적용(둘을 같은 run에 동시 적용하지 않음). 분기는 `is None`/`is not None` 명시(L574 truthiness 답습 금지), size 값을 단위테스트로 고정.
5. **★③ 표셀 비대칭 구분(v4 MINOR)** — rule-3 target_pt는 **표 셀에 dominant·target 모두 미적용(스킵)** 이다. 이는 **현행 dominant 통일이 표 셀(1-level, L522-531, 중첩표 비재귀)을 라이브로 처리하는 기존 동작과 별개**다. 즉 `target_pt`가 None이면 표 셀 dominant 처리는 그대로 유지되고, `target_pt`가 켜져도 표 셀은 둘 다 손대지 않는다(독자 혼동 방지용 명확화 — rule-3가 기존 표셀 dominant를 없애는 것이 아님).
6. **강조와의 순서 고정** — `run_all`에서 ②색·③크기를 강조보다 먼저(크기·색만, b/u·highlight 보존). 참고: 강조 패스(`emphasize_key_sentences`, L368-371)는 `w:u`만 append하며 새 run/색/크기를 만들지 않으므로 순서상 색·크기 정규화 후 강조가 안전.
7. **플래그 우선권** — 서식 절대보존 양식은 `color_to_black=False`+`body_font_pt=None`(`minimal`/`off`)로 ①을 ②③보다 우위. 충돌 최종 결정권은 프리셋.
8. **멱등·count/size/score 골든 회귀로 보증** — ②③ 재실행 0건(멱등), 골든은 count 불변(+highlight 잔존수 불변 + 본문 대표 run size 값 + score.total 불변)으로 상시 검증.

---

## 5. 미해결/사용자 확인 필요 (Open Questions) — 개정

- ③ **두 층위 구분(중요)**: (a) *숫자 차이* — 요청 10pt vs 기존 `normalize_font_sizes` body_pt=11.0는 프리셋 override로 해결. (b) *메커니즘 충돌* — **'지배값 통일 자체'와 'target_pt 고정'의 동시적용 모순**(§4-4)이 본질이며, 11/10 숫자 차이와 별개 문제. 본문에서 상호배타로 확정했으나, **"양식이 11pt를 강제"하는 케이스 vs target_pt=10의 기본 우선순위는 사용자 합의 필요(bizplan 프리셋 출시 전 반드시 결정 — 계획 차단요인은 아니나 출시 차단요인)**.
- ⑤ **채점 동작 변경(v4)**: `empty_required_cells` 가중치를 0→비0으로 켜는 것은 '동작 변경'이라 `bizplan` 프리셋의 점수 산정을 바꾼다. **`bizplan`에서 `score_empty_required=True`를 기본으로 둘지(권고) vs 보수적으로 off 유지할지** 사용자 합의 필요(점수 게이트 85점 통과율에 영향).
- ⑤ 마커 주입 범위: 마커 주입 fixer를 기본 off로 축소했는데, 사용자가 "빈칸 강제 표기"를 원하면 fail→fail 전환을 감수하고 켤지 합의 필요.
- ⑦ "사실 기반" 판정: 근거표기 유무로만 보수 판단(warn). 화이트리스트 범위 합의 필요.
- ⑧ 역할경계: acceptance를 루프에 끌어들이지 않기로 했으나, 향후 "fix 직후 동일 검출기 재호출"을 별도 검증 단계로 둘지(루프 밖) 사용자 합의 필요.

---

## 6. ADR (Architecture Decision Record)

### Decision
사업계획서 작성 규칙(①~⑧)을 **(1) 프리셋 config(`quality_rules.py`, `score_empty_required` 플래그 포함) + (2) 기존 `doc_quality_ops`/`submittable_filler`/`doc_quality_score` 확장** 으로 내장한다. ② 색변환 walker는 검출기가 공개한 `usage_acceptance.dedup_cells`(L220)를 **import해 REUSE**(본문+표 셀+중첩표 셀, 검출기와 정확히 같은 범위)하되 **색만 검정화하고 `w:highlight`·`w:shd`는 보존**(`_set_run_color_black_unless_preserved` 재사용 금지). ③은 **지배값 통일과 target_pt를 상호배타**로 처리하고 분기를 `is None`/`is not None`으로 명시하며, 모든 신규 패스는 **멱등**이다. ⑤의 채점 연동은 **'재사용'이 아니라 가중치 0→비0의 '동작 변경'** 임을 명시하고 **`score_empty_required` 플래그로 게이팅**(기본 off, `bizplan`만 on). **acceptance(검수)는 오케스트레이터 수정 루프에 결합하지 않고 사후 게이트(`AcceptanceReport.submittable`)로 유지**한다. 하위호환은 **`run_all(rules=None)==레거시` count 동등성 + `score_empty_required=False`일 때 score.total 불변 + 골든 count/size/score 기반 baseline JSON**으로 삼중 보증(바이트 동일 아님).

### Drivers
1. 회귀 안전성(골든 불변 + highlight 부수삭제 방지 + 수렴 소진 방지 + ⑤ 점수 누수 방지 + rule-3 size 드리프트 방지). 2. 범용 엔진 제어성(프리셋/플래그, ⑤ 점수 동작 변경 게이팅). 3. 범위 일치(REUSE)·부작용 격리·중복금지(검출기 `dedup_cells` REUSE로 중첩표 재귀 보존, highlight/shd 비변경, 색변환 신규 경량 헬퍼).

### Alternatives considered
- **Alt-1 (기존안 폐기)** "오케스트레이터 루프에서 `run_acceptance`를 호출해 detect→fix 루프를 닫는다." → **거짓 전제**: 현 루프(L151-159)는 acceptance를 호출하지 않으며(grep 0), acceptance는 `submission_orchestrator.py:213`/`autopilot_pipeline.py:296`의 사후 게이트(`submittable`)다. 강결합 시 ⑧ 역할경계 위반 + 수렴 불안정 → **기각**.
- **Alt-2** 색변환·폰트통일·셀 순회를 새 모듈에 재구현(옵션 B). → 기존 헬퍼·`dedup_cells`와 **중복** + 중첩표 재귀 누락 위험, '고쳤는데 검출' 회귀 → 기각(검사 ⑦·config에만 모듈 분리 적용).
- **Alt-3** ③에서 지배값 통일과 target_pt를 **둘 다 적용**. → 같은 본문 run에 두 목표 충돌 → 비결정·비멱등·수렴 소진 → 기각(상호배타 채택).
- **Alt-4** 골든 회귀를 **바이트 동일**로 단언. → python-docx 재직렬화 비결정성으로 day-one 거짓실패 → 기각(count + size 값 + score.total 기반 채택).
- **Alt-5** ⑤ 마커 주입을 core 기본 도입. → empty fail→marker fail 치환일 뿐 `submittable` 상승 없음·기존 manual_review와 중복 → 기각(마커는 옵트인, 채점 연동으로 축소).
- **Alt-6** ② walker가 `_set_run_color_black_unless_preserved`(L61)를 **그대로 재사용**. → 색뿐 아니라 `w:highlight`(L66-68)·`w:shd`(L69-71)를 제거해 전 문서의 정당한 형광펜·음영 강조를 조용히 삭제(검출기는 highlight 미검사라 못 잡음) → 기각(**색만 바꾸는 신규 경량 헬퍼** 채택, highlight/shd 보존 테스트 동반).
- **Alt-7** ②③⑤를 **루프 밖 단발(out-of-loop)** 로 배치해 비멱등 수렴소진을 구조적으로 제거. → 색·크기 규칙이 미래 루프 내 다른 패스가 만든 새 서식에 재적용되지 못해 **순서 일관성/단일 정규화 상태가 깨짐**(참고: 현재 underline 패스는 새 run을 만들지 않으므로 이 우려의 *현존* 사례는 아님 — 미래 패스 대비 근거) → 기본은 루프-내부 + 멱등 강제(테스트+observability), 단발 분리는 비멱등 불가피 시의 탈출구로 follow-up 보류(채택 보류, Follow-up 4).
- **Alt-8 (v4 신규)** ⑤ 채점 연동을 **'기존 `empty_required_cells` 경로 재사용'으로 구현(플래그 없이 항상 점수 반영)**. → 이는 사실상 가중치 0→비0의 **동작 변경**이라 `ruleset=None` 경로의 `score.total`까지 흔들어 골든·하위호환을 깬다(거짓 전제) → 기각(**`score_empty_required` 플래그 게이팅 + 하위호환-점수 테스트 + 골든 score.total 고정** 채택).

### Why chosen
검출기/수정기 **범위 일치(검출기 `dedup_cells` REUSE로 중첩표 재귀 보존) + 부작용 격리(highlight/shd 보존)**, ③ **상호배타 + None-vs-value 명시 분기**, 모든 패스 **멱등**, ⑤ 채점 **'동작 변경' 명시 + 플래그 게이팅**으로 합의에서 지적된 회귀 클래스('고쳤는데 검출'(중첩표 포함), '강조 증발', 수렴 소진, 골든 거짓실패, 하위호환 무성회귀(서식·점수), rule-3 size 드리프트)를 구조적으로 차단한다. 게이트 속성을 `submittable`로 정정해 구현 즉시 `AttributeError`를 방지하고, `run_all(rules=None)==레거시` + `score.total` 직접 테스트로 하위호환 전제를 독립 고정한다. 루프-내부 배치 근거를 거짓('underline이 비검정 run 생성')에서 사실('미래 패스 대비 순서 일관성')로 정정해 구현자가 잘못된 전제를 신뢰하지 않게 한다. 프리셋으로 범용 제어성을 확보하고 기존 헬퍼·순회(색변환 제외) 재사용으로 변경면을 최소화하며, acceptance를 사후 게이트로 유지해 ⑧ 역할경계와 수렴 안정성을 함께 보존한다.

### Consequences
- (+) 회귀 7종 차단('고쳤는데 검출'(중첩표 포함)·'강조 증발'·수렴 소진·골든 거짓실패·하위호환 무성회귀(서식)·**⑤ 점수 누수**·**rule-3 size 드리프트**), 양식별 제어 가능, 변경면 최소, 하위호환(논리 동등 + 점수 불변) 보장, 구현 즉시 게이트 속성·루프 근거 정확.
- (-) `unify_paragraph_formatting`/`run_all` 시그니처 비대화 + ③ dominant↔target 두 모드 응집으로 함수 복잡도·테스트 표면 증가(수용된 유지보수 비용).
- (-) ② 색변환만 기존 L61 헬퍼를 재사용하지 못하고 신규 경량 헬퍼를 추가(중복 회피 원칙의 의도적 예외 — 부작용 격리가 우선). 단 셀 순회는 `dedup_cells`(L220) REUSE로 중복 회피.
- (-) ⑤ 채점 연동이 '동작 변경'이라 `bizplan` 점수 산정이 바뀜(85점 게이트 통과율 영향) → 출시 전 사용자 합의 필요(Open Questions·Follow-up 3).
- (-) detect→fix가 한 루프에서 자동 수렴하지 않으므로, fix 후 검출 재확인은 사후 게이트(별도 단계)에 의존.
- (-) ⑤ 마커 강제 표기는 옵트인이라 "빈칸 강제"를 원하면 추가 결정 필요.

### Follow-ups
1. `tests/golden/bizplan_baseline.json` 결정론적 캡처 절차 확정·1회 캡처(전제: `run_all(rules=None)==레거시` + `score_empty_required=False`일 때 score.total 불변 단위테스트 선통과). baseline에 **count + 본문 대표 run size 값 + score.total** 포함.
2. ⑤ "빈칸 강제 표기"(마커 주입) 기본값(off 유지 vs on) 사용자 합의.
3. ⑤ **채점 연동(`score_empty_required`) `bizplan` 기본 on vs off + ③ 양식 강제 11pt vs target_pt=10 기본 우선순위 사용자 합의 — bizplan 프리셋 출시 전 필수**(둘 다 점수/서식 결과를 바꿈).
4. (선택) 비멱등 패스가 불가피해질 경우 해당 패스만 **루프 밖 단발**로 분리하는 구조적 탈출구 적용(⑧ 경계·순서 일관성 유지 전제).
5. (v4 신규) **글머리표 정리·표 공백 정리 등 다른 루프-내부 패스가 새 run을 만드는지 검증** — 루프-내부 배치의 '미래 패스 대비' 근거의 실제 후보를 확인해, 필요 시 색·크기 재정규화 순서를 보강.
6. ⑦ 화이트리스트 범위 사용자 합의 후 점진 확장(warn 유지).
7. (선택) fix 직후 검출기 재호출을 **루프 밖** 별도 검증 단계로 둘지 검토(⑧ 경계 유지 전제).
