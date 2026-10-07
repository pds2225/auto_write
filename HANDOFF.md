# HANDOFF.md — Cursor → Luna 인수인계

> 작성 시각: 2026-10-01 (이 클라우드 세션에서 저장소 상태를 직접 확인한 뒤 갱신).
> 이 문서는 참고다. 사실 우선순위는 현재 사용자 지시 → `origin/main:TASK.md` → repo-local 규칙(`AGENTS.md`, `CLAUDE.md`) → 확정된 코드 계약 → 이 파일.
> 이전 `HANDOFF.md`(2026-06-06, 품질 하네스 스냅샷, “202 passed”)는 현재 HEAD의 작업 상태가 아니다. 그 수치를 현재 테스트 결과로 쓰지 말 것.

## 현재 목표

- 프로젝트의 실제 최종 사용자 목표: 정부지원사업 양식(HWP/HWPX)을 변환 왕복 없이 직접 채워 제출 가능한 한글로 만든다. DOCX 품질 하네스는 별도 경로다. 제품 목표 정본은 `TASK.md`의 `AW-005` 8-1과 `최우선 사용 케이스`다. `T-20260814-02`의 긴 8-1은 명세 지시이지 제품 목표가 아니다.
- 현재 단계: draft PR #211. rhwp 기본 끄기·Round-2 채움 수정은 이 브랜치에 커밋되어 있다. Round-3 동적 E2E(사용자 보고: Windows, 한글 2022, head `8043382`, 3/9 통과)에서 남은 채움·lineseg·COM 멈춤은 **코드에 반영되지 않았다**.
- 이번 세션 작업 목적: Round-3를 구현하지 않고, Luna가 저장소만 보고 이어서 고칠 수 있게 실제 Git/소스/증거 기준으로 이 문서를 다시 쓴다.
- 사용자 제약 (Round-3 지시, 아직 유효): 같은 draft PR #211에서 고친다. 머지하지 않는다. 테스트를 지우거나 약하게 하거나 skip 하지 않는다. L050은 `category=gap`, mechanized false. rhwp는 기본 꺼짐(`AUTO_WRITE_ENABLE_RHWP`가 `1`/`true`/`yes`/`on`일 때만). PR 문장은 한국어. `RESUME.md`/`CLAUDE.md`/`AGENTS.md`는 이 작업에서 갱신하지 않는다. 신청서 작성 자체를 TASK LIST에 등록하지 않는다(파일에서 사업명을 지우라는 뜻이 아니다).

## Git 상태

확인 명령과 결과 (2026-10-01, 이 세션):

```text
git rev-parse --show-toplevel
→ /workspace

git branch --show-current
→ cursor/rhwp-unsupported-lrule-status-6a12

git status --porcelain
→ (이 파일을 쓰기 직전) 출력 없음 = CLEAN

git rev-parse @{u}
→ origin/cursor/rhwp-unsupported-lrule-status-6a12

git fetch origin main
→ 완료

git rev-list --left-right --count origin/main...HEAD
→ 0 4
  (origin/main 에만 있는 커밋 0, 이 브랜치에만 있는 커밋 4)

git log -1 --oneline origin/main
→ 6ed289f 콘솔 L규칙 가드 테스트를 실행해 통과한 것만 VERIFIED로 표시 (#210)
```

- repo root: `/workspace`. 원격: `https://github.com/pds2225/auto_write`
- branch: `cursor/rhwp-unsupported-lrule-status-6a12`
- 제품 코드 마지막 커밋 (이 문서의 parent 여야 함): `8043382ec66bde6125130d3de2ceb9bc4bc8b6e4`
- 이 파일을 쓰기 직전 working tree: CLEAN. untracked 없음. stash 없음 (`git stash list` 빈 출력). worktree는 `/workspace` 하나.
- 이 문서 커밋 후 일치 조건: `git rev-parse HEAD^` 가 `8043382ec66bde6125130d3de2ceb9bc4bc8b6e4` 이고, `git diff --stat HEAD^ HEAD` 가 `HANDOFF.md` 뿐이며, working tree가 CLEAN.
- 관련 PR: https://github.com/pds2225/auto_write/pull/211
  - `gh pr view 211`: `state=OPEN`, `isDraft=true`, `mergedAt=null`, `baseRefName=main`, `headRefName=cursor/rhwp-unsupported-lrule-status-6a12`, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`
  - checks: `docs-gate` SUCCESS (completedAt 2026-09-30T07:32:49Z). 그 외 체크는 이 세션에서 확인하지 않음.
- Merge: **하지 않음.** 사용자 지시가 머지 금지다. draft라 GitHub auto-merge도 걸 수 없다.

최근 커밋 (이 브랜치, `git log -8 --oneline`):

| SHA | 내용 |
|-----|------|
| `8043382` | fix(hwpx): 예시 칸은 본문 스타일로 바꾸고 라벨 칸·기지원 표·전역 taskkill을 막는다 |
| `4b63211` | fix(rhwp): P0 기본은 rhwp를 끄고 HWPX 변환은 한글 COM만 쓴다 |
| `b43eceb` | fix(hwpx): 양식 유색은 초안 사유가 아니고 기업칸·PDF·레지스트리를 맞춘다 |
| `883d43b` | fix(rhwp): JSON을 모르는 rhwp는 미설치로 보고 L규칙 검증을 폴링한다 |
| `6ed289f` | origin/main. 콘솔 L규칙 가드 (#210) |

## 이번 세션에서 완료한 것

이 세션은 제품 코드를 수정하지 않았다. `git status`가 이 파일을 쓰기 직전까지 CLEAN이었다.

- 한 일: 저장소·PR·L050 집계·채움/COM 소스·라벨 키·업로드된 Round-3 요약/CSV를 읽고 이 문서를 현재 상태로 다시 썼다.
- 완료 근거: 아래 「확인한 사실」. 실행 검증은 소스 판독과 `python3` 라벨/플레이스홀더 호출뿐이다. pytest는 이 세션에서 실행하지 않았다.
- 이전 세션이 이미 커밋한 것 (다시 구현하지 말 것, 단 이번 세션에서 재실행 검증은 하지 않음):
  - rhwp 기본 꺼짐. `.hwp`→HWPX 기본은 한글 COM. `AUTO_WRITE_ENABLE_RHWP` opt-in만 rhwp.
  - 값을 쓴 run이 유색/기울임이면 검정 정자체 클론. 원본 charPr와 손대지 않은 양식 색은 유지.
  - HWPX 예시 칸(`OOO`, `000-0000-0000`, `OO도 OO시·군`, 슬래시 옆 공백이 있는 선택 안내). `_is_obvious_placeholder`는 전역으로 바꾸지 않음.
  - T02가 `팀      명 :`에 값을 붙이고 그 문단 lineseg만 제거. `fill_hwpx`는 `비고 :`(가시 빈칸 없는 콜론)를 채우지 않음.
  - 오른쪽에 값 칸이 있으면 라벨 칸의 빈 run에 값을 쓰지 않음.
  - 기지원/창업지원금 표에는 신청인 신원(기업명·대표자·연락처·주소·이메일·사업자등록번호·설립일)을 넣지 않음. `단체명`은 동의어에 남김. 같은 표의 `사업명` 빈 칸은 기존 테스트가 채움을 요구함.
  - `kill_hangul_processes`는 `[]`. 전역 `taskkill /IM` 없음. 새로 뜬 PID만 `/PID`.
  - L050 `category=gap`. PDF 거부 문구 `BLOCKED-by-form: Hangul refused SaveAs PDF for this form`. PDF 실패가 `_DRAFT`를 만들면 안 됨.

## 아직 완료되지 않은 것

Round-3 (head `8043382`)는 구현 전이다. `app/tests/test_hwpx_round3_fill.py` 없음.

사용자 제출 요약 (`summary_7958.md`, 이 VM 업로드, **저장소 밖**): 전체 FAIL. 통과 yechang, smartmfg, sba. 실패 dips, saas, hwp_ex, onlab, sinchung, ipdidim. 유지해야 할 것: 값 스타일(검정 정자체), 라벨 칸, 콜론 간격, onlab 단체명 이력 제외, hwp_ex가 `_DRAFT`가 아님, 전역 taskkill 없음(미리 연 미저장 한글 창이 살아 있음).

### 현재 BLOCKER

증상: 같은 직접 HWPX 채움이 이력 표의 `지원기관` 칸에 사업명을 넣고, 남은 예시/안내 칸을 비우며, 고치지 않은 제목 문단의 lineseg를 지우고, 변경 추적이 켜진 양식의 PDF 저장에서 한글 대화상자에 멈춘다.

재현 (사용자 보고, **이 세션에서 재실행하지 않음**): Windows, 한글 2022, head `8043382`, in-process `POST /console/documents/write`, `AUTO_WRITE_ENABLE_RHWP` 미설정. 가짜 프로필: 기업명 테스트주식회사, 대표자 홍길동, 팀명 테스트팀, 사업자등록번호 123-45-67890, 연락처 010-1234-5678, 주소 서울특별시 테스트구 테스트로 123, 4층, 설립일 2020-01-15, 이메일 test@example.com, 홈페이지, 업종, 직원수 12명, 자본금, 팩스, 창업아이템명·사업명·과제명 `AI 기반 문서 자동작성 플랫폼 고도화`, narrative/notes.

이 Linux VM에는 한글 2022가 없다. E2E 재현은 미검증.

### 항목별 (소스에서 이 세션에 확인한 것 / 추정은 추정)

1. DIPS 잘못된 표. **원인 확정(코드).** `_PRIOR_SUPPORT_RE`는 `창업지원금|수혜 이력|지원 이력|기 지원|기지혜|과거 지원|참여 이력|지원금 수혜|수혜 실적|기수혜`만 본다. `타 창업지원사업`, `신청·수행 여부`, `중복`, `수행실적`은 없다. `사업명`은 `_APPLICANT_IDENTITY_REPS`에 없으므로 이력 표로 잡혀도 사업명 쓰기를 막지 않는다. 데이터 칸 글자 `사업명`이 라벨이 되고 오른쪽 `OOOOO`(지원기관 열)가 예시 칸이라 채워진다. 사용자 증거: `completeness`가 아니라 요약 1번과 제목 `2. 타 창업지원사업 신청·수행 여부`. **기존 테스트 `test_prior_support_table_does_not_take_applicant_identity`는 이력 표의 `사업명 | 빈칸`이 `테스트사업`이 되기를 요구한다. 그 단언을 지우거나 약하게 하지 말 것.** 고칠 방향: 키워드 확장 + `사업명`을 `지원기관` 열에 쓰지 않기 + 머리글과 같은 글자의 데이터 칸을 오른쪽 쓰기 라벨로 쓰지 않기.

2. 남은 예시. **일부 확정(이 세션 `python3` 호출).**
   - `OOOOO (법인등기부등본 … 기입)` 길이 47. `_is_hwpx_example_scaffold` False, `_is_obvious_placeholder` False. 순수 `OOOOO`만 예시로 본다.
   - 라벨 `사업장 소재지 (본사(점))`의 `key()`는 `사업장소재지)`이고 `cluster_rep`는 None. 값 `OO도 OO시·군`은 scaffold True인데 라벨 키가 어긋나 못 채우는 것으로 본다. 괄호 제거는 `SubmittableFiller._key`의 `\(.*?\)` 한 번이라 중첩 괄호 뒤에 `)`가 남는다.
   - `0000년 00월 00일`은 `_is_obvious_placeholder` True, scaffold False. 라벨 `개업연월일`은 cluster `설립일`. CSV에 개업연월일 행이 없다. 실제 칸이 이 문자열만인지는 **미확인**(양식 XML이 저장소에 없음).
   - `010-0000-0000`, `(휴대폰)`, `예비창업의 경우 “예비창업자“ 기재`, `앙트프러너십팀`, `startup@koef.or.kr`은 scaffold False이고 obvious False.
   - onlab 서약 `팀 명 :`는 `fill_hwpx`가 가시 빈칸 없는 콜론을 채우지 않는다. `비고 :` 테스트(`test_inline_colon_space_only_not_filled`, `test_body_colon_space_only_not_filled`)를 깨면서 콜론만 채우게 바꾸지 말 것. 두 번째 인물 행(OOO / qwer@abc.co.kr)은 사용자 지시로 채우지 말 것. 서명 `(서명)`은 덮지 말 것.

3. 안 채워진 칸. **라벨 키는 이 세션에 확인.**
   - `설립일자 (창업 예정일)` → `설립일자` cluster `설립일`. `업태`/`휴대전화`/`개업연월일`은 이미 동의어다. 동의어 부재가 아니라 값 칸이 안내문이라 채움 대상이 아닌 경우가 있다. saas 설립일자 값 `예비창업의 경우 창업 예정일 작성`, 사업자등록번호 값 `예비창업의 경우 “예비창업자“ 기재`는 obvious/scaffold 모두 False (위 호출).
   - `사업의 종류(업태)` → `사업의종류` cluster None. 괄호를 지우면 `업태`가 사라진다.
   - `e-mail 주소` → `e-mail주소` cluster None. `E-mail` → `E-mail` cluster None. `e-mail` 소문자는 cluster `이메일`. ipdidim `E-mail` EMPTY, sinchung `e-mail 주소` EMPTY의 라벨 불일치는 확정. 대소문자 접기는 없다.
   - hwp_ex 라벨 `연 락 처`는 cluster `연락처`. 값 `(휴대폰)`이 플레이스홀더가 아니다.
   - `창업아이템 개요`: `project_service._generate_hwpx_direct`는 `answers`의 `user_brief`/`user_notes`를 identity에 넣지 않는다(소스 확인). 안내 서술 쓰기는 `authorize_guidance_narrative_writes`가 있고, 라벨이 정확히 맞을 때만 `apply_t02_analyzer_writes`가 넘긴다. hwp_ex 양식 XML은 이 저장소에 없어, 그 칸이 이 경로의 빈 run인지 **미확인**. notes를 개요에 매핑하는 코드는 없다. 값을 지어내지 말 것. 경로에 들어가면 notes를 매핑하고, 아니면 왜 안 쓰는지 보고에 남길 것.

4. L074. 사용자 보고: dips/saas에서 편집하지 않은 제목 문단의 lineseg가 빠짐(dips 1420→1412, saas 306→297). 픽셀 변화 없음. **코드:** `_strip_linesegarray`는 `scope.iter(linesegarray)`로 내려가고, `_fill_section_xml` 끝은 `id(paragraph)`로 편집 전 글을 비교한다. 같은 파일의 다른 주석은 lxml `id()` 재사용을 피하라고 되어 있다. 제목 문단이 그 때문에 지워지는지는 실양식 XML 없이 **추정**. 고칠 때 `test_strip_linesegarray_when_filled`(값 칸만 제거, 바깥 문단 1개 유지), `test_strip_linesegarray_only_under_preserves_siblings`, `test_linesegarray_kept_when_no_change`를 유지할 것. 실제로 글이 바뀐 문단만 지울 것.

5. ipdidim PDF 멈춤. **코드 확정:** `_convert_via_com`은 `SetMessageBoxMode(0x00000020)`만 호출하고, COM 단계 타임아웃이 없으며, 락이 없다. 사용자 보고: 변경 추적 대화상자 `변경 추적 기능이 사용된 문서입니다… [저장][취소]`에서 550초 멈춤. `0x00000020`으로는 안 닫힌다고 함(이 세션에서 한글으로 재현하지 않음 → 대화상자 억제 성공은 미검증). 타임아웃 시 이번 호출이 만든 PID만 죽이고 L050은 BLOCKED, mechanized false, gap 유지. 기존 거부 문구 `BLOCKED-by-form` 테스트(`test_hangul_refuses_pdf_records_blocked_by_form`)를 깨지 말 것. mock으로 검증. Linux/mock/COM 성공으로 L050을 mechanized로 올리지 말 것. PDF 실패로 `_DRAFT` 하지 말 것. L005 픽셀 PASS라고 쓰지 말 것.

6. Windows 테스트. **코드 확정, 실패 재현은 미검증(이 VM은 Linux).** `test_hwp_to_hwpx_default_uses_com_even_if_rhwp_exe_is_set`가 `native_hwp.subprocess.run`을 AssertionError로 패치한다. `_hangul_image_pids`는 win32에서 `subprocess.run`을 부르고 `OSError`만 잡는다. 사용자 보고: Windows에서 이 테스트 1건 실패, 2143 passed, 5 skipped. 단언(`calls == []`, `report.ok`, `method == hancom_com`, SaveAs HWPX)을 약하게 하지 말 것. 패치된 `subprocess.run`을 PID 조회가 호출하면 `calls`에 `rhwp`가 쌓이므로, 예외만 삼키는 것으로는 그 단언이 통과하지 않는다.

7. PID 경쟁. **코드 확정:** `_convert_via_com`은 변환 전후 `Hwp.exe` PID 차이로 소유 PID를 정한다. 그 사이에 다른 변환이 띄운 Hwp도 차이에 들어간다. 전역 `taskkill /IM Hwp.exe`로 되돌리지 말 것. `kill_hangul_processes`의 taskkill 부재와 Dispatch 직전 호출(`test_l003_kill_does_not_taskkill_every_hangul`, `test_l003_dispatch_calls_kill_before_com`)을 유지할 것.

saas 10–11행 담당자 성명/휴대전화, sinchung 종업원수를 `(3년전)`에 넣는 일은 사용자 지시에서 필수 수정이 아니다.

### 확인한 사실 (이 세션)

- `app/tests/lessons_coverage.json` `counts`: mechanized 69, gap 1, judgment 101, total 171.
- L050 lesson `category`=`gap`, `mechanizable`=`partial`. gap_desc에 `BLOCKED-by-form`이 있다.
- `.session/closeout_due.json` `due` false. 이 세션에서 ack 하지 않음.
- `RULES.md`, `CODEX.md`, `CONTRIBUTING.md`는 repo root에 없다. `AGENTS.md`, `CLAUDE.md`, `TASK.md`, `RESUME.md`, `README.md`는 있다.
- `TASK.md` `# 0`: `[~] AW-001`. 열린 `[ ]`: AW-002~AW-010, T-20260814-02, T-20260816-03. 공식 정본은 `origin/main:TASK.md`. 이 브랜치 TASK와 origin/main TASK의 diff는 이 세션에서 보지 않았다 → **미확인**.
- `RESUME.md` 최종 갱신 표기는 2026-08-31이다. 현재 PR #211 상태를 반영하지 않는다. 이 세션에서 고치지 않았다.
- Python: `python3` 3.12.3. `pytest.ini`: `testpaths=app/tests`, `pythonpath=app`. `py -3.11` 런처는 이 VM에서 확인하지 않음.

## 테스트

이 세션에서 pytest를 실행하지 않았다. 아래 숫자는 PASS로 재판정하지 않는다.

```text
명령:
(이 세션) pytest 미실행

PR 본문에 적힌 이전 결과 (head 8043382, 이전 세션 기록, 이 세션 미재실행):
python3 -m pytest app/tests -q --tb=line
→ 13 failed, 2124 passed, 12 skipped, 87 warnings, 23 subtests passed in 163.75s

사용자 업로드 summary_7958.md 에 적힌 Windows 결과 (이 세션 미재실행):
1 failed, 2143 passed, 5 skipped
실패로 적힌 테스트:
app/tests/test_hwp_docx_convert.py::test_hwp_to_hwpx_default_uses_com_even_if_rhwp_exe_is_set

판정:
이전 13건 실패의 현재 재현 여부는 미확인.
Windows 1건은 코드 경로(OSError만 처리)와 맞지만, 이 Linux에서 그 테스트가 실패하는지는 미확인
(platform != win32 이면 _hangul_image_pids 가 tasklist 를 부르기 전에 return).
```

PR 본문이 이전 13건을 “이번 diff 밖”으로 적은 것: `data/*.hwpx` 골든 11건, PIL `OSError: cannot open resource`, 제출 파이프라인 `'images' not found`. 이 세션에서 그 실패를 다시 보지 못했다 → 미확인. 지우거나 skip 하지 말 것.

이 세션에서 실행한 것:

```text
python3 로 label_utils.key / cluster_rep / _is_hwpx_example_scaffold / _is_obvious_placeholder
결과: 위 항목 2·3에 적은 True/False. pytest 아님.
```

## 실제 사용자 검증

- 실제 입력 사용: 미검증 (이 세션에서 양식을 넣지 않음)
- 실제 처리 경로 실행: 미검증
- 최종 결과 생성: 미검증
- 저장 / 재조회: 미검증
- UI 확인: 미검증
- 실제 파일 열기(한글 2022): 미검증. 이 VM에 한글 없음
- 배포환경 확인: 미검증
- regression: 미검증 (pytest 미실행)
- 사용자 업로드 요약·completeness CSV는 읽었다. 스크린샷 경로 `/workspace/pr211_r3/...` 는 이 VM에 없다 → 이미지 미검증
- 업로드 파일은 저장소에 없다: `/home/ubuntu/.cursor/projects/workspace/uploads/summary_7958.md`, `completeness_619f.csv`, `matrix_3ed0.csv`

## Production Path

```text
POST /console/documents/write
→ app/auto_write/operator_main.py operator_write_document
→ _run_document_generation
→ _hwpx_identity_from_references + project_service.save_project_form
→ project_service.generate
→ _generate_hwpx_direct
→ company_identity.build_direct_fill_identity
→ hwpx_submit.apply_t02_analyzer_writes
→ hwpx_submit.submit_hwpx (preserve_template=True, normalize_colors=False, submission_cleanup=False)
→ hwpx_fill.fill_hwpx
→ submission_gates.try_generate_sibling_pdf
→ (Windows, rhwp 꺼짐) hwp_docx_convert.export_pdf_via_com
→ _convert_via_com
→ 산출 output.hwpx (+ PDF 또는 BLOCKED)
```

핵심 함수:

- 채움: `app/core/docx/services/hwpx_fill.py` `_fill_section_xml`, `_is_hwpx_example_scaffold`, `_is_prior_support_table`, `_strip_linesegarray`, `_set_cell_text`
- 라벨: `app/core/docx/services/label_utils.py` `key`, `SYNONYMS`. 괄호 제거 구현은 `app/core/docx/services/submittable_filler.py` `SubmittableFiller._key`
- 플레이스홀더 전역(바꾸지 말 것): `app/core/docx/services/cross_form_autofill.py` `_is_obvious_placeholder`
- T02/서술: `app/core/docx/services/hwpx_protected_regions.py` `find_inline_field_targets`, `authorize_guidance_narrative_writes`
- 제출: `app/auto_write/services/hwpx_submit.py` `submit_hwpx`, `apply_t02_analyzer_writes`, `relax_t02_written_layout`
- identity: `app/auto_write/services/company_identity.py` `build_direct_fill_identity`
- COM/PDF: `app/core/docx/services/hwp_docx_convert.py` `_convert_via_com`, `_hangul_image_pids`, `_kill_owned_pids`, `kill_hangul_processes`
- L050: `app/core/docx/services/submission_gates.py` `_try_hangul_com_pdf`, `try_generate_sibling_pdf`
- `app/auto_write/services/hwpx_fill.py` 는 core를 재노출한다. 수정은 core 쪽을 고친다.

새로 병렬 채움 엔진을 만들지 말 것. `fill_hwpx` / `submit_hwpx` / COM 변환을 확장할 것.

## 보호할 기존 작업

- 머지 금지. main 직접 push 금지. force push / reset --hard / clean -fd / 기존 브랜치 삭제 금지.
- `app/tests/lessons_coverage.json` L050 `category=gap`과 counts 69/1/101/171을 mechanized로 올리지 말 것.
- 기존 테스트를 삭제·skip·단언 완화하지 말 것. 특히:
  - `test_prior_support_table_does_not_take_applicant_identity` (`사업명` → `테스트사업` 유지)
  - `test_inline_colon_space_only_not_filled`, `test_body_colon_space_only_not_filled`
  - `test_strip_linesegarray_when_filled`, `test_strip_linesegarray_only_under_preserves_siblings`
  - `test_l003_kill_does_not_taskkill_every_hangul`, `test_l003_dispatch_calls_kill_before_com`
  - `test_hangul_refuses_pdf_records_blocked_by_form` (`BLOCKED-by-form`)
  - `test_hwp_to_hwpx_default_uses_com_even_if_rhwp_exe_is_set`의 rhwp 미호출 단언
  - `test_example_scaffold_detector_rejects_real_words` (`GOOGLE`, `직위/직책`은 예시가 아님)
- `_is_obvious_placeholder` 전역 변경 금지 (GOOGLE/SOHO/O2O).
- `단체명`을 기업명 동의어에서 빼지 말 것.
- 전역 `taskkill /F /IM Hwp.exe` 금지. 사용자의 기존 한글 창을 Quit/Clear 하지 말 것.
- `preserve_template=True`일 때 전역 색 정규화·전역 lineseg 삭제를 켜지 말 것.
- `.env`, credentials, production config, lock file, 사용자 양식 원본, `results/`·`templates/` 원본 삭제 금지. Secret 값을 이 문서나 커밋에 넣지 말 것.
- `RESUME.md`, `CLAUDE.md`, `AGENTS.md`, `TASK.md`는 이 Round-3 수정에 필수가 아니면 건드리지 말 것.
- closeout `due`는 false. ack 하지 말 것.
- 환경변수 이름만: `AUTO_WRITE_ENABLE_RHWP`, `RHWP_EXE`, `AUTO_WRITE_ALLOW_HANCOM_2024_COM`. 값은 기록하지 않음.

## 시도했으나 쓰지 않기로 한 접근

- `fill_hwpx`에서 콜론 뒤 공백만 있는 칸을 일괄 채움: Round-2에서 `비고 :`에 `채우면안됨`이 들어가 테스트가 실패해 되돌렸다. 다시 그 경로로 서약 칸을 채우지 말 것.
- PID 조회가 패치된 `subprocess.run`을 호출한 뒤 Exception만 삼키기: 테스트의 forbid가 호출 시 `calls`에 `rhwp`를 넣은 다음 raise 한다. 삼켜도 `calls == []`이 깨진다.
- L050을 Linux mock COM 성공으로 mechanized 처리: 금지.

## 다음 최소 작업

```text
다음 최소 작업:
- DIPS 이력 표에서 사업명이 지원기관 열로 들어가지 않게 한다.
  _PRIOR_SUPPORT_RE 에 타 창업지원사업, 신청·수행 여부, 중복 지원, 수행실적(사용자 문구: 중복, 수행실적)을 넣고,
  머리글이 지원기관인 열에는 사업명/과제명을 쓰지 않는다.
  머리글과 같은 글자인 데이터 칸(예: 칸 텍스트가 사업명)은 오른쪽 칸을 채우는 라벨로 쓰지 않는다.
  합성 HWPX 회귀 테스트를 추가한다. 기존 이력 표 테스트의 사업명→테스트사업 단언은 유지한다.

왜 먼저 해야 하는가:
- 신청 사업명이 다른 사업 이력의 지원기관 칸에 들어가 표가 밀린다. 소스 위치가 확정되어 있고, 양식 XML 없이도 합성 표로 잠글 수 있다.

수정 예상 파일:
- app/core/docx/services/hwpx_fill.py
- app/tests/test_hwpx_round2_fill.py 또는 새 app/tests/test_hwpx_round3_fill.py (기존 테스트 삭제 없음)

완료 조건:
- 제목 `2. 타 창업지원사업 신청·수행 여부`, 머리글 `순번|사업명|지원기관|...`, 데이터 `1 | 사업명 | OOOOO | ...` 인 합성 HWPX에서 지원기관 칸에 프로필 사업명이 없다.
- test_prior_support_table_does_not_take_applicant_identity 가 그대로 통과한다.

검증 명령:
- python3 -m pytest app/tests/test_hwpx_round2_fill.py app/tests/test_hwpx_fill.py -q --tb=line
- 새 테스트 파일을 만들었다면 그 경로를 같은 명령에 포함한다.
- 전체 `python3 -m pytest app/tests -q --tb=line` 은 그 다음이다. 이 세션에서는 돌리지 않았다.

이 작업에서 건드리지 않을 것:
- COM 타임아웃, PID 락, lineseg, 예시+안내 혼합 칸, L050 category, rhwp 기본값, RESUME/CLAUDE/AGENTS/TASK, 머지
```

그 다음 순서 (이 최소 작업에 섞지 말 것): (2) 혼합 예시·깨진 라벨 키·`E-mail` 대소문자·안내만 있는 칸 (3) 편집된 문단만 lineseg (4) COM 대화상자·타임아웃·소유 PID, mock 테스트 (5) subprocess PID 조회가 rhwp 테스트의 `calls`를 오염시키지 않게 (6) 변환 직렬화 또는 정확한 소유 PID (7) 창업아이템 개요는 서술 경로에 들어갈 때만 notes 매핑, 아니면 이유를 보고.

## 재개 정보

```text
[RESUME]

현재 Branch:
cursor/rhwp-unsupported-lrule-status-6a12

현재 HEAD:
이 문서 커밋의 parent = 8043382ec66bde6125130d3de2ceb9bc4bc8b6e4
재개 시 `git rev-parse HEAD` 와 `git status` 로 이 문서 커밋 이후 변경이 없는지 볼 것.

Working tree:
이 파일 작성 직전 CLEAN.
이 파일 커밋이 HANDOFF.md 하나만 바꾸었고 그 뒤 CLEAN 이면 이 문서와 일치.

마지막 성공:
- 제품 코드 커밋 8043382 가 origin 에 있다.
- PR #211 은 OPEN draft, mergedAt null, docs-gate SUCCESS.
- 라벨 키/플레이스홀더 판정을 이 세션 python3 로 확인했다.

마지막 실패:
- 이 세션에서 pytest/E2E 를 돌리지 않았다. 실패를 새로 재현하지 못함.
- 사용자 보고(미재실행): Round-3 E2E 3/9, Windows pytest 1 failed.

현재 BLOCKER:
- 사업명이 타 창업지원사업 표의 지원기관 열에 들어감. 코드 원인 확정. 수정은 없음.

마지막 실행 명령:
- git fetch origin main
- gh pr view 211
- python3 로 key/cluster_rep/_is_hwpx_example_scaffold/_is_obvious_placeholder

마지막 테스트 결과:
- pytest 미실행. PASS/FAIL 없음.

다음 최소 작업:
- 지원기관 열에 사업명을 쓰지 않는 합성 HWPX 회귀 + _PRIOR_SUPPORT_RE 확장. 기존 사업명→테스트사업 단언 유지.

재개 후 첫 명령:
- git status && git rev-parse HEAD && git rev-parse HEAD^
- 그 다음 app/core/docx/services/hwpx_fill.py 의 _PRIOR_SUPPORT_RE 와 _fill_section_xml 표 루프를 읽고, 위 최소 작업만 구현
```
