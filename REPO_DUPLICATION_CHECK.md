# 레포 중복 확인 리포트 — `auto_write` ↔ `autowrite`

> 작성: 2026-06-27 · 대상: `pds2225/auto_write`(신) ↔ `pds2225/autowrite`(구)
> **통합 완료(2026-08-02):** 고유 자산은 `tools/injector/` 로 전부 이전. `autowrite` 는
> GitHub에서 **archived** 상태. 원격 레포 삭제는 owner가 GitHub Settings → Delete 로 수행
> (이 환경의 토큰에는 `admin`/`delete` 권한 없음).

---

## 1. 두 레포의 정체

| | `pds2225/autowrite` (구) | `pds2225/auto_write` (신) |
|---|---|---|
| 정체 | **BizPlan Injector** — 사업계획서 DOCX 자동 주입 도구 | 문서 품질 개선·제출완성 하네스 |
| 시작 커밋 | `8a891bb` (2026-03-22) | `d94c41f` (2026-06-06) |
| 기본 브랜치 | `main` | `master` |
| 고유 자산 | `inject.py`, `bizplan_app.py`, `core/`(22), `prompts/`(11), `examples/`(6), `templates/`, `references/` | `.claude/`(에이전트·스킬·커맨드), `scripts/`, 품질 하네스 서비스, `pytest.ini` |
| 통합 후 | **archived** — 삭제 대기 | 단일 정본 (인젝터 = `tools/injector/`) |

**공통 루트 커밋 없음** — fork가 아니라 **파일을 복사해 새 레포로 출발**한 관계다.

## 2. 실제 중복 현황 (재검증 2026-08-02)

- **`autowrite`의 `app/auto_write/` 고유 함수·클래스: 0개.** `auto_write`가 완전한 상위집합.
- 갈라진 10개 파일도 `auto_write`가 상위호환(+날조 버그 수정: `"1,000(추정)"` 제거).
- **판정: 코어 흡수 불필요. 손실 0.**

## 3. 이전 완료 자산 (`tools/injector/`)

| 자산 | 상태 |
|---|---|
| `inject.py`, `bizplan_app.py` | ✅ md5 일치 |
| `core/`, `prompts/`, `examples/`, `references/`, `templates/` | ✅ 내용 동일 |
| `requirements.txt` | ✅ |
| `run.bat`, `run.sh` | ✅ 2026-08-02 추가 (경로 `tools/injector` 기준) |
| `docs/새양식_적용_가이드.md` | ✅ 2026-08-02 추가 |
| `tests/test_v2.py` | ✅ 2026-08-02 추가 |

버려도 되는 것: 중복 `app/auto_write/` 사본, `*_backup.py`/`*.bak.*`, `output/` 산출물,
원격 Claude용 `.claude/hooks/session-start.sh`(본 레포 설정과 무관).

## 4. `autowrite` 삭제 절차 (owner)

1. https://github.com/pds2225/autowrite/settings 열기
2. (이미 archived) Danger Zone → **Delete this repository**
3. 확인 문자열 `pds2225/autowrite` 입력 후 삭제

이 에이전트 토큰은 `permissions.admin=false` 라 API로 삭제할 수 없다.

## 5. 비파괴 원칙 (CLAUDE.md 준수)

원본 덮어쓰기·삭제 없이 git 이동 + PR 리뷰. 산출물(`output/`·`results`)은 이전하지 않는다.
