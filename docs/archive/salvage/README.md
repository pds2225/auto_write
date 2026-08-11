# 고아 워크트리에서 회수한 코드 (2026-07-20)

등록이 끊긴 워크트리 폴더 22개를 정리하기 전, **git 어디에도 저장돼 있지 않은**
코드가 있는지 전수 검사(`git hash-object` → `git cat-file -e`)한 결과 회수한 것들이다.
20개 폴더는 고유 파일이 없어 안전하게 정리했고, 아래 2건만 여기 보존한다.

> ⚠ **원래 경로가 아니라 `salvage/` 아래에 둔 이유** — `cross_form_autofill.py` 는
> master 현재본(2343줄)과 다른 **오래된 갈래**(1224줄)다. 원래 경로에 두면 실수로
> 병합했을 때 회귀한다. 쓰려면 여기서 필요한 부분만 옮겨라.

## cross-form-pdf/ (1,467줄)
완성 사업계획서를 **PDF로 받아** 전사하는 기능. 현재 엔진은 DOCX/HWP/HWPX만 지원한다.
표 구조가 없는 플랫 텍스트에서 기업명·대표자 같은 짧은 식별항목만 앵커 방식으로 추출하며,
오매칭 방지 가드(값이 라벨이면 폐기, 긴 서술문은 길이 초과로 폐기)와 테스트가 갖춰져 있다.
→ 영구목표 `cross-form-value-autofill-goal` 의 확장.

- `cross_form_autofill.py` (1224줄, master 와 다른 갈래)
- `test_cross_form_pdf_source.py` (243줄, git 히스토리 전체에 없던 파일)

## fill-blanks-harness/ (749줄)
`SubmittableFiller` 를 감싸 **목차(섹션 제목)는 보존하면서 빈 내용칸만** 외부 plan 으로
채우는 1단계 골격(AI 미사용). 2단계 AI 채우기 연결 지점까지 설계돼 있다.
→ 메모리 `autowrite-fill-goal` ("목차 보존하며 빈 내용칸 채우기") = **품질하네스 1순위**와 일치.

- `blank_fill_service.py` (159줄)
- `test_blank_fill.py` (176줄)
- `_build_chochang.py` (414줄, master본 366줄 + `cmd_fill` 서브커맨드)
