# BizPlan Injector (통합 이전 자산)

> 원래 `pds2225/autowrite` 레포의 **BizPlan Injector** — 사업계획서 DOCX 자동 주입 도구.
> 레포 중복 통합(`REPO_DUPLICATION_CHECK.md` 참조)에 따라 `autowrite`의 고유 자산만
> 이곳으로 이전했다. `autowrite`의 `app/auto_write/` 웹 패키지는 `auto_write` 본체가
> 상위호환이므로 이전하지 않았다(중복 제거).

## 구성

| 경로 | 설명 |
|---|---|
| `inject.py` | 양식 분석 / content.json 스켈레톤 생성 / 자동 주입 CLI |
| `bizplan_app.py` | 인젝터 GUI/앱 진입점 |
| `core/` | 분석기·주입기·AI 작성·검증·서식 모듈 + `prompt_templates/` |
| `prompts/` | 섹션별(PSST) 프롬프트 모듈 |
| `examples/` | content/스키마/검증 리포트 샘플 |
| `references/` | 참고용 사업계획서 마크다운 |
| `templates/` | 원본 양식 DOCX |

## 출처
- 원본 레포: `pds2225/autowrite` (BizPlan Injector, 2026-03 시작)
- 이전 시점의 원본 사용법은 해당 레포 `README.md` 참조.

## 주의
이전 직후 상태로, `auto_write` 본체 패키지(`app/auto_write/`)와의 import 경로 정합은
아직 맞추지 않았다. 독립 CLI로 동작하던 자산이므로 통합 사용 시 경로 조정이 필요할 수 있다.
