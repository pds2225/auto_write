# Target Form Analyzer 인수인계

작성: 2026-09-26. 이 문서는 설계를 이어 가기 위한 증거 정리이다. 이 턴에서 AutoWrite 코드, 테스트, `TASK.md`, Google Sheet, Git 이력, HWPX 원본은 수정하지 않았다. 새 분석기 구현도 시작하지 않았다.

증거 출처:

- 작업 트리 `C:\Users\ekth3\dev\aw-native-0924`의 `git status`, `git rev-parse`, `git log`, `git grep origin/main`
- `data/hwpx_analysis_results.json` (156,162,028 bytes, `분석시각` `2026-09-26T20:13:03+09:00`)
- 그 JSON을 만든 읽기 전용 스크립트 `C:\Users\ekth3\AppData\Local\Temp\hwpx_batch_analyze.py` (저장소 밖, AutoWrite를 import하지 않음)
- 좌표 대조 기록 `C:\Users\ekth3\AppData\Local\Temp\hwpx_verify_report.json`
- 같은 10개 HWPX의 section XML을 다시 읽어 확인한 run 텍스트
- 작업본의 `hwpx_fill.py`, `hwpx_analysis_adapter.py`, `hwpx_fill_coverage.py`, `form_analyzer.py`, `models.py`, `native_hwp.py`

JSON의 `성공: 489`는 ZIP/section XML을 읽었다는 뜻이다. write target이 안전하게 쓸 위치라는 뜻은 아니다. 안전성 판정은 아래 10개 파일 대조이며, 현재 결과는 PASS 2 / FAIL 8이다.

---

## 1. CURRENT BASELINE

| 항목 | 확인값 |
|---|---|
| branch | `codex/aw-native-20260924` |
| upstream | `origin/main` |
| HEAD | `f63eb71b457c34c9f4fa9f6d928803043beb9592` |
| HEAD 제목 | `Merge pull request #191 from pds2225/cursor/group3-gate-merge-7092` (2026-09-23) |
| origin/main | `ad2c72d3d0cf6dafe42b550559a68b8bb69caade` |
| origin/main 제목 | `merge: Render operator console access on latest main` (2026-09-25) |
| ahead / behind | `0 / 16` (`git rev-list --left-right --count HEAD...origin/main`) |
| dirty | 있음. staged, unstaged, untracked가 같이 있다 |

`HEAD`에만 있고 `origin/main`에 없는 커밋은 0개다. `origin/main`에만 있는 16개 커밋은 운영 콘솔·접근 게이트·모바일 셸이다. Target Form Analyzer가 아니다.

`origin/main`에만 있고 현재 작업 트리 파일로 없는 것:

- `app/auto_write/access_gate.py` (작업 트리에 파일 없음)
- 같은 16개 커밋의 `render.yaml`, `app/tests/test_access_gate.py`, `app/tests/test_config.py`, 모바일 콘솔 관련 변경

작업본에만 있고 `origin/main` blob에는 없는 구현:

- `app/core/docx/services/native_hwp.py` (untracked). `git cat-file -e origin/main:app/core/docx/services/native_hwp.py` 실패
- `app/core/docx/tests/test_f01_write_map.py` (untracked)
- `docs/AI_WRITE_RISK_PLAN_20260924.md` (untracked)
- `.tools/rhwp-0.8.6/` (untracked, `rhwp.exe` 포함)
- `app/core/docx/services/hwpx_analysis_adapter.py`의 셀/라벨 보조 함수. `origin/main` grep에는 `class HwpxAnalysis`, `def read_hwpx_analysis`만 있고 `_table_cells`, `_label_evidence`는 없다
- `app/core/docx/services/hwpx_fill.py`의 `region_cell_is_writable`, `apply_f01_field_writes`, `expected_sha256`, `REVIEW_REQUIRED`. `origin/main`의 같은 파일 grep에는 이 심볼이 없다
- `app/auto_write/models.py`의 `TemplateProfile.source_hwpx`, `native_analysis`, `native_source`. `HEAD` diff에만 추가되어 있다

`origin/main`과 작업본에 둘 다 있는 writer 함수: `_set_cell_text`, `_splice_run_text`, `_apply_line_edits`, `fill_hwpx`, `clamp_letter_spacing`.

`data/hwpx_analysis_results.json`은 `.gitignore`의 `data/`에 걸려 git status에 없다.

dirty 목록 (`git status --short`, 이 문서 작성 직전):

- staged: `app/auto_write/main.py`, `models.py`, `operator_main.py`, `services/hwpx_submit.py`, `services/project_service.py`, `templates/operator_result.html`, `project_detail.html`, `template_detail.html`, `app/core/docx/tests/test_document_ingest.py`, `app/tests/test_hwpx_submit.py`, `app/tests/test_project_service_safety.py`
- unstaged도 있음: `models.py`, `hwpx_submit.py`, `project_service.py`, `hwpx_analysis_adapter.py`, `hwpx_fill.py` (`MM`은 staged와 unstaged가 둘 다 있다는 뜻)
- untracked: 위 native/F01/rhwp/위험계획 문서

`git diff --stat HEAD`는 위 13개 추적 파일에서 1,254 insertions, 33 deletions이다. 이 수치는 `HEAD`(f63eb71) 대비이며, `origin/main`(ad2c72d) 대비 전체가 아니다. 브랜치가 16커밋 뒤져 있으므로 `main.py`와 `operator_main.py`의 작업본 수정은 ad2c72d 위에 올라간 상태가 아니다.

---

## 2. TARGET FORM ANALYZER 목표

이 절은 이번 인수인계가 Astra에게 넘기는 목표이다. 아래 문장이 이미 코드로 구현되었다는 뜻은 아니다.

- 다양한 HWPX 양식에서 실제 사용자가 작성해야 하는 영역을 찾는다.
- field label과 write target을 정확히 연결한다.
- 잘못된 위치에 쓰는 것보다 `REVIEW_REQUIRED` / `NO_TARGET`을 우선한다.
- 기존 writer/fill 경로를 대체하지 않는다.
- REUSE → EXTEND → NEW 원칙을 유지한다.

현재 489개 JSON을 만든 배치 스크립트는 이 목표의 구현이 아니다. AutoWrite를 호출하지 않았고, 저장소에 들어 있지 않다.

---

## 3. 현재 전체 분석 결과

입력: `C:\Users\ekth3\dev\aw-native-0924\data\hwpx_analysis_results.json`

`요약`:

| 키 | 값 |
|---|---|
| 전체 | 489 |
| 성공 | 489 |
| 실패 | 0 |
| 작성양식 | 367 |
| 작성양식아님 | 105 |
| 판정불명 | 17 |
| 원본수정 | 0 |

`성공`은 section XML 파싱이 끝났다는 뜻이다. `작성양식: true`도 write target 안전 PASS가 아니다. 10개 안전성 대조는 4절이다.

최상위 키: `분석시각`, `대상폴더`, `분석방법`, `요약`, `파일`.

`분석방법` 원문: "HWPX ZIP의 section XML만 읽었다. 원본 저장·AutoWrite 코드 호출은 하지 않았다."

파일 객체 키: `sha256`, `문서미리보기`, `분석실패사유`, `상대경로`, `성공`, `안내문`, `원본수정`, `작성양식여부`, `작성양식판정`, `절대경로`, `크기`, `통계`, `파일명`, `판정근거`, `항목`.

항목 키: `write_target_신뢰도`, `write_target_후보`, `기존텍스트`, `기존텍스트잘림`, `문단run위치`, `사용자입력영역`, `신뢰도근거`, `안내문`, `안내문잘림`, `작성항목명`, `종류`, `표위치`.

`표위치` 키: `라벨셀`, `섹션`, `섹션인덱스`, `셀인덱스`, `열`, `열병합`, `주소추정`, `표경로`, `표인덱스`, `행`, `행병합`.

`문단run위치` 키: `charPrIDRef`, `run인덱스`, `문단인덱스`, `섹션`, `섹션인덱스`, `셀안문단인덱스`.

항목 `종류`와 전체 개수:

| 종류 | 개수 |
|---|---|
| 표_기존값 | 61196 |
| 표_세로빈칸 | 33208 |
| 표_빈값칸 | 19254 |
| 표_예시값칸 | 2112 |
| 체크선택 | 1099 |
| 표_인라인빈칸 | 839 |
| 표_기존인라인 | 717 |
| 표_기존서술 | 518 |
| 표_칸안공백 | 459 |
| 본문_인라인빈칸 | 455 |
| 본문_기존인라인 | 389 |
| 표_서술칸 | 356 |
| 입력컨트롤 | 8 |

write target 후보 신뢰도 합계: high 18592, medium 34306, low 3785. 체크선택은 `write_target_후보`가 아니라 이 합계에 들어 있지 않다.

### 후보를 만드는 방식

스크립트 `hwpx_batch_analyze.py`가 section XML만 읽는다. 표 번호는 파일 전체에서 증가한다. 부모 표를 센 다음, 셀 안 중첩 표를 그 셀 순서로 센다. 행·열은 `cellAddr`의 `rowAddr`/`colAddr`이다. 문단 번호는 그 section의 `hp:p` 문서 순이다. write target의 run 번호는 그 문단의 첫 직계 `hp:run`이다.

후보 종류:

- 왼쪽 짧은 라벨에 붙은 빈 셀 → `표_빈값칸`. 라벨이 일반 헤더가 아니고 주소가 추정값이 아니며 격자가 유효하면 high, 아니면 medium 또는 low
- 헤더 아래 빈 셀 → `표_세로빈칸`
- 예시·자리표시만 있는 값 칸 → `표_예시값칸` medium
- `년`/`월`/`일` 사이 공백이나 밑줄이 있는 짧은 칸 → `표_칸안공백` medium
- `라벨:` 또는 `년 월 일` 문단 → 인라인. 밑줄·두 칸 이상 공백·날짜 공백이면 medium, 콜론 뒤가 비어 있기만 하면 low
- 작성 안내가 있고 본문이 없으면 `표_서술칸`. 안내 다음 빈 문단이 있으면 medium, 없으면 low이고 항목명이 비면 `(서술 칸)`
- `□`/`■`이 선택지 2개 이상이거나 짧은 선택어 하나면 `체크선택`. write target은 아님
- 폼 컨트롤만 있는 빈 칸 → `입력컨트롤`. write target은 아님

`작성양식여부`는 구조만이 아니다. `judge()`는 파일명에 `신청서`, `양식`, `서식`, `계획서`, `공고`, `안내` 등이 있는지도 본다. high ≥ 4이면 파일명과 상관없이 작성양식이다. high ≥ 1이고 파일명이 양식 쪽이며 공고 쪽이 아니면 작성양식이다. medium ≥ 2이고 같은 파일명 조건이어도 작성양식이다. 선택칸 ≥ 5이고 같은 조건이어도 작성양식이다.

### 확인된 한계

- 분석 성공과 write target 안전성은 다르다. 489 성공 중 안전성 대조는 10개이고, 그 결과는 PASS 2 / FAIL 8이다.
- 파일명 힌트가 판정에 들어 있다.
- run 전체를 가리킨다. 한 run 안의 라벨과 빈칸을 나누지 않는다.
- 병합 셀 하단 인라인의 `라벨셀`은 그 셀의 인접 제목이다. 인라인 문장의 라벨이 아니다.
- 첫 run이 비어 있어도 run 0을 가리킨다.
- 빈 문단이 없는 서술 칸은 `※` 안내 run을 write target으로 두고 항목명을 `(서술 칸)`으로 둔다.
- 체크표의 짧은 열 제목 `해 당`을 문항명으로 둔 경우가 있다.
- 안내문은 파일당 40개까지만 저장한다. 별첨1 사업계획서는 `안내문생략수` 36이다.
- 항목 저장 상한은 1,500이다. 이번 10개 파일은 그 상한에 걸리지 않았다.
- `hp:t` 인덱스, `anchor_before`, `anchor_after`, raw/normalized 분리 필드는 JSON에 없다.
- `read_hwpx_analysis`는 이 JSON을 만들지 않는다. `origin/main`과 작업본 모두 그 함수의 반환은 문단 문자열, 그림 수, 섹션 수이다. 작업본에 추가된 `_table_cells`/`_label_evidence`는 `read_hwpx_analysis`가 호출하지 않는다.

---

## 4. 실제 10개 HWPX 검증 결과

10개 파일은 모두 `data\`에 있다. 모두 JSON에서 `작성양식여부: true`, `성공: true`이다.

좌표 스크립트 `hwpx_verify_report.json`의 `결과` 필드는 라벨 문자열 일치와 high/medium 빈 run 여부 위주이다. 그 스크립트가 PASS로 둔 파일 중에도, run 텍스트를 다시 읽으면 안전 기입에 실패하는 항목이 있다. 이 절의 PASS/FAIL은 그 안전성 대조이며 PASS 2 / FAIL 8이다.

안전했던 공통 유형: `표_빈값칸` high이고, 지정 run 텍스트가 빈 문자열인 경우. 서식09와 참여신청서에서 그렇게 확인했다. 공고·신용취약·별첨1·연구개발 본문1의 high 빈 칸 표본도 좌표 스크립트에서 오류가 없었다. 그 표본이 파일 전체 high를 모두 덮지는 않는다.

### (서식09) 연구개발기관 대표의 참여의사 확인서_접수번호(기관명).hwpx — PASS

- 구조: 섹션 1, 표 2, 문단 49. 항목 12. write target 8 (high 6, medium 2).
- 좌표 스크립트: 8/12 검사, 오류 0, 누락 샘플 0.
- XML: `연구개발과제번호`, `연구개발과제명`의 지정 run은 `''`. 라벨셀 좌표가 있다.
- 잘못 잡힌 field label: 이 검사 범위에서는 없음.
- 잘못 잡힌 write target: 이 검사 범위에서는 없음.
- 안전했던 target: high `표_빈값칸`의 빈 run.

### (참여신청서, 개인정보동의서) 서울창업허브 성수, 창동×홈앤쇼핑 오픈이노베이션.hwpx — PASS

- 구조: 섹션 1, 표 5, 문단 82. 항목 17. write target 11 (high 7, medium 4). 선택칸 4.
- 좌표 스크립트: 15/17 검사, 오류 0, 누락 샘플 0.
- XML: `업체명`, `업종/업태`의 지정 run은 `''`.
- 잘못 잡힌 field label: 이 검사 범위에서는 없음.
- 잘못 잡힌 write target: 이 검사 범위에서는 없음.
- 안전했던 target: high `표_빈값칸`의 빈 run.

### 2025전담PM(자기기술서).hwpx — FAIL

- 구조: 섹션 1, 표 1, 문단 14. 항목 3. write target 3, 모두 medium. high 없음.
- 좌표 스크립트 `결과`는 PASS(3/3, 오류 0)이다. 안전성 재확인에서 FAIL이다.
- XML:
  - `표_서술칸` `자기기술서`: 지정 run `''`. 안내문은 `□ 컨설팅 전문분야 경력사항...`. 이 칸은 안내문과 빈 run이 나뉘어 있다.
  - `본문_인라인빈칸` `일자`: 지정 run `2025년 월 일`.
  - `본문_인라인빈칸` `성 명`: 지정 run `성 명 : (서명)`.
- 잘못 잡힌 field label: 본문 인라인은 `라벨셀`이 없다. 항목명 자체는 그 run 문장과 맞다.
- 잘못 잡힌 write target: `일자`와 `성 명`은 라벨·날짜 뼈대·서명이 같은 run이다. run 전체를 쓰면 라벨이 지워진다.
- 안전했던 target: `자기기술서` 서술 칸의 빈 run.

### (첨부3) 성장촉진자금(자동화설비) 신청 자가진단표.hwpx — FAIL

- 구조: 섹션 1, 표 3, 문단 87. 항목 22. 선택칸 19. write target 후보는 0이다. 실패는 텍스트 write target이 아니라 체크 항목명이다.
- 좌표 스크립트 `결과`는 PASS(6/22)이다. 체크 19개의 항목명을 모두 세면 FAIL이다.
- XML: 앞쪽 `체크선택`의 지정 run은 `□예`. `라벨셀`은 행 0, 열 1, 셀인덱스 1이다.
- 잘못 잡힌 field label: 체크 19개 중 15개가 `해 당`이다. 문항으로 잡힌 것은 4개뿐이다. `비영리 법인 또는 비영리 개인사업자`, `소상공인 정책자금 지원제외업종에 해당하는 경우`, `휴폐업 중인 경우`, `임직원의 자금횡령 등 사회적 물의를 일으킨 경우`.
- 잘못 잡힌 write target: write target 후보는 없다. `□예` 문단만 가리키므로 `□아니오`가 같은 셀의 다른 문단에 있어도 이 항목은 그 문단을 항목명으로 쓰지 않는다.
- 안전했던 target: 자동 텍스트 기입 후보는 없다.

### (별첨1) 2024년도 창업중심대학 예비창업자 사업계획서 양식.hwpx — FAIL

- 구조: 섹션 1, 표 49, 문단 588. 항목 152. write target 58 (high 13, medium 40, low 5). `표_서술칸`은 1개이고 low이다. 안내문 저장 40, 생략 36.
- 좌표 스크립트: 32/152 검사, 오류 0. high/medium 빈 칸 표본은 그 스크립트에서 통과했다.
- XML: 유일한 `표_서술칸`의 항목명은 `(서술 칸)`. 지정 run은 `※ 사업계획서는 목차(1페이지)를 제외하고 15페이지 이내로 작성`. 같은 문단에 빈 run이 하나 더 있으나 지정 run은 안내 run이다. `라벨셀`은 없다.
- 잘못 잡힌 field label: `(서술 칸)`.
- 잘못 잡힌 write target: `※` 안내 run.
- 안전했던 target: 좌표 스크립트가 오류 없이 본 high `표_빈값칸` 표본. 서술 칸은 안전하지 않다.

### (붙임2) 신용취약소상공인자금 신청 서식.hwpx — FAIL

- 구조: 섹션 5, 표 84, 문단 1816. 항목 417. write target 183 (high 76, medium 90, low 17). 선택칸 35.
- 좌표 스크립트: 48/417 검사, 실질오류 0, 누락 샘플 0. low 4건은 라벨 불일치로 남아 있다. 표 번호는 파일 전체 기준이다. 섹션마다 0부터 세면 표 63·69·75가 섹션 표 수를 넘는 것으로 보이지만, 그것은 대조 스크립트의 첫 구현 오류였고 전체 표 순서로 다시 보면 인덱스 범위 오류는 없다.
- 좌표 스크립트에 남은 라벨 불일치:
  - `기업체명` / `대 표 자`의 `라벨셀` 텍스트가 `고 객`
  - `성 명` / `연락처`의 `라벨셀` 텍스트가 `건물 소유자 또는 전월세계약자*`
- 잘못 잡힌 field label: 위 4개 인라인의 `라벨셀`. 항목명 문자열은 그 문단의 `기업체명 :`, `대 표 자 :`와 맞다.
- 잘못 잡힌 write target: 그 문단 run이 라벨 문장 자체이다. low이지만 후보로는 올라가 있다.
- 안전했던 target: 같은 파일에서 좌표 스크립트가 본 high 빈 칸. 48건 표본이지 183건 전체가 아니다.

### 3. SBA 액셀러레이팅 정보 수집 및 이용 동의서 양식(2023년).hwpx — FAIL

- 구조: 섹션 1, 표 2, 문단 44. 항목 13. write target 4, 모두 medium 본문 인라인. 선택칸 3. high 없음.
- 좌표 스크립트 `결과`는 PASS(7/13)이다. run을 나누어 보면 FAIL이다.
- XML, 지정 run에 `*` :
  - `일자`: `2023년 월 일` 한 run
  - `기 업 명`: `기 업 명 :` 한 run
  - `대표자 성명`: run0 `대표자 성명 :`, run1 `(인)`, run2 `''`. 지정은 run0
  - `신청자 성명`: run0 `신청자 성명 :`, run1 `(인)`. 지정은 run0
- 잘못 잡힌 field label: 항목명은 문장과 맞다. 별도 `라벨셀`은 없다.
- 잘못 잡힌 write target: 라벨 run을 가리킨다. `대표자 성명`의 빈 run은 run2인데 지정되지 않았다. `일자` run에는 `년`/`월`/`일` 뼈대가 들어 있다.
- 안전했던 target: 빈 셀 high 후보는 이 파일에 없다.

### (공고)2024년 2030청년창업프로젝트 초기유형 모집 공고문.hwpx — FAIL

- 구조: 섹션 1, 표 51, 문단 822. 항목 235. write target 92 (high 15, medium 53, low 24). 선택칸 3. 파일명에 공고가 있고, high 15라서 `judge()`가 작성양식으로 두었다.
- 좌표 스크립트: 40/235 검사, 오류 2. 둘 다 medium `표_인라인빈칸`.
- XML:
  - `일자` 지정 run `년 월 일`. 같은 문단에 빈 run이 하나 더 있다. `라벨셀`은 행 11, 열 0.
  - `신청인(대표)` 지정 run `신청인(대표) : (인)`.
- 좌표 스크립트의 라벨 불일치 원문: JSON `일자` / `신청인(대표)`에 대해 라벨 텍스트 `주요 사업 내용`.
- 잘못 잡힌 field label: 병합 셀의 인접 제목 `주요 사업 내용`.
- 잘못 잡힌 write target: 날짜 뼈대 run, 서명 라벨이 들어 있는 run.
- 안전했던 target: 같은 검사에서 오류가 없었던 high `표_빈값칸` 표본 (`대표자명`, `기업명`, `주소` 등이 좌표 스크립트 출력에 있었다). 15개 high 전수를 이 문서에서 다시 열지는 않았다.

### (필수) 2. 연구개발계획서 본문1.hwpx — FAIL

- 구조: 섹션 1, 표 29, 문단 281. 항목 111. write target 89 (high 15, medium 73, low 1). `표_서술칸`은 1개이고 그 1개가 low이다.
- 좌표 스크립트: 30/111 검사, 오류 0.
- XML: `표_서술칸` 항목명 `(서술 칸)`. 지정 run `※ 자체 연구개발 실적 및 타 부처 지원 R&D 사업 포함 가능`.
- 잘못 잡힌 field label: `(서술 칸)`.
- 잘못 잡힌 write target: `※` 안내 run.
- 안전했던 target: 좌표 스크립트가 통과시킨 high 빈 칸 표본. 서술 칸은 안전하지 않다.

### 2026년도 SaaS 개발환경 지원 수요기업 신청서.hwpx — FAIL

- 구조: 섹션 1, 표 7, 문단 306. 항목 159. write target 123 (high 15, medium 106, low 2).
- 좌표 스크립트: 31/159 검사, 오류 2. medium `일자`, `대표이사`. 라벨 텍스트는 `신청 기업 정 보`.
- XML:
  - `일자` 지정 run `2026년 월 일`. `라벨셀`은 행 0 열 0, 그리고 또 하나의 `일자`는 행 1 열 0.
  - `대표이사` runs: `''`, `''`, `대표이사 : (인)`. 지정은 첫 빈 run이다. 글자가 있는 run은 세 번째다.
- 잘못 잡힌 field label: `신청 기업 정 보`.
- 잘못 잡힌 write target: 날짜 뼈대 run, 그리고 `대표이사`의 앞쪽 빈 run.
- 안전했던 target: 좌표 스크립트에서 오류가 없었던 high 빈 칸 표본. 123개 전수는 아니다.

---

## 5. 확인된 공통 실패패턴

10개 XML 대조에서 아래 5개가 확인되었다.

### A

라벨과 빈칸이 동일 run에 있으면 run 전체를 write target으로 쓰면 안 된다.

확인: 자기기술서 `성 명 : (서명)`, SBA `기 업 명 :`, SBA `대표자 성명 :`, 공고 `신청인(대표) : (인)`. 날짜 run `2025년 월 일`, `2023년 월 일`, `2026년 월 일`, `년 월 일`도 뼈대와 빈칸이 한 run이다.

### B

병합 셀 하단 날짜/서명/대표자 항목을 인접 섹션 제목과 연결하면 안 된다.

확인: 공고의 `일자`/`신청인(대표)` 라벨 텍스트가 `주요 사업 내용`. SaaS의 `일자`/`대표이사` 라벨 텍스트가 `신청 기업 정 보`. 신용취약 인라인의 `라벨셀`이 `고 객`, `건물 소유자 또는 전월세계약자*`.

### C

문단 첫 run이 비어 있다는 이유만으로 write target으로 판단하면 안 된다.

확인: SaaS `대표이사`는 run0·run1이 `''`이고, `대표이사 : (인)`은 run2이다. JSON `run인덱스`는 0이다.

### D

`※` / 작성요령 / 작성방법 등의 안내문을 write target으로 판단하면 안 된다. 실제 입력 영역이 없으면 `(서술 칸)` 같은 가상 항목도 생성하면 안 된다.

확인: 별첨1 지정 run이 `※ 사업계획서는 목차...작성`이고 항목명이 `(서술 칸)`. 연구개발 본문1 지정 run이 `※ 자체 연구개발 실적...`이고 항목명이 `(서술 칸)`. 스크립트는 빈 문단이 없으면 confidence를 low로 두고 이름도 `(서술 칸)`으로 둔다. low여도 `write_target_후보`는 true이다.

### E

체크표에서 `해당`, `여`, `부`, `예`, `아니오`, `확인` 같은 열 헤더를 실제 질문 label로 판단하면 안 된다.

확인: 자가진단표 체크 19개 중 15개의 항목명이 `해 당`이다. 이 파일에서 `여`/`부`/`확인`이 항목명으로 잡힌 건수는 세지 않았다. `예`/`아니오`는 항목명이 아니라 `□예` run으로 남아 있다.

---

## 6. 기존 AutoWrite 재사용 자산

### hwpx_analysis_adapter

경로: `app/core/docx/services/hwpx_analysis_adapter.py`

- 현재 역할: `read_hwpx_analysis`가 HWPX를 DOCX로 바꾸지 않고 문단 문자열, 그림 수, 섹션 수를 읽는다. 원본을 쓰지 않는다.
- 재사용 가능: ZIP을 읽기만 하는 진입, section XML 정규식, 문단 텍스트를 중첩 `hp:p`와 분리하는 `_paragraph_text`.
- 확장이 필요한 부분: 작업본의 `_table_cells`, `_label_evidence`, `_input_label`은 `read_hwpx_analysis`에 연결되어 있지 않다. `origin/main`에는 이 보조 함수가 없다.
- 사용하면 안 되는 부분: `read_hwpx_analysis` 결과만으로 write target을 만들었다고 보면 안 된다. 이번 JSON의 종류·좌표는 이 함수의 반환이 아니다.

### hwpx_fill

경로: `app/core/docx/services/hwpx_fill.py`

- 현재 역할: 출력 HWPX에 값을 쓴다. `fill_hwpx`는 라벨 매칭으로 값 칸을 찾고 `_set_cell_text`로 쓴다. 인라인은 `_splice_run_text`로 한 `hp:t` 구간만 바꾼다. `line_edits`는 앵커 문단을 수정한다.
- 재사용 가능: 원본과 출력 경로가 같으면 거부하는 것, 폼 컨트롤 칸에 글자를 넣지 않는 `_has_form_control`, cross-run이면 False를 반환하는 `_splice_run_text`, 이미 값이 있으면 라벨 매칭 기입을 건너뛰는 `_cell_is_fillable`.
- 확장이 필요한 부분: 작업본에만 있는 `region_cell_is_writable`와 `apply_f01_field_writes`. 전자는 빈 단순 셀만 true이다. 후자는 F-01 스펙 7곳에만 쓰고, 앵커가 어긋나면 `REVIEW_REQUIRED`로 건너뛴다. 범용 분석기가 아니다.
- 사용하면 안 되는 부분: `_set_cell_text`와 `line_edits`의 `set`을 분석기의 기입 허용으로 쓰면 안 된다. 7절.

### hwpx_fill_coverage

경로: `app/core/docx/services/hwpx_fill_coverage.py`

- 현재 역할: 특정 신청서의 채움률이다. `_find_tbl`은 `성명(국문)`, `소속/직위` 같은 문자열로 표를 찾는다. `_count_value_cells`는 `주요 근무처`, `자격증/면허증` 같은 고정 헤더 목록을 건너뛴다. section XML은 `Contents/section0.xml`이 없으면 section 파일명 정렬의 첫 파일을 쓴다.
- 재사용 가능: 채움률 리포트 껍데기(`CoverageReport`). 분석 좌표의 정본으로는 쓰지 않는다.
- 확장이 필요한 부분: 표 식별이 문구 검색이다. 행·열 좌표를 만들지 않는다.
- 사용하면 안 되는 부분: 고정 헤더 목록과 짝수 칸=라벨 가정을 다른 양식의 write target 규칙으로 재사용하면 안 된다.

### auto_write/services/form_analyzer

경로: `app/auto_write/services/form_analyzer.py`

- 현재 역할: DOCX 양식 요약. HWP/PDF는 `ensure_template_docx`로 DOCX를 만든 뒤 `analyze_template`를 호출한다. `classify_field_kind`는 라벨 길이·PSST 단어로 fact/narrative를 나눈다. `writable_items`는 최대 `max_items` 기본 30개다.
- 재사용 가능: 읽기 전용 `FormReport` 요약 형식. `origin/main`에도 이 파일이 있다.
- 확장이 필요한 부분: HWPX 셀·run 좌표가 없다.
- 사용하면 안 되는 부분: HWPX write target을 만들려고 DOCX 변환 결과를 좌표로 쓰면 안 된다. 변환은 위치를 보존하지 않는다.

### bizplan/services/form_analyzer

경로: `app/bizplan/services/form_analyzer.py`

- 현재 역할: `auto_write.services.form_analyzer`의 re-export이다. 구현이 없다. 파일 주석에 `TODO: migrate impl`이 있다. `origin/main`에도 이 파일이 있다.
- 재사용 가능: import 경로뿐.
- 확장이 필요한 부분: 별도 구현이 필요하다면 auto_write 쪽을 확장한 뒤 다시 export하는 순서이다.
- 사용하면 안 되는 부분: 이 파일을 HWPX 분석 구현이 있는 곳으로 보면 안 된다.

### models

경로: `app/auto_write/models.py`

- 현재 역할: `TemplateProfile`은 `source_docx`, 섹션, 표, 질문 목록을 가진다. 작업본 diff는 `source_hwpx`, `native_analysis`, `native_source` 세 필드를 추가한다. `origin/main` grep에는 `source_hwpx`와 `native_analysis`가 없다.
- 재사용 가능: 프로필을 저장하는 Pydantic 모델.
- 확장이 필요한 부분: `native_analysis`는 dict이다. 4절의 좌표 계약을 강제하는 스키마가 아니다.
- 사용하면 안 되는 부분: `questions`나 DOCX `source_docx`를 HWPX write target 좌표로 해석하면 안 된다.

### native_hwp

작업본에만 있다. `prepare_native_source`와 `verify_hwpx_native`는 rhwp로 변환·재열기·PDF 렌더를 한다. 필드 좌표를 만들지 않는다. 분석기 좌표 모듈로 쓰면 안 된다. 렌더 성공을 기입 성공으로 보면 안 된다. 모듈 문서도 그 둘을 분리한다고 적혀 있다.

재사용 경계: 분석 JSON의 후보를 `fill_hwpx(identity=...)`에 바로 넣지 않는다. `fill_hwpx`는 라벨 문자열을 다시 찾는다. 분석 좌표와 writer의 `_tc_at` 순서는 8절에서 다르다고 확인했다.

---

## 7. writer의 현재 위험

아래는 작업본 `hwpx_fill.py`를 읽은 결과이다. `_set_cell_text`, `_splice_run_text`, `_apply_line_edits`, `fill_hwpx`, `clamp_letter_spacing`은 `origin/main`에도 있다. `region_cell_is_writable`, `expected_sha256`, F-01 `REVIEW_REQUIRED`는 작업본에만 있다.

- 셀 전체 교체: `_set_cell_text`는 `tc.iter(hp:t)`의 첫 `hp:t`에 값을 넣고 나머지 `hp:t` 텍스트를 빈 문자열로 만든다. `iter`는 중첩 `hp:tbl` 안의 `hp:t`도 포함한다. 안내 문단과 중첩 표 글자가 같은 셀에 있으면 지워질 수 있다. `region_cell_is_writable`는 중첩 표·여분 자식이 있으면 false이지만, `fill_hwpx`의 라벨 매칭 경로는 그 함수가 아니라 `_cell_is_fillable`과 `_set_cell_text`를 쓴다.
- single `hp:t` span: `_splice_run_text`는 시작과 끝이 같은 `hp:t`일 때만 부분 교체한다.
- cross-run: 구간이 두 `hp:t`에 걸치면 False이고 쓰지 않는다. 주석 원문: "cross-run span: 보수적 skip".
- 빈칸 판정과 작성 권한: `_cell_text_fillable`은 셀 텍스트가 비었거나 obvious placeholder이면 true이다. `region_cell_is_writable`는 그에 더해 이웃 라벨의 서명·동의·체크 등과 셀 자식 구조를 본다. 둘은 같지 않다. 분석 JSON의 `write_target_후보: true`는 둘 다 호출하지 않는다.
- substring anchor / nth: `_apply_line_edits`는 `anchor in flat`으로 문단을 찾는다. `nth` 또는 `all`이 있으면 유일하지 않아도 적용한다. 없으면 1건일 때만 적용한다.
- `line_edits`의 `set`: 그 문단 `_inline_texts`의 첫 `hp:t`에 새 글을 넣고 나머지 `hp:t`를 비운다. 중첩 표가 든 run은 `_inline_texts`가 건너뛰지만, 같은 문단의 다른 텍스트 run은 비워진다.
- 부분 성공: `fill_hwpx`의 `report.ok`는 `template_status != "TEMPLATE_MISMATCH"`이다. 채운 칸이 0이어도 ok를 false로 두지 않고 notes만 추가한다. F-01은 키마다 앵커가 실패하면 그 키만 `REVIEW_REQUIRED`로 skipped에 넣고, 다른 키는 계속 쓸 수 있다. `apply_f01_field_writes`의 `ok`는 skipped가 비어 있을 때 true이다.
- source hash / expected text: `expected_sha256`은 `field_writes`가 있고 인자가 넘어온 경우에만 비교한다. 불일치하면 F-01만 건너뛰고 `TEMPLATE_MISMATCH`이다. identity/line_edits 일반 경로에는 이 검사가 없다. F-01 앵커는 `_cell_payload`와 옆 라벨 문자열이 스펙과 같을 때만 쓴다. 분석 JSON 후보는 이런 expected text가 없다.
- header 등 비대상 XML: `force_black`이 true이고 유색 charPr를 만나면 `_BlackCharPr`가 header에 검정 클론을 추가하고, `black.changed`이면 `Contents/header.xml`을 다시 쓴다. 이어서 `clamp_letter_spacing`이 자간을 바꾸면 header를 다시 쓴다. `apply_f01_field_writes`는 `force_black=False`로 `fill_hwpx`를 호출하지만, `clamp_letter_spacing` 블록은 force_black과 별도로 header가 있으면 실행된다.

`_tc_at`은 `root.iter(hp:tbl)` 문서 순의 N번째 표에서, 직계 `hp:tr`의 N번째, 직계 `hp:tc`의 N번째를 집는다. 분석 JSON의 `행`/`열`은 `rowAddr`/`colAddr`이다. 이 둘을 같은 번호로 쓰면 안 된다.

---

## 8. 좌표 계약에서 확정해야 할 것

지금 JSON과 writer가 이미 서로 다른 번호를 쓴다. 한 필드에 섞지 않는다.

| 이름 | 지금 확인된 의미 | 다른 번호와 혼용 금지 |
|---|---|---|
| section_member | ZIP 멤버 이름. JSON `섹션`은 `Contents/sectionN.xml` | 섹션 순서 인덱스 |
| section 순서 | 파일명 숫자 정렬. JSON `섹션인덱스`는 그 숫자이다. 멤버가 section0만 있어도 0이다 | 배열 enumerate 번호 |
| table_index | 배치 스크립트는 파일 전체 DFS. 부모 표 다음 셀 안 중첩 표. `_tc_at`은 `iter(tbl)` 문서 순이며 부모/중첩을 따로 세지 않는다 | 섹션마다 0부터 다시 세는 번호, 직계 표만 세는 번호 |
| 중첩 table 포함 여부 | 배치 스크립트 표 수에는 포함. coverage의 문구 검색은 포함 여부를 좌표로 말하지 않는다 | 포함 여부를 적지 않은 table_index |
| direct tr/tc index | `_tc_at`의 row/col 인자. F-01은 이 인덱스와 `cellAddr` 문자열을 둘 다 검사한다 | `rowAddr`/`colAddr` |
| cellAddr rowAddr / colAddr | JSON `행`/`열` | direct tr/tc index |
| rowSpan / colSpan | JSON `행병합`/`열병합`. 주소가 없으면 `주소추정: true` | 칸의 개수 |
| paragraph_index | 그 section의 모든 `hp:p` 문서 순. 표 안 문단 포함 | 셀 안 문단만 세는 `셀안문단인덱스` |
| run_index | 그 `hp:p`의 직계 `hp:run` 순. 현재 후보는 첫 run | `hp:t` 순 |
| hp:t index | 현재 JSON에 없다. `_splice_run_text`는 t 단위이다 | run_index |
| raw text | XML `hp:t` 원문. JSON `기존텍스트`는 strip 후 600자에서 자를 수 있다 (`기존텍스트잘림`) | normalized text |
| normalized text | 스크립트의 `norm()`은 공백을 한 칸으로 줄인다. 항목명은 그 결과이다. 별도 필드는 없다 | raw text |
| anchor_before | 현재 JSON에 없다. F-01은 셀 payload와 옆 라벨 전체 일치를 쓴다 | substring `anchor in flat` |
| anchor_after | 현재 JSON에 없다 | 기입 후 기대 문자열을 적지 않은 상태 |

`라벨셀`은 `행`/`열`/`셀인덱스`만 있다. 그 셀의 raw 텍스트 필드는 없다. 4절에서 라벨이 틀린 사례는 좌표가 가리키는 셀의 실제 텍스트와 항목명이 다르다는 뜻이다.

---

## 9. Astra에게 넘길 핵심 질문

Astra가 코드를 쓰기 전에 아래를 확정한다.

A. 현재 분석기의 근본 오류 원인. 489 파싱 성공과 10개 안전 FAIL을 한 원인으로 합치지 않는다.

B. write target 유형 분류체계. 4절의 빈 셀, 인라인 run, 서술 안내, 체크를 한 종류로 합치지 않는다.

C. 유형별 최종 판정 규칙. 유형마다 쓸 수 있음 / 검토 / 대상 없음을 나눈다.

D. confidence / abstention 규칙. 지금 medium이 `성 명 : (서명)` 같은 불안전 run에도 붙는다.

E. `auto_write_allowed` 규칙. high라는 이유만으로 true로 두지 않는다.

F. `REVIEW_REQUIRED` / `NO_TARGET` 조건. 잘못된 기입보다 거절이 우선이다.

G. 최종 JSON schema. 8절의 좌표를 서로 다른 필드로 둔다.

H. 추가 검증이 필요한 구조 유형. 10절 가운데 이번 10개에서 run까지 확인하지 않은 유형을 적는다.

I. 기존 AutoWrite 재사용/확장 경계. 6절과 7절을 넘어 쓰지 않는다.

J. Cursor 구현 단계. 분석기만 먼저 두고 writer 연결은 안전 규칙 다음으로 둔다.

K. 구현 전 반드시 해결해야 할 위험. 5절 다섯 개와 7절 writer 위험을 구현 허가 조건으로 둔다.

L. 합격조건 및 회귀테스트 구조. 10개 FAIL이 같은 오탐을 내지 않는지, 그리고 그 10개에만 하드코딩하지 않았는지 둘 다 본다.

---

## 10. Astra에서 반드시 다뤄야 할 구조 유형

이번 10개에서 XML로 본 것과, JSON에 종류는 있으나 이번 안전 판정의 전수를 보지 않은 것을 구분한다.

이번 대조에서 사례가 있는 유형:

- 완전 빈 셀, 라벨 + 빈 셀: 서식09, 참여신청서의 high `표_빈값칸`. 지정 run이 빈 문자열.
- 동일 run 내 라벨 + 입력공간: 자기기술서 `성 명 : (서명)`, SBA `기 업 명 :`, 공고 `신청인(대표) : (인)`.
- 다중 run inline field: SBA `대표자 성명` 3 run, SaaS `대표이사` 3 run.
- 병합 셀 하단 날짜·서명·대표자: 공고, SaaS. 라벨셀이 섹션 제목.
- 날짜: `2025년 월 일`, `2023년 월 일`, `2026년 월 일`, `년 월 일`.
- 성명: 자기기술서 `성 명`, SBA `대표자 성명`/`신청자 성명`.
- 안내문 포함 서술 영역: 별첨1, 연구개발 본문1의 `※` run.
- 체크박스 / 예·아니오: 자가진단 `□예`와 항목명 `해 당`.
- 공고문 안에 포함된 신청서: 청년창업 공고. high 15로 작성양식 판정.
- 기존 값이 이미 있는 양식: JSON 종류 `표_기존값`이 전체 61,196개. 이번 10개 FAIL의 주원인은 아니다.
- multi-section: 신용취약 섹션 5, 표 84. 표 번호는 파일 전체 DFS이다.

종류는 있으나 이번 10개 안전 판정에서 전수를 다시 열지 않은 유형:

- 동일 셀 안 라벨 + 입력공간이 빈 셀과 다른 경우. `표_칸안공백` 459개가 JSON에 있다.
- 장문 서술 영역 중 `※`가 아닌 본문. `표_기존서술` 518개.
- 반복행 / 반복항목. `표_세로빈칸` 33,208개. 10개 파일의 세로 칸 전수를 안전 판정하지 않았다.
- 표 밖 일반 본문. `본문_인라인빈칸` 455개 중 자기기술서·SBA만 run을 확인했다.
- 중첩표. 배치 스크립트는 표 번호에 넣는다. 10개 FAIL의 인용 사례는 중첩표 기입이 아니다.
- `origin/main` writer의 중첩표 `iter(hp:t)` 위험은 7절 코드 확인이다. 이번 10개 HWPX에서 그 writer를 실행하지 않았다.

---

## 11. Astra 금지사항

- 코드 수정 금지. 이 인수인계 단계의 산출물은 설계 문서이다.
- 특정 10개 파일에 맞춘 하드코딩 금지.
- 파일명 기반 판단 금지. 현재 `judge()`의 파일명 힌트를 최종 규칙으로 가져가지 않는다.
- "AI가 알아서 판단" 같은 추상 규칙 금지. 유형, 좌표, 거절 조건을 문장으로 고정한다.
- 빈 run만 보고 자동작성 승인 금지. SaaS `대표이사`의 run0이 빈 문자열이었다.
- high confidence라는 이유만으로 서명/동의/체크 항목 자동작성 금지. 자가진단 체크는 write target이 아니었고, 서명 run은 medium이었다. high 빈 셀이라도 서명·동의 라벨인지는 별도 규칙이 필요하다.
- 기존 writer 권한보다 넓은 수정 범위 부여 금지. `_set_cell_text`와 `line_edits set`보다 넓은 셀 치환을 분석기 허가로 만들면 안 된다.

---

## 12. Astra 최종 산출물 형식

Astra는 코드를 쓰지 않고, 아래 순서로 최종안만 만든다.

A. 근본 오류 원인

B. write target 유형 분류체계

C. 최종 판정 규칙

D. confidence / abstention

E. JSON 계약

F. 추가 검증 구조

G. Target Form Analyzer 구현계획

H. 기존 AutoWrite 재사용/확장 모듈

I. Cursor 개발 단계

J. 구현 전 위험요소

K. Acceptance Criteria

L. Regression Test Matrix

A는 3절의 파싱 성공과 4절의 PASS 2 / FAIL 8을 한 성공으로 합치지 않는다. E는 8절의 좌표를 한 숫자로 합치지 않는다. H는 6절에서 "사용하면 안 되는 부분"을 재사용 목록에 넣지 않는다. L은 이 10개 파일의 오탐이 재발하지 않는 검사와, 이 10개에만 맞지 않는다는 검사를 둘 다 포함한다.
