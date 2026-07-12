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

## 실행

독립 CLI/앱으로 동작한다. `tools/injector/` 의존성은 `requirements.txt` 참조.

```bash
pip install -r tools/injector/requirements.txt
python tools/injector/inject.py --analyze tools/injector/templates/<양식>.docx
```

## import 경로 정합 (점검 완료)

이전 후 점검 결과 **경로 조정 불필요**하다. 인젝터는 자기 위치를 스스로 부트스트랩한다:

- `inject.py` → `sys.path.insert(0, os.path.dirname(__file__))`
- `core/ai_writer.py` → `sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))`

덕분에 CWD와 무관하게 `from core import ...` / `from prompts import ...` 가 새 위치
(`tools/injector/`)에서 그대로 해소된다(스모크 테스트로 확인 — `prompts` import OK,
`core` 는 경로 해소 통과 후 `lxml`(python-docx 의존성) 설치 여부에만 좌우).

`auto_write` 본체 패키지(`app/auto_write/`)와는 결합하지 않은 **독립 도구**다. 두 코드베이스를
한 모듈에서 함께 쓰려는 경우에만 추가 경로 작업이 필요하다(현재 그런 사용처 없음).
