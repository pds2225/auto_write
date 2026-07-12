---
description: PSST 4영역(문제·실현·성장·팀)을 검사(기본)하거나 --apply 로 누락/미흡 영역에 작성 뼈대+가이드를 삽입한다.
argument-hint: <input.docx> [--apply] [--out 결과.docx] [--json]
---

# /auto-write-psst

## 사용 목적

사업계획서/발표평가 유형 DOCX 의 **PSST 4영역 구조 충실도**를 다룬다.
PSST = Problem(문제인식) / Solution(실현가능성) / Scale-up(성장전략) / Team(팀구성).

두 가지 모드가 있다.

- **기본(검사 모드, 읽기 전용)**: `psst_check.check_psst` 로 각 영역 등급(누락/미흡/적정/우수)과
  빠진 하위항목을 리포트만 한다. 파일을 고치지 않는다.
- **`--apply`(보강 모드, 실제 수정)**: `psst_fill.apply_psst_scaffold` 로 **누락·미흡 영역**에
  문서 끝에 **작성 보강 가이드 섹션**(영역 헤더 + 빠진 항목 체크리스트)을 삽입한다.
  - 내용을 지어내지 않는다. "(작성 필요)" 자리표시만 넣어 사용자가 직접 채우게 한다.
  - 실제 알맹이는 사용자(또는 AI 초안)가 작성해야 PSST 점수가 오른다(날조 금지).

쉽게 말하면: 기본은 "문제·해결·성장·팀이 빠짐없이 들어갔나" 점검, `--apply` 는 "빠진 부분에
무엇을 써야 하는지 작성 뼈대를 문서에 넣어준다".

## 입력값

- `input.docx` (필수): DOCX 절대경로 또는 `app` 기준 상대경로.
- `--apply` (선택): 누락/미흡 영역에 작성 가이드를 삽입(미지정 시 검사만).
- `--out` / `-o` (선택, `--apply` 와 함께): 결과 DOCX. 미지정 시 `results\<원본>_psst.docx`.
- `--json` (선택): 결과 JSON 출력.

검사/보강 대상 유형: business_plan(사업계획서), pitch_deck(발표평가) 권장.
규칙: **원본 덮어쓰기 금지**(out ≠ in, 같으면 `ValueError`).

## 실행 워크플로우(단계)

1. **유형 확인(권장)**: `classify_docx(path)` 가 business_plan/pitch_deck 이 아니면 사용자 확인.
2. **검사 모드(`--apply` 없음)**: `check_psst(doc)` → 영역별 등급/빠진 항목/전체 충족률 보고.
3. **보강 모드(`--apply`)**: `apply_psst_scaffold(in, out)` →
   - 등급이 '누락' 또는 '미흡' 인 영역마다 문서 끝에 헤더 + 빠진 항목 체크리스트 삽입.
   - 보강 영역 수 / 추가 항목 수 / 출력 DOCX 경로 보고. 원본 보존(out ≠ in).
4. 보강 후 실제 내용은 사용자가 채워야 함을 명확히 안내한다(가이드는 점수에 반영 안 됨).

## 호출 에이전트

- `doc-analyzer`: 검사(`check_psst`) + 유형 분류.
- `doc-postprocessor`: 보강(`psst_fill.apply_psst_scaffold`) 담당(DOCX 변형).

## 예시 명령(실제 PowerShell)

```powershell
cd D:\auto_write\app

# 1) 검사만(읽기 전용)
python -c "from docx import Document; from auto_write.services.psst_check import check_psst; r=check_psst(Document(r'C:\제출\사업계획서.docx')); print(r.summary); [print(a.label, a.grade, '누락:', a.missing_items) for a in r.areas]"

# 2) 누락/미흡 영역에 작성 가이드 삽입(원본 보존)
python -c "from auto_write.services.psst_fill import apply_psst_scaffold; r=apply_psst_scaffold(r'C:\제출\사업계획서.docx', r'D:\auto_write\results\사업계획서_psst.docx'); print('보강영역', r.areas_scaffolded, '| 추가항목', r.items_added, '| 출력', r.output_docx)"
```

## 실패 시 처리

- 파일 없음/손상: 절대경로 재확인, `Document()` 로드 실패 메시지 보고 후 중단.
- 출력=입력 동일(`ValueError`): `--out` 다른 경로 지정 안내.
- 전 영역 '적정' 이상이면 보강 대상 없음 → "수정 없음(보강 불필요)" 보고.
- import 오류: `cd D:\auto_write\app` 에서 실행했는지 확인.

## 보고 형식

첫 줄 상태: `정상 실행 확인됨` / `수정만 완료` / `미검증` / `실행 막힘` / `수정 없음`.
- 대상 파일/분류 유형
- (검사) 전체 충족률 + 영역별 등급/빠진 항목
- (보강) 보강 영역 수·추가 항목 수·출력 DOCX, 사용자 직접 작성 안내
