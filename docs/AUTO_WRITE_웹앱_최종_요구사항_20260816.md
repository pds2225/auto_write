AUTO_WRITE 웹앱 최종 요구사항_20260816

Google Docs(실행 정본): https://docs.google.com/document/d/1E4aHoLtC36XS8E19jzR8B9nP8__H1zePYtjslL03LRo/edit
대상 저장소: GitHub pds2225/auto_write
작성일: 2026-08-16
상태: 최종계획. 이 문서 승인 전까지 웹앱 제품 코드 대기.

이 문서가 웹앱의 유일한 사양서다.
대체하는 문서:
- 2026-08-14 사양: https://docs.google.com/document/d/1afL0r7pk0Iei0RZoDNgSulpd5uc8fYbdT7eb_wrTxuY/edit (역사 보존, 실행 정본 아님)
- 2026-08-16 공유본: https://docs.google.com/document/d/15eaMmOmtEBPuxUFXnNQdLFGzsfMbQWjQ5cIam6U7O-w/edit (역사 보존, 실행 정본 아님)

작업지시 파일은 GitHub 루트 TASK.md다. 이 사양서와 TASK.md가 충돌하면 이 문서의 「확정」이 웹 UX 충돌 부분만 덮는다.

목적: 기존 auto_write 엔진을 재사용하여 비개발자가 사업계획서를 작성·수정하고, L 규칙·아키텍처·업무 흐름·GitHub 동기화 상태를 확인·관리하는 운영 웹앱.

최상위: GitHub 원격이 시스템 정의의 Source of Truth. 웹과 원격은 실제 양방향 Sync. 고객 문서·사업계획서 원본은 GitHub Sync 대상이 아니다.


0. 확정 (2026-08-16 사용자. 충돌 부분만 덮음)

0.1 첫 화면 (최우선 기준을 이렇게 구체화)
- 필수: 공고+양식.
- 공고와 양식이 한 파일에 같이 있을 수 있다. 파일이 2개 이상일 수도 있다.
- 기존 사업계획서 첨부는 (선택).
- 처음부터 회사소개·재무·메모 업로드칸을 다 펼치지 않는다.
- 세 역할(공고 / 양식 / 기존 계획서)은 칸으로 명시한다. 한 파일이 공고+양식이면 사용자가 그렇게 표시한다.

0.2 작성 시점
- 파일(최소 공고+양식)이 있어야 한다. 없으면 진행 불가.
- 작성계획 확인 → 사용자 승인 후에만 초안.
- 문서 전체를 한 번에 쓰지 않는다. 지금 화면의 파트만 작성한다.

0.3 분해·재조립 (가장 중요: 최종 칸 = 공고·양식 대목차)
- 과거 자료를 의미 모듈로 나눈다.
- 그 모듈을 이번 공고·양식 대목차 아래에 재배치한다.
- 양식은 대목차 정도만 나온다. 중·소목차·제목은 모듈 이름을 쓴다.
- PSST(Problem/Solution/Scale/Team) 표시는 선택사항. 최종 나누기 기준이 아니다.
- 정본 위키: GitHub docs/WEBAPP_MODULE_TO_FORM_TOC.md

0.4 구현 대기
- 이 최종계획 승인 전까지 웹앱 제품 코드·엔진 연결 코딩을 시작하지 않는다.
- TASK.md 사양 반영은 허용.

0.5 칸 내용 우선순위
1) 사실 전사
2) 사실과 비슷한 것을 찾음 (오매칭은 빈칸보다 못함)
3) 아예 없으면 생성. 반드시 「생성」이라고 표시. 출처 있는 사실처럼 위장 금지.

0.6 자동판정
- 제출 가능/불가능 자동판정 UI 없음. 사람이 판단.
- 품질점수 자동 산정 UI 없음.
- 엔진의 _DRAFT 게이트는 끄지 않는다. 웹 메뉴에 올리지 않을 뿐이다.

0.7 P0 / P2 / 업무 흐름 메뉴
- P0 미완이면 고도화 금지.
- P0 = 문서 작업 화면(업로드·모듈·목차 재구성·재료 선택·번호 지시·작성계획·해당 파트 초안) + GitHub 상태바 + L 규칙 전수 조회(읽기).
- P1 = L 규칙 수정·Git 반영·history·rollback, 결과 편집·USER_LOCKED.
- P2 = 업무 흐름 메뉴(Flow 지도, 단계별 L Rule, 서비스/코드), 시스템 아키텍처·상태 화면, Flow↔Rule↔Code 상호 탐색.
- 문서 작업 화면의 최소 진행표시(대기/작성중/실패, 실제 runtime)는 P0. 별도 「업무 흐름」 메뉴의 시각화는 P2. 둘을 섞지 않는다.


1. 아직 고를 것 (선택사항. 승인 전에 사용자가 정함)

아래는 2026-08-14 사양과 2026-08-16 공유본의 차이 중, 이번 확정에 안 들어간 것이다. 기본값을 적어 두었으니 바꾸면 말한다.

S1. 공고+양식이 한 파일일 때
- A: 사용자가 「이 파일 = 공고+양식」만 표시. 시스템이 구역 분리를 제안하고 사람이 승인.
- B: 사람이 공고 구간/양식 구간을 직접 지정.
기본 제안: A.

S2. 기존 사업계획서 첨부 개수
- A: 0 또는 1개.
- B: 여러 개.
기본 제안: B (여러 개 허용. 없으면 선택 안 함).

S3. 회사소개·재무·상담메모 등 추가 자료
- A: 첫 화면에는 없음. 공고+양식(+선택 계획서) 올린 뒤 「자료 더 넣기」.
- B: 첫 화면부터 기타 자료 칸.
기본 제안: A. (최우선: 칸을 다 펼치지 않음)

S4. 「해당 화면의 파트」의 단위
- A: 지금 보고 있는 양식 대목차 1개.
- B: 그 대목차 아래 모듈 1개.
기본 제안: A (대목차 1개 = 한 화면). 대목차 안에서 모듈은 중·소목차로 보여 준다.

S5. 파일 역할
- 확정: 공고/양식/기존계획서는 칸으로 명시. 자동으로 역할을 확정하지 않음.
- 남은 것: 시스템이 역할 초안을 제안하고 사람이 고칠지(A), 제안 없이 사람만 지정할지(B).
기본 제안: A (제안 + 사람 확정). 사람 확정 전 엔진 실행 금지.

S6. 고급설정 라디오
- 2026-08-14: 기본 UI 숨김. 필요 시 「그대로 사용 / 내용 활용」 2개.
- 2026-08-16 공유본: 고급설정에 3개 (기존 내용 우선 / 공고 맞춤 우선 / 기존 내용 사용 안 함).
기본 제안: 기본 UI 숨김. 고급설정은 3개. 기본값=AI 초안이 아니라 0.5의 전사→유사→생성 순서.

S7. DOCX
- 2026-08-14: 이번 웹 구축에서 DOCX 신규 개발·고도화 금지. 기존 코드는 삭제 금지.
- 2026-08-16 공유본: DOCX locator·양식 채움이 본문에 포함.
기본 제안: 기존 DOCX 엔진 재사용은 허용. 웹 전용 DOCX writer/편집기 신규 개발은 금지.

S8. 웹 L규칙 변경의 Git 반영
- A: 작업 브랜치 + PR만. PR 머지 후에야 기본 브랜치 SYNCED.
- B: 허용된 설정은 기본 브랜치 직접 push도 가능.
기본 제안: A. force push 금지.

S9. 문서 작업 화면의 진행표시 깊이 (P0)
- A: 대기 / 계획 승인 대기 / 작성중 / 실패 4상태만.
- B: 파일분석→모듈분해→… 전 단계를 P0에 표시.
기본 제안: A. 전 단계 타임라인은 P2 업무 흐름 메뉴.

정하지 않으면 위 기본 제안으로 승인된 것으로 본다.


2. 최우선 원칙 [P0]

- 코드 작성은 이 문서 승인 후. 승인 후 첫 일은 pds2225/auto_write 원격 최신 전수 분석.
- 기존 엔진·서비스·CLI·DomainRouter·LRuleEnforcer·Finalizer·cross-form 재사용. 웹 전용 복제 엔진 금지.
- 웹 전용 규칙 사본·별도 Source of Truth 금지.
- GitHub → Web, Web → GitHub 양방향 Sync를 실제 E2E로 검증.
- UI만으로 완료 금지. runtime, 원격 SHA, 실제 결과 파일로 판정.
- 고객 문서·사업계획서 원본은 GitHub Sync 대상이 아님. Sync 대상 = 코드·L 규칙·registry·workflow/architecture 정의·관리 설정.


3. 최종 사용자 메뉴

좌측 4개 + 상단 GitHub 상태바.

1) 문서 작업 [P0]
   작성 + 기존자료 활용(선택 첨부) + 해당 파트 수정 + 지원 변환 + 최소 진행상태(대기/작성중/실패)

2) L 규칙
   전수 조회 [P0]
   검색·수정·Git 반영·변경이력·rollback [P1]

3) 업무 흐름 [P2]
   실제 처리 Flow + 단계별 L Rule + 관련 서비스/코드
   P0 미완이면 이 메뉴를 고도화하지 않음. 문서 작업 화면과 이 메뉴를 하나로 합치지 않음.

4) 시스템 [P2]
   비개발자 Architecture + 시스템 상태 + 연결 오류

상단 GitHub Bar [P0]: Remote / Branch / Web SHA / Remote SHA / Sync / 충돌 / 최신화 / ahead·behind / 마지막 Sync 시각


4. 제외 기능

- 품질점수 자동 산정 및 품질 KPI 대시보드
- 제출 가능/불가능 자동판정 UI (사람 판단)
- 고객 CRM, 프로젝트 관리 대시보드, 영업·매출 KPI, 결제·구독
- 주자료/보조자료 필수 구분
- PRESERVE/ADAPT/REWRITE/NEW 및 4단 라디오를 기본 UI에 노출
- 가짜 progress animation
- 기존 엔진 중복 구현
- 페이지 번호만 주고 줄을 찾게 하는 UX


5. 저장소 사전 분석 (승인 후, 코드 전)

README.md, CLAUDE.md, RESUME.md, HANDOFF.md, PROJECT_REPORT.md
docs/BIZDOC_HUB_MAP.md, docs/WEBAPP_MODULE_TO_FORM_TOC.md
app/auto_write_hub.py, app/bizplan_autopilot.py, app/auto_write_autopilot.py
app/auto_write/services/, app/core/, app/bizplan/, app/resume/, .claude/
DomainRouter, LRuleEnforcer, Finalizer, Rule Registry
L 규칙 정의/호출/테스트/해시
기존 Web/API/서버, CLI / autopilot / pipeline / submit / web 진입점

DEAD_RULE, PARTIALLY_CONNECTED, DUPLICATE, CONFLICT, SHADOW_RULE, HARDCODED_RULE, UNKNOWN 전수.


6. 문서 작업 화면 [P0]

신규작성과 기존자료 작성을 별도 메뉴로 나누지 않는다. 한 화면.

6.1 업로드
필수
- 공고+양식 (1파일에 공고와 양식이 같이 있을 수 있음, 또는 2개 이상 파일)

선택
- 기존 사업계획서 첨부

이후 「자료 더 넣기」(S3 기본 A): 회사소개, 재무, 상담메모, 기타, 직접 입력 문장/표/메모

6.2 역할
공고 / 양식 / 기존 계획서는 칸으로 명시. 한 파일이 공고+양식이면 그 칸에 표시.
시스템이 역할을 제안할 수는 있다. 사람이 확정하기 전 작성 엔진 실행 금지. (S5 기본 A)

6.3 핵심 사용자 흐름
STEP 1. 공고+양식 업로드. 기존 계획서는 선택.
STEP 2. 양식에서 대목차 추출. 기존 자료를 모듈로 분해.
STEP 3. 모듈을 대목차 아래로 재구성. (선택: PSST 표시)
STEP 4. 사용자가 지금 대목차를 고르고, 원문을 보고 재료를 체크.
STEP 5. 선택 재료에 [1][2][3] 번호.
STEP 6. 자연어 지시. 예: 「1번은 그대로. 2번 표는 유지. 3번은 표에 추가.」
STEP 7. AI가 이 파트만의 작성계획(Composition Plan)을 보여 줌.
STEP 8. [이대로 작성] / [지시 수정]. 승인 전 초안 금지.
STEP 9. 해당 파트만, 우선순위 전사→유사→생성 으로 작성. 생성은 표시.
STEP 10. 그 파트 결과 검토. 다음 대목차로 이동.
STEP 11. 모든 대목차가 끝난 뒤에만 최종 양식 조립·결과 파일.

6.4 모듈 카드
모듈명 + 원문 미리보기 + 파일명 + 페이지. (선택: PSST)
제목만 보여 주고 원문을 숨기지 않음.
계층: 문서 → 대목차 → 모듈(중·소목차) → Block → 문장/표 행.
페이지는 출처 메타데이터. 선택 기준이 아님.
내부 locator: PDF page+block+bbox+hash / DOCX paragraph·table·cell·char / HWPX section·paragraph·run·cell / HWP 가능 구조 / XLSX sheet+cell.
화면 예: 창업도약_2025.docx / 경쟁사 비교표. 「원문에서 보기」로 하이라이트.
최종 출처 표시: 파일명 + 페이지.

6.5 선택·번호·붙여넣기
AI 추천 가능. 최종 선택은 사람.
전체 모듈 / 문단 / 문장 / 표 / 표 행·셀 선택 가능.
선택한 항목에 [1][2][3]…
주자료/보조자료 UI 없음. 모두 「선택한 재료」.
직접 붙여넣기 가능. 출처 없으면 「사용자 직접 입력」.

6.6 작성방식 UI
4단 라디오 기본 노출 금지. PRESERVE/ADAPT/REWRITE/NEW 기본 숨김.
고급설정(S6 기본): 기존 내용 우선 / 이번 공고 맞춤 우선 / 기존 내용 사용 안 함.
칸 내용은 항상 0.5 우선순위(전사→유사→생성)를 따른다.

6.7 Composition Plan (파트 단위)
target_section: 지금 대목차
selected_material_ids
user_instruction
ai_interpreted_actions
fill_rank: transcript | similar | generated
applicable_l_rules
source_locators
user_locked_ranges
psst_tag: 선택

바로 작성하지 않음. [이대로 작성] 후에만 이 파트 초안.


7. 결과 편집 [P1]

파트별 검토·수정. 제목·본문·표 셀·수치·출처.
AI 생성 / 사용자 수정 / 원문 사실을 구분. 생성 표시 유지.
USER_LOCKED는 재실행 시 보호.
특정 파트만 다시 작성. 다시 작성 전에도 작성계획 승인.


8. 출처

표시: 파일명 + 페이지. 복수 출처 허용. 사용자가 수정 가능.
근거 없으면 「자료 내 확인 불가」.
추론·제안·가정·생성은 사실과 구분.
원문에서 보기 = locator 하이라이트.


9. GitHub 양방향 Sync [P0]

웹 DB는 캐시·실행로그·임시 UI만.

9.1 GitHub → Web
「GitHub 최신상태 가져오기」. fetch. Remote HEAD vs Web SHA.
L Rule·mapping 재분석.
SYNCED / REMOTE_AHEAD / LOCAL_CHANGES / CONFLICT.

9.2 Web → GitHub [P1 수정 반영, P0은 상태 표시]
validation → 중복/충돌 → 테스트 → registry 파일 → hash → diff → commit → branch+PR(S8 기본 A) → Remote SHA 재검증.
실제 일치만 SYNCED. push/PR 실패면 SYNCED 금지.

9.3 충돌
시작 Base SHA vs push 직전 Remote HEAD.
원격 변경 시 자동 덮어쓰기 금지. force push 기본 동작 아님.


10. L 규칙

10.1 전수 조회 [P0]
repo/registry 스캔. 하드코딩 목록 금지.
ID, 이름, 분야, 설명, 적용대상, 강제수준, 상태, 사용위치, 최근수정, Git 상태.
검색·필터.

10.2 수정·Git [P1]
validation → 충돌 → 테스트 → registry → hash → diff → commit → PR → remote 검증.
history/rollback은 Git. rollback도 revert/commit.

10.3 연결상태 [P1]
Registry / DomainRouter / Bizplan / Resume / Autopilot / Submit / Finalizer / Web / Tests
CONNECTED / PARTIAL / NOT_CONNECTED. 코드 존재만으로 CONNECTED 금지.


11. 백엔드

새 문서 생성 엔진 중복 개발 금지.
core / bizplan / resume / auto_write services / DomainRouter / LRuleEnforcer / Finalizer / CLI / pipeline 재사용.
subprocess 남발보다 Python service import 우선.
웹에서 일반 Python 코드 자유 편집 불필요.
DOCX: 기존 엔진 재사용 허용. 웹 전용 DOCX writer/편집기 신규 금지. (S7)


12. P0 / P1 / P2 구분

P0 (승인 후 이것만. 미완이면 고도화 금지)
- 원격 분석
- 문서 작업 화면: 업로드(공고+양식 필수, 계획서 선택), 모듈 분해, 대목차 재구성, 원문 선택, 번호, 자연어, 작성계획, 해당 파트만 초안, 생성 표시
- GitHub 상태바 + GitHub→Web Sync 표시
- L 규칙 전수 조회(읽기)
- 문서 작업 화면의 최소 진행상태(대기/계획승인대기/작성중/실패)
- P0 E2E

P1
- 파트별 결과 편집, USER_LOCKED
- L 규칙 수정, Git 반영, history, rollback, runtime 연결상태

P2 (업무 흐름 메뉴 · 시스템 메뉴. P0 미완이면 착수 금지)
- 업무 흐름 메뉴: Flow 지도, 단계별 L Rule, 서비스/코드
- 시스템: Architecture, 상태 화면, Flow↔Rule↔Code
- 문서 작업 안의 최소 진행표시를 이 메뉴로 대체하지 않음


13. 필수 E2E

GIT-E2E-01 Remote Rule 변경 → Web Sync → 웹 반영
GIT-E2E-02 Web Rule 수정 → diff → commit → PR → Remote 파일 변경 (P1)
GIT-E2E-03 Web 수정 중 Remote 변경 → 충돌 탐지, 강제 덮어쓰기 금지
GIT-E2E-04 Push 실패 → SYNCED 금지
GIT-E2E-05 Rule rollback → Git → Remote → Web (P1)
GIT-E2E-06 Remote 코드구조 변경 → Sync → Architecture/Flow 재분석 (P2)

DOC-E2E-01 공고+양식(+선택 계획서) → 작성계획 승인 → 해당 대목차만 초안 → 기존 엔진 → 결과
DOC-E2E-02 기존 계획서 없이 공고+양식만 → 같은 화면. 재료 없으면 생성 표시
DOC-E2E-03 한 파일이 공고+양식 → 사용자 표시 후 진행
DOC-E2E-04 기존 문서+자연어 수정 → 그 파트만 → USER_LOCKED (P1)

MODULE-E2E-01 모듈 분해 + 원문 표시
MODULE-E2E-02 모듈을 양식 대목차 아래로 재구성. 중·소목차=모듈명
MODULE-E2E-03 선택한 문장/표만 해당 파트 Composition Plan에 포함
MODULE-E2E-04 [1][2][3] 자연어 → 계획과 일치
MODULE-E2E-05 승인 전 초안 파일 없음

LOCATOR-E2E-01 원문에서 보기 → 정확한 문단/표/문장 하이라이트
SOURCE-E2E-01 표시는 파일명+페이지, 내부 locator는 정밀
FILL-E2E-01 전사 → 유사 → 생성 순서. 생성 칸에 생성 표시. 사실 위장 금지

L-E2E-01 repo L Rule 수 = 웹 조회 수 [P0]
FLOW-E2E-01 문서 작업 최소 상태 = 실제 runtime [P0]
FLOW-E2E-02 업무 흐름 메뉴 단계 = 실제 실행단계 [P2]


14. Definition of Done

P0 DOD
- 문서 작업 한 화면. 공고+양식 필수, 기존 계획서 선택.
- 모듈 분해. 원문 확인. 문단/문장/표 선택. [1][2][3] 자연어.
- 모듈을 양식 대목차에 재구성. 중·소목차=모듈.
- 해당 파트 작성계획 승인 후에만 그 파트 초안. 전체 일괄 작성 없음.
- 전사 → 유사 → 생성. 생성 표시.
- 출처 파일명+페이지 + locator.
- GitHub 상태바. GitHub→Web Sync. 다른 상태를 SYNCED라고 하지 않음.
- L Rule 전수 조회 수 = repo.
- 제출가능 자동판정 UI 없음.
- P2 메뉴를 P0 미완에 고도화하지 않음.

P1/P2 DOD는 해당 단계 착수 후. P0 미완이면 P1/P2 DONE 금지.


15. 금지

- 웹 DB에만 L Rule
- GitHub 변경을 사람 수동 복사
- Remote SHA 없이 SYNCED
- push/PR 실패를 성공
- force push 기본
- L Rule 일부 하드코딩
- 코드 존재만으로 CONNECTED
- UI 목업만, 엔진 미연결
- 가짜 progress
- 기존 엔진 중복
- 페이지 번호로 내용 찾게 하기
- 주자료/보조자료 강제
- 4단 라디오 기본 UI
- 작성계획 승인 전 초안
- 문서 전체 일괄 작성
- 제출가능 자동판정 UI
- P0 미완 상태에서 업무 흐름·Architecture 고도화
- AIMY 사실 복사
- 원본 덮어쓰기. 출력 경로 = 입력 경로 금지


16. 최종 보고 형식 (승인 후 구현 세션)

GitHub Sync: Remote / Branch / Remote HEAD / Web HEAD / Sync Status
Web→GitHub, GitHub→Web, Conflict 테스트
화면과 데이터 원천
모듈 분해 / 대목차 재구성 / 선택 / 번호 / 자연어 / 파트 승인 / 생성 표시
L Rule 전체/Connected/Partial/Dead/Duplicate/Conflict
문서 기능 연결 상태
Architecture / Workflow (P2면)
변경 파일, Branch, Commit, PR
테스트 근거
BLOCKED와 원인


17. 최종 명령

예쁜 UI가 목적이 아니다.
문서작성 UX: 공고+양식(기존 계획서는 선택) → 모듈 분해 → 양식 대목차로 재구성 → 원문 확인 → 재료 선택 → 번호 자연어 → 작성계획 승인 → 그 파트만 작성(전사→유사→생성 표시).
시스템: GitHub 원격과 웹이 같은지 검증하고 양방향 Sync.
P0가 살기 전에 업무 흐름 메뉴와 시스템 지도를 꾸미지 마라.
이 문서를 사용자가 승인하기 전에 웹앱 코드를 시작하지 마라.
