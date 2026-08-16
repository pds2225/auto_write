# RESUME.md — 세션 재시작 시 이어하기 진입점

> 새 세션을 시작하면 이 파일을 가장 먼저 읽어라. (최종 갱신: 2026-08-16 22:56)

## 0. 30초 컨텍스트
도보네비 사업계획서. 기준 양식은 PSST. AIMY 본선본을 모듈 팩으로 잘랐고 1단계 검수는 PASS. **지금은 정지.** 공고+빈 양식이 오면 초안 1건만 쓴다. AIMY급 자동작성(BPQ-00)은 사용자가 대기라 시작하지 않는다.

## 1. 빠른 재개 (복붙용)
```powershell
cd D:\auto_write
# 공고+빈양식이 오면: 모듈 팩을 읽고 초안 1건 (원본 덮어쓰기 금지)
# 모듈: results\aimy_form_rules\modules\
# 테스트는 py -3.11 (기본 3.14 는 matplotlib 부재)
```

## 2. 완료된 작업 ✅
- [x] KICXUP 1~3 종료(미접수)
- [x] 킥스업 문체·라벨 대조표
- [x] AIMY 본선 역추정 보고서
- [x] PSST 모듈 팩 + AUDIT PASS (이슈 2건은 기록만, 코드 미수정)
- [x] 작업지시서 원격 등록(T-20260814-02 명세). 구현 안 함

## 3. 남은 작업 ⬜ (다음 세션에서 이어서)
- [ ] **공고 + 빈 양식이 오면** 모듈을 P→S→Sc→T 순으로 읽어 초안 1건
- [ ] 그 1건에서 칸 갭이 숫자로 나온 뒤에만 엔진 연결·킥스업/KAMCO 쪼개기
- [ ] BPQ-00 / T-20260814-02 구현 — **시작하지 않음** (사용자 대기)

## 4. 핵심 결정·제약 (되돌리지 말 것)
- `facts_aimy.json` 수치·고유명사를 **다음 아이템 기본값으로 쓰지 말 것**
- 교차양식 = 사실 전사. 서술 재작성과 섞지 말 것
- GitHub default = `main`. TASK.md 도 main. master 는 구버전
- 원본 미수정 · 날조 0 · 출력≠입력 · 더미 공고 없음
- 대량 HWP 이미지는 비전으로 열지 말고 추출문+파일명으로 보고

## 5. 핵심 파일 인덱스 (어디에 뭐가 있나)
| 알고 싶은 것 | 파일 |
|---|---|
| 모듈 팩 | `results/aimy_form_rules/modules/` |
| 검수 | `results/aimy_form_rules/modules/AUDIT.md` |
| AIMY 역추정 | `results/aimy_form_rules/AIMY_대한안전보건교육원_본선제출_역추정.md` |
| 플랜 | `.omc/plans/2026-08-15-psst-modules-next.md` |
| 운영 위키 | `.omc/wiki/psst.md` |
| 최근 신청서 | `WORKS/KAMCO_TechBlaze/KAMCO_신청서_도보네비_박다솜_v4.1.hwp` |

## 6. 검증된 사실 (재확인 불필요)
- 모듈 1단계 검수 PASS. 엔진은 `modules/` 를 아직 안 읽음
- 양식 「해결방안」 vs 코드 「실현 가능성」, Team 헤더 정규식 = 알려진 갭(코드 미수정)
- KICXUP 추천·케이블텔레콤·신청서/동의서 = 종료(미접수)

## 7. 재개 시 첫 행동
1. 이 파일을 읽는다.
2. 공고+빈 양식이 **있으면** 초안 1건. **없으면** 기다린다. BPQ-00 구현을 시작하지 않는다.
3. AIMY 숫자를 새 초안에 복사하지 않는다.

## 8. 현재 세션 상태 (2026-08-16)
- [x] 사용자 요청: 로그아웃/세션 종료. Codex 전역 설정 오류 수정은 보류
- [x] Codex 시작 로그 진단: `cockpit-collector.toml`, `mail-acc-coverage-sentinel.toml`의 description 안 Windows 경로 백슬래시 때문에 TOML 파싱 실패
- [x] 코드·프로젝트 파일 수정 없음. 해당 에이전트 2개만 이번 세션에서 로드되지 않음
- [ ] 다음 액션: 사용자 요청 시 두 TOML의 백슬래시를 TOML 문법에 맞게 수정하고 `codex` 재시작으로 로드 여부 확인
- [ ] MCP 초기화 중단(`context7`, `filesystem`, `github` 등)은 별도 연결/플러그인 점검 대상

## 9. 다른 AI 작업 상태 점검 (2026-08-16)
- [x] 로컬 `TASK.md`, 루트 dirty 파일, Git worktree·stash·브랜치·실행 프로세스를 읽기 전용 점검
- [x] 확정된 코드 dirty 작업: `D:\tmp\wt-auto_write-m4-generate-prep`의 이미지 자동화 4개 수정 + 테스트 1개 추가(마지막 파일 수정 2026-08-10)
- [x] `rusalka-fill-task`는 추적 파일 변경 없이 HWPX 점검용 임시 파일만 남아 있고, 나머지는 문서 브랜치 또는 clean 상태
- [x] 루트 `master`는 로컬 `origin/master`보다 61커밋 뒤이며 `.claude/*`, `.gitignore`, `REQUEST_LEDGER.md`, `RESUME.md`가 dirty; 삭제·정리하지 않음
- [x] GitHub live PR 확인 완료: draft PR #149, #151~#154 확인

## 10. 원격 인증 진단 (2026-08-16)
- [x] 기본 Git HTTPS(Schannel)는 `SEC_E_NO_CREDENTIALS`로 실패
- [x] 같은 원격에 `git -c http.sslBackend=openssl ls-remote origin HEAD`는 성공하여 원격/네트워크 자체는 접근 가능
- [x] Git 전역 `http.sslBackend=openssl` 적용 및 `git ls-remote origin HEAD` 성공
- [x] 기존 무효 pds2225 GitHub 인증정보 로그아웃 완료
- [x] 브라우저 인증 완료 후 `gh auth status`·`gh auth setup-git`·Git 원격 조회·열린 PR 조회 성공
- [x] live origin은 `HEAD`/`main`=`0a8b262c...`이며 `master` ref는 조회되지 않음. 로컬 `origin/master`는 stale 추적 ref

## 11. 다음 프롬프트 고스트 스킬 (2026-08-16)
- [x] 중복 스킬 대신 기존 `run-next-suggestion`을 확장: 실질 작업 종료 시 `👉 다음 프롬프트:` 한 개를 생성하고, 선택 시 기존 실행 매핑을 유지
- [x] Claude 정본 스킬과 Codex·Claude·Cursor trigger pack에 `다음프롬프트 고스트`·`고스트 프롬프트`·`다음 프롬프트 스킬` 추가
- [x] `PYTHONUTF8=1 python ... quick_validate.py` 통과 및 `codex debug prompt-input`에서 loader 노출 확인
- [ ] 이미 열린 세션의 UI/캐시는 새 Codex 세션 또는 재시작 후 최종 반영 확인

## 12. 압축 후 복원 상태 (2026-08-16)
- [x] 대화 압축 후 `RESUME.md` 체크포인트 갱신
- [x] 사용자 확인 후 `session-closeout` 저장 절차 시작
- [x] agent-self-learning: 자가학습 감시견 정상, 최근 평가 표본 부족 상태 확인
- [x] skill-harvester: 기존 `run-next-suggestion` 확장으로 중복 생성 없음
- [x] wiki-session-capture: 인증 우회법·고스트 프롬프트 지식 저장, broken refs 0
- [x] session-recap: `D:\auto_write\SESSION_RECAP.md`에 최신 회고 누적
- [x] session-resume: 이 체크포인트 최종 갱신
- [x] 새 Codex CLI 세션에서 고스트 프롬프트 응답 노출 확인
- [ ] 저장 완료 후 사용자가 `/clear` 실행

## 13. 현재 확인 작업 (2026-08-16)
- [x] `run-next-suggestion` 규칙과 Codex trigger pack에 `다음프롬프트 고스트`가 포함된 것을 읽기 전용 확인
- [x] `codex debug prompt-input "다음프롬프트 고스트"`에서 해당 트리거가 로더 입력에 노출됨을 확인
- [x] 별도 새 `codex exec` 세션에서 동일 문구를 입력하고 실제 `👉 다음 프롬프트:` 응답 확인
- [ ] Codex Desktop의 회색 입력 제안 UI 자체는 현재 도구에서 시각 확인 불가
