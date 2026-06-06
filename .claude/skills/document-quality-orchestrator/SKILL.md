---
name: document-quality-orchestrator
description: >-
  auto_write 문서 품질 개선 하네스 오케스트레이터. 완성된 DOCX(사업계획서·R&D계획서·
  컨설팅/정책자금/인증/수출/현장클리닉 보고서 등)의 품질을 자동으로 끌어올린다. 양식 안내문구
  삭제, 글머리표·표 공백 정리, 빈 문단 삭제, 핵심문장 Bold/Underline 강조, 문서 유형 자동분류,
  PSST 구조검사, 인포그래픽 삽입 제안, 100점 품질점수 산정·85점 게이트, 원본 백업·롤백까지 수행.
  '문서 품질 개선', 'DOCX 후처리', '양식 안내문구 삭제', '글머리표 공백 정리', '인포그래픽 제안',
  'auto_write 문서검수', '제출문서 서식 보정', 'PSST 검사', '품질점수 산정', '문서 최종검수',
  '사업계획서 다듬어줘', '보고서 정리해줘' 요청 시 반드시 사용. 다시 실행·재실행·수정·보완·
  부분 재실행(특정 단계만)·회귀 검수 요청도 이 스킬로 처리.
---

# 문서 품질 개선 하네스 오케스트레이터

완성된 DOCX 를 입력받아 **백업 → 유형분류 → 결정론적 후처리 → PSST/구조검사 → 이미지 제안 →
품질점수 → 게이트 → 보완루프 → 저장 → 리포트** 를 한 번에 수행한다. 전 과정은 AI 키 없이
결정론적으로 동작하며(분류 보조만 선택적 AI), 원본은 절대 덮어쓰지 않는다.

## 실행 모드: 에이전트 팀 (Team Ralph)

2명 이상이 협업하므로 에이전트 팀이 기본값이다. 단일 문서 1회 처리는 오케스트레이터 코드
(`DocumentQualityOrchestrator.run()`)가 전 단계를 단일 호출로 끝내므로, 팀은 **설계·검수·보완
의사결정이 필요한 경우**(예: 게이트 미달 반복, 새 문서유형 추가)에 구성한다.

데이터 흐름:
```
document-architect(파이프라인 설계)
  → template-cleanup-agent / formatting-normalizer / content-emphasis-agent (후처리)
  → document-type-classifier (유형 분류)
  → psst-review-agent (PSST, 사업계획서/발표자료)
  → infographic-suggestion-agent (도식 제안)
  → quality-gate-agent (점수·게이트·보완 트리거)
  → backup-rollback-agent (안전) / security-agent (보안 게이트)
  → qa-document-agent (회귀·검수) → documentation-agent (리포트·핸드오프)
```

## Phase 0: 컨텍스트 확인 (항상 먼저)

1. 입력 DOCX 경로가 주어졌는가? 없으면 사용자에게 요청.
2. `results/` 에 이전 품질 리포트가 있는가?
   - 있고 **부분 수정 요청**(예: "강조만 다시", "PSST만") → 해당 단계 커맨드만 재실행
     (`/auto-write-psst`, `/auto-write-images`, `/auto-write-inspect`).
   - 있고 **새 입력 문서** → 새 실행(이전 리포트 보존, 타임스탬프로 구분).
   - 없으면 → 초기 실행(전체 파이프라인).

## 표준 실행 (PowerShell)

```powershell
cd D:\auto_write\app
# 전체 품질 개선 1회
python document_quality_orchestrator.py "C:\경로\문서.docx"
# 출력 지정 + 밑줄 강조
python document_quality_orchestrator.py 문서.docx --output 결과.docx --underline
# 진단만(후처리 없이)
python _build_chochang.py inspect "결과.docx"
# 롤백
python document_quality_orchestrator.py --rollback "..\results\backup\<ts>" 결과.docx
```

또는 래퍼: `python D:\auto_write\scripts\run_document_quality_harness.py "문서.docx"`

## 단계별 담당 (커맨드 ↔ 에이전트 ↔ 코드)

| 단계 | 커맨드 | 에이전트 | 코드 |
|------|--------|----------|------|
| 전체 실행 | `/improve-doc-quality` | document-architect | `DocumentQualityOrchestrator.run` |
| 유형 분류 | (자동) | document-type-classifier | `classify_text/classify_docx` |
| 안내문구 삭제 | (자동) | template-cleanup-agent | `remove_guide_paragraphs` |
| 서식 정리 | (자동) | formatting-normalizer | `normalize_bullet_spacing`/`cleanup_table_whitespace`/`remove_empty_paragraphs` |
| 강조 | (자동) | content-emphasis-agent | `emphasize_key_sentences` |
| PSST | `/auto-write-psst` | psst-review-agent | `check_psst` |
| 이미지 제안 | `/auto-write-images` | infographic-suggestion-agent | `suggest_images` |
| 점수·게이트 | `/auto-write-quality` | quality-gate-agent | `score_document` |
| 검수 | `/auto-write-inspect` | qa-document-agent | `_build_chochang inspect` + `qa_service.build_report` |
| 최종 | `/auto-write-finalize` | documentation-agent | finalize + 검수 |

## 품질 게이트

- 90↑ 우수 / 85↑ 통과 / 70↑ 보완 필요 / 70 미만 실패. `passed = 총점 >= 85`.
- 미달 시 최대 10회 보완 루프(2회차부터 밑줄 강조 보강). 점수 변화 0.5 미만이면 수렴 → 조기 종료
  하고 잔존 결함을 **수동 확인 항목**으로 리포트에 명시(거짓 통과 보고 금지).

## 에러 핸들링

- 입력 DOCX 없음/확장자 오류 → 즉시 중단, 명확한 메시지.
- 출력 경로 = 입력 경로 → `ValueError`(원본 보호). 다른 경로로 안내.
- 후처리 중 예외 → 원본은 백업에 보존됨. 롤백 명령 안내.
- AI 분류 실패 → 규칙기반 결과 유지(중단 안 함).

## 테스트 시나리오

- **정상 흐름**: 사업계획서 DOCX → `business_plan` 분류 → 후처리 → PSST 100% → 점수 90+ → 통과 → 리포트 생성.
- **에러 흐름**: 출력=입력 경로 → `ValueError` → 사용자에게 다른 출력 경로 안내.
- 회귀: `cd app; python -m pytest tests/test_document_quality_harness.py -q` (11 통과 기대).

## 금지

원본 덮어쓰기, 백업 없는 수정, Secret/.env 출력, 유료 API 무단 호출, 실패의 성공 보고, 기존 생성 기능 삭제.
