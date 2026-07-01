# 레포 중복 확인 리포트 — `auto_write` ↔ `autowrite`

> 작성: 2026-06-27 · 대상: `pds2225/auto_write`(신) ↔ `pds2225/autowrite`(구)
> 결론: **두 레포는 같은 프로젝트의 두 세대다.** Git 이력은 분리돼 있으나 핵심 `app/auto_write/`
> 웹 패키지가 복사되어 양쪽에 중복된다. `auto_write`가 코어의 완전한 상위호환이므로, `autowrite`의
> 고유 자산(BizPlan Injector CLI)만 흡수하고 `auto_write`를 단일 정본으로 통합하는 것을 권장한다.

---

## 1. 두 레포의 정체

| | `pds2225/autowrite` (구) | `pds2225/auto_write` (신) |
|---|---|---|
| 정체 | **BizPlan Injector** — 사업계획서 DOCX 자동 주입 도구 | 문서 품질 개선·제출완성 하네스 |
| 시작 커밋 | `8a891bb` (2026-03-22) | `d94c41f` (2026-06-06) |
| 커밋 수 | 45 | 138 |
| 추적 파일 | 121 | 197 |
| 기본 브랜치 | `main` | `master` |
| 고유 자산 | `inject.py`, `bizplan_app.py`, `core/`(22), `prompts/`(11), `examples/`(6), `templates/`, `references/` | `.claude/`(35: 에이전트·스킬·커맨드), `scripts/`(8), 품질 하네스 서비스 49+, `pytest.ini` |

**공통 루트 커밋 없음** — fork가 아니라 **파일을 복사해 새 레포로 출발**한 관계다.

## 2. 실제 중복 현황

- **내용 완전 동일(md5 일치) 파일: 46개**, 같은 경로 기준 **63개 경로**가 양쪽에 존재.
- 중복의 핵심은 **`app/auto_write/` FastAPI 웹 패키지**:
  - 공유 경로 37개 중 **27개 완전 동일**, **10개 갈라짐(diverged)**.
  - 갈라진 파일: `config.py`, `main.py`, `services/{docx_ops, evaluation_service, image_service, project_service, render_service}.py`, `templates/{index, project_detail, template_detail}.html`
- 그 외 동일 루트 파일: `auto_write.code-workspace`, `check_env.bat`, `launch.bat`.
- 갈라진 메타: `README.md`, `.gitignore`, `.claude/settings.json`.
- **노이즈**: 양쪽 모두 백업 파일(`*_backup.py`, `*.bak.YYYYMMDD_*`)을 리포에 커밋 — "동일 46파일"의 상당수가 이것이다(이미 git 이력이 보관하므로 불필요).

## 3. 갈라진 코어 안전 점검 (흡수해도 손실 없는가?)

갈라진 10개 파일을 정밀 대조한 결과:

- **`autowrite`에만 있는 함수·클래스: 0개.** `auto_write`가 함수 단위로 완전한 상위집합.
- "autowrite에만 있는 라인"으로 잡힌 것은 전부 **리팩터링으로 형태만 바뀐 동일 로직**이었다.
  검증된 심볼(모두 `auto_write`에 존재): `_resolve_table_cell`, `score_document`, `build_eval_result`,
  `to_report_dict`, `_filter_missing_for_autofill`, `generate_image_file`, `EvalLoopReport`.
- **결정적 증거**: `autowrite`의 `project_service.py`는 매출 빈칸에 `"1,000(추정)"`을 채우는데,
  `auto_write`는 이 줄을 의도적으로 제거하고 *"수치 날조 금지 — 임의값 대신…"* 주석을 달았다.
  즉 `auto_write`는 `autowrite`의 **날조 버그까지 고친 상태**다.

| diverged 파일 | auto_write 라인 | autowrite 라인 | 판정 |
|---|---:|---:|---|
| config.py | 145 | 137 | auto_write 상위 |
| main.py | 430 | 399 | auto_write 상위 |
| services/docx_ops.py | 342 | 295 | auto_write 상위 |
| services/evaluation_service.py | 378 | 376 | auto_write 상위 |
| services/image_service.py | 234 | 149 | auto_write 상위 |
| services/project_service.py | 1870 | 1690 | auto_write 상위(+날조버그 수정) |
| services/render_service.py | 254 | 179 | auto_write 상위 |

> **판정: `autowrite`의 `app/auto_write/` 코어는 흡수가 필요 없다.** 버려도 손실 0.
> `autowrite`의 유일한 고유 가치는 **BizPlan Injector CLI**(`inject.py`, `core/`, `prompts/`, `examples/`, `templates/`)뿐이다.

## 4. 통합 방향 — 권장안 ⭐

**`auto_write`를 단일 정본(monorepo)으로, `autowrite`는 인젝터만 흡수 후 아카이브.**

**옮길 것 (autowrite → auto_write/tools/injector/):**
- `inject.py`, `bizplan_app.py`
- `core/`, `prompts/`, `examples/`, `templates/`, `references/`

**버릴 것:**
- `autowrite`의 중복된 `app/auto_write/` 옛 사본 (auto_write가 상위호환)
- 양쪽 공통 백업 파일(`*_backup.py`, `*.bak.*`) — git 이력이 보관
- 동일한 `check_env.bat`·`launch.bat`·`auto_write.code-workspace`·`output/`

**마무리:** `autowrite` README에 "→ `auto_write`로 통합됨" 표기 후 archive.

### 대안 (권장 안 함)
- **B. 코어를 공유 패키지로 분리** — 두 레포가 동시에 같은 패키지를 쓸 때나 의미 있음. 지금은 `autowrite` 사본이 정체돼 오버엔지니어링.
- **C. 현상 유지 + 동기화 스크립트** — 갈라짐이 누적돼 부채만 키움.

### 비파괴 원칙 (CLAUDE.md 준수)
원본 덮어쓰기·삭제 없이 `git` 이동 + PR 리뷰로. 산출물(`output/`·`results`)은 이전하지 않는다.
