# HANDOFF.md — auto_write 문서 품질 하네스 인계 문서

> 작성: 2026-06-06 / 다음 AI·개발자가 이어받기 위한 인수인계.

## 1. 현재 auto_write 구조 (요약)

- 정부지원사업 문서 자동생성 엔진(`app/auto_write/`, FastAPI + python-docx + OpenAI).
- 생성 흐름: 양식분석 → AI작성 → DOCX렌더 → 검수(`qa_service`) → finalize(`submittable_filler`).
- 실행: 시스템 Python 3.11~3.13(venv 없음), `app/` 이 import 기준. AI 키 없어도 동작.
- 상세: `AUTO_WRITE_DOMAIN_MAP.md`, `HARNESS_AUDIT.md`.

## 2. 생성한 하네스 구조

완성 DOCX 를 입력받아 **백업 → 유형분류 → 결정론 후처리 → PSST → 이미지제안 → 점수 → 게이트 → 보완루프 → 리포트** 를 수행. 생성 파이프라인과 독립(과거 산출물에도 적용 가능).

```
app/auto_write/services/
  doc_quality_ops.py              # 후처리(글머리표·표공백·빈문단·강조·안내문구·폰트)
  document_type_classifier.py     # 유형 9종 분류
  psst_check.py                   # PSST 4영역 검사
  infographic_suggest.py          # 도식 삽입 제안
  doc_quality_score.py            # 100점 점수·게이트
  document_quality_orchestrator.py# 파이프라인+백업/롤백
app/document_quality_orchestrator.py        # CLI 진입
scripts/run_document_quality_harness.py     # 래퍼
app/tests/test_document_quality_harness.py  # 회귀 테스트(11)
.claude/{agents,skills,commands,workflows}/ # 에이전트·스킬·커맨드·워크플로
```

## 3. Agent 목록 (`.claude/agents/`, 12)

document-architect · template-cleanup-agent · formatting-normalizer · content-emphasis-agent ·
document-type-classifier · psst-review-agent · infographic-suggestion-agent · quality-gate-agent ·
backup-rollback-agent · qa-document-agent · security-agent · documentation-agent

## 4. Skill 목록 (`.claude/skills/`, 허브 1 + 세부 11)

허브: **document-quality-orchestrator/SKILL.md** (CLAUDE.md 트리거 대상)
세부: docx-template-cleanup · bullet-spacing-normalization · paragraph-font-sizing ·
table-whitespace-cleanup · content-emphasis · document-type-classification ·
psst-structure-check · infographic-suggestion · document-quality-scoring ·
backup-and-rollback · document-quality-inspection

## 5. Workflow 목록 (`.claude/workflows/`, 1)

document-quality-harness.md (17단계 순서 + 병렬/순차 구분)

## 6. Command 목록 (`.claude/commands/`, 6)

`/improve-doc-quality` · `/auto-write-quality` · `/auto-write-inspect` ·
`/auto-write-psst` · `/auto-write-images` · `/auto-write-finalize`

## 7. 실행 방법

```powershell
# 패키지 설치된 Python (사용자 환경)
$py = "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"
cd D:\auto_write\app
& $py document_quality_orchestrator.py "C:\경로\문서.docx"          # 전체 1회
& $py document_quality_orchestrator.py 문서.docx -o 결과.docx --underline
& $py _build_chochang.py inspect "결과.docx"                        # 진단
# 또는 래퍼
& $py D:\auto_write\scripts\run_document_quality_harness.py "문서.docx"
```

## 8. 테스트 방법

```powershell
$py = "C:\Users\ekth3\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONPATH = 'D:\auto_write\app'
& $py -m pytest D:\auto_write\app\tests -q          # 전체 72개
& $py -m pytest D:\auto_write\app\tests\test_document_quality_harness.py -q  # 하네스 11개
```

현재 상태: **72 passed** (회귀 포함). 하네스 신규 11개 포함.

## 9. 품질점수 기준

100점 9항목: 안내문구15 / 글머리표10 / 문단공백10 / 글자크기15 / 표10 / 강조10 / 유형구조15 / PSST10 / 이미지5.
게이트: **90 우수 / 85 통과 / 70 보완 / 미만 실패**, passed=총점≥85. 미달 시 최대 10회 보완루프(수렴 시 조기종료).
상세: `DOCUMENT_QUALITY_SCORE_RULES.md`.

## 10. 백업·롤백 방법

- 후처리 전 원본을 `results/backup/<YYYYMMDD_HHMMSS>/` 에 자동 백업.
- 원본 절대 덮어쓰기 금지(출력=입력이면 ValueError).
- 복구: `python document_quality_orchestrator.py --rollback "<backup_dir>" "<target>"`.
- 상세: `BACKUP_ROLLBACK_RULES.md`.

## 11. 남은 문제 / 한계

- **git 미초기화**: 버전관리 없음. 커밋하려면 `git init` 필요(사용자 결정 대기).
- **실제 사용자 DOCX 검증 미수행**: 합성 샘플로만 end-to-end 확인. 실제 사업계획서 1건으로 검증 권장.
- **HWP/PDF 후처리 범위 외**: 후처리는 DOCX 단계만. HWP/PDF 변환 후 결과에는 미적용.
- **폰트 표준화 기본 비활성**: 서식 파손 위험으로 `--normalize-fonts` 옵션에서만 동작(보수적).
- **AI 분류 보조**: 키 있을 때만(모호 케이스). 키 없으면 규칙기반 분류.
- **이미지 실제 삽입 미수행**: 제안만 생성. 삽입은 `docx_ops.insert_image_*` 별도 호출 필요.

## 12. 다음 AI 에게 줄 프롬프트

```
D:\auto_write 의 문서 품질 하네스를 사용/확장한다.
- 구조: HANDOFF.md, AUTO_WRITE_DOMAIN_MAP.md, HARNESS_TEAM_DESIGN.md 참조.
- 실제 사업계획서 DOCX 1건으로 `cd app; python document_quality_orchestrator.py "<경로>"` 를 실행하고,
  생성된 results/*_quality_report_*.md 를 검토해 오탐(안내문구 오삭제, 과잉 강조)을 확인하라.
- 새 문서유형/시그니처는 document_type_classifier.py 의 _SIGNATURES 에, PSST 항목은 psst_check.py 의 _PSST_ITEMS 에 추가하고
  test_document_quality_harness.py 에 케이스를 더한 뒤 `python -m pytest tests -q` 로 회귀 확인하라.
- 원본 덮어쓰기·Secret 출력·백업 없는 수정 금지. 변경 시 CLAUDE.md 변경 이력에 기록하라.
```
