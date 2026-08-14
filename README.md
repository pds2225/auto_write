# ✍️ auto_write — 사업계획서를 자동으로 써주고 다듬어주는 프로그램

> 한 줄 요약: **양식과 메모만 넣으면 사업계획서 초안을 만들어 주고, 완성된 문서의 서식·품질까지 자동으로 검수해 점수를 매겨주는** 문서 작성 도우미입니다.

- Windows 폴더 위치: `D:\auto_write`
- 원격 저장소: https://github.com/pds2225/auto_write
- 처음 받기: `git clone https://github.com/pds2225/auto_write.git D:\auto_write`

---

## 1. 이게 뭐예요? (비개발자용 설명)

정부지원사업·창업패키지에 지원하려면 **사업계획서**를 써야 합니다.
양식이 복잡하고, 빈칸을 채우고, 서식을 다듬는 데 시간이 오래 걸립니다.

`auto_write`는 이 일을 두 단계로 도와줍니다.

1. ✍️ **자동 작성**: 양식(HWP/DOCX)과 회사 정보·메모를 넣으면 **사업계획서 초안**을 만들어 줍니다.
2. 🧹 **자동 검수**: 완성된 문서의 서식 문제를 정리하고 **품질 점수(100점 만점)** 를 매겨, 제출 가능한 수준인지 알려줍니다.

쉽게 말하면 **"사업계획서 작성 + 교정 비서"** 입니다.

---

## 2. 처음 실행하는 법 (제일 쉬운 방법)

### 2-0. GitHub에서 프로그램 받기 (처음 한 번)

PC에 아직 `D:\auto_write` 폴더가 없으면, PowerShell 또는 명령 프롬프트에서 아래를 실행합니다.

```powershell
git clone https://github.com/pds2225/auto_write.git D:\auto_write
```

- Git이 없으면 https://git-scm.com/download/win 에서 설치합니다.
- **이미 `D:\auto_write`가 있으면 다시 clone하지 마세요.** 기존 파일을 덮어쓰지 않습니다.
- 다른 폴더에 깨끗한 복사본이 필요하면 `clone.bat D:\auto_write_copy` 또는 `py -3.11 app\clone_repo.py --dest D:\auto_write_copy` 를 씁니다.

### 2-1. 설치·실행

Windows 파일 탐색기에서 아래 파일을 **순서대로 더블클릭**하면 됩니다.

| 순서 | 더블클릭할 파일 | 하는 일 |
|------|----------------|---------|
| 1 | `D:\auto_write\setup.bat` | 필요한 프로그램 설치 (최초 1회) |
| 2 | `D:\auto_write\check_env.bat` | 제대로 설치됐는지 점검 |
| 3 | `D:\auto_write\launch.bat` | 프로그램(웹 화면) 실행 |

3번을 실행하면 잠시 후 인터넷 브라우저가 열리고 아래 주소로 접속됩니다.
브라우저가 자동으로 안 열리면 주소창에 직접 입력하세요.

```
http://127.0.0.1:8765
```

---

## 3. 화면에서 사업계획서 만드는 순서

| 순서 | 작업 | 설명 |
|------|------|------|
| 1 | 템플릿 업로드 | 사업계획서 양식(DOCX/HWP/HWPX)을 올림 |
| 2 | 템플릿 분석 | 빈칸·표·이미지 위치를 자동으로 분석 |
| 3 | 프로젝트 생성 | 분석된 양식으로 작성 프로젝트를 만듦 |
| 4 | 핵심 정보 입력 | 과제명·회사명·사업 개요·메모 입력 |
| 5 | 참고자료 업로드 | 공고문·상담메모·기존 사업계획서 등 첨부 |
| 6 | 생성 실행 | 사업계획서 초안과 DOCX 파일 생성 |
| 7 | 결과 확인 | 완성된 DOCX, 검수 리포트, 출처 목록 받기 |

---

## 4. 문서 품질 자동 검수란?

완성된 사업계획서(DOCX)를 넣으면, 사람이 일일이 보지 않아도 아래를 자동으로 처리합니다.

- 🗑️ 양식에 남아 있는 **안내문구·작성요령** 삭제
- 🧹 **글머리표·표 빈칸·불필요한 빈 줄** 정리
- ✨ **핵심 성과 문장**을 굵게/밑줄로 강조
- 🏷️ 문서 종류 자동 분류 (사업계획서·R&D계획서·보고서 등)
- 🧩 **PSST**(문제-해결-성장-팀) 구조가 빠짐없이 들어갔는지 점검
- 🖼️ 인포그래픽·도식을 어디에 넣으면 좋을지 제안
- 💯 **100점 만점 품질 점수**를 매기고 합격 여부(85점 이상 통과) 판정
- 💾 손대기 전 **원본을 자동 백업**(되돌리기 가능)

> 즉, "제출 직전 최종 교정"을 자동으로 해주는 기능입니다.

---

## 5. AI 작성 품질을 높이려면 (선택)

AI가 더 좋은 문안을 쓰게 하려면 API 키를 넣어주면 됩니다. (없어도 기본 동작은 합니다.)

1. `D:\auto_write\app\.env.example` 파일을 복사합니다.
2. 복사본 이름을 `.env` 로 바꿉니다.
3. 파일 안에 아래 중 하나를 적습니다.
   ```
   OPENAI_API_KEY=발급받은_키
   ```
   또는
   ```
   ANTHROPIC_API_KEY=발급받은_키
   ```

> ⚠️ API 키는 다른 사람에게 공유하거나 인터넷에 올리지 않습니다.

---

## 6. 잘 안 될 때 (오류 해결)

| 증상 | 해결 방법 |
|------|-----------|
| "Python을 찾을 수 없음" | Python 3.11 이상 설치 후 다시 실행 |
| `git clone` 실패 / Git 없음 | Git for Windows 설치 후 다시 실행. 기존 `D:\auto_write`는 덮어쓰지 않음 |
| 설치/패키지 오류 | `setup.bat` 다시 실행 |
| 웹페이지 접속 안 됨 | `launch.bat` 창에 뜬 오류 메시지 확인 |
| `http://127.0.0.1:8765` 안 열림 | 다른 프로그램이 같은 포트를 쓰는지 확인 |
| 템플릿 분석 실패 | HWP를 DOCX로 변환 후 다시 시도 |
| AI 문안 품질이 낮음 | `.env`에 API 키가 들어 있는지 확인 |

> 오류 메시지가 뜨면 창의 내용을 그대로 복사해서 AI에게 전달하면 원인 파악이 빠릅니다.

---

## 6.5. 문서 작업 입구 (헷갈릴 때)

| 상황 | 쓸 것 |
|------|--------|
| AI에게 "문서 도와줘" (의도 불명) | `/bizdoc` 또는 스킬 `bizdoc-hub` |
| 어디서든 채움·진단 CLI | `py -3.11 app\auto_write_hub.py env\|diagnose\|fill …` |
| 상세 라우팅표 | [`docs/BIZDOC_HUB_MAP.md`](docs/BIZDOC_HUB_MAP.md) |
| 세션 이어하기 | [`RESUME.md`](RESUME.md) |

---

## 7. 안전 규칙

- 🗂️ 기존 파일은 함부로 삭제하지 않고, 수정 전 **백업본**을 만듭니다.
- 🧯 검수는 항상 **원본을 백업한 뒤** 진행하며, 잘못되면 되돌릴 수 있습니다.
- 🔑 API 키·개인정보는 화면에 출력하거나 인터넷에 올리지 않습니다.
- ✅ 대량 이동·삭제 전에는 사용자 승인을 받습니다.

---

## 8. (개발자용) 직접 명령으로 검수 실행

```powershell
cd D:\auto_write\app
python document_quality_orchestrator.py "C:\제출\사업계획서.docx"
# 결과: results\ 폴더에 개선된 DOCX + 리포트(md/json), results\backup\ 에 원본 백업
```

자세한 내부 구조·규칙은 `CLAUDE.md`, `docs/PROJECT_REPORT.md`, `docs/PSST_CHECK_RULES.md`, `docs/DOCUMENT_QUALITY_SCORE_RULES.md` 를 참고하세요.

---

## 9. (개발자용) 프로젝트 구조 — 저장소 분리 진행 중

이력서(컨설턴트신청서)와 사업계획서 기능을 같은 저장소 내 폴더로 분리하고 있습니다.

### 현재 구조 (분리 진행 중)

```
app/
├── core/                    ← 공유 코어 모듈
│   └── docx/                ← DOCX 관련 코드 집결 (65개 파일)
│       ├── services/        ← 핵심 서비스 18개 (docx_ops, hwp_docx_convert, fill, quality, render)
│       ├── cli/             ← CLI 도구 16개 (hwp_docx, cross_form_fill, quality_ratchet 등)
│       ├── tests/           ← 테스트 27개
│       ├── document_ingest.py
│       └── docx_template.py
├── resume/                  ← 이력서 전용 (신규)
│   ├── services/            ← resume_fill_service, resume_extract, resume_form_map, hwpx_fill_coverage
│   └── cli/                 ← resume_fill
├── bizplan/                 ← 사업계획서 전용 (신규)
│   ├── services/            ← cross_form_autofill, psst_fill, quality_rules, render_service 등
│   └── cli/                 ← company_master, cross_form_fill, self_diagnose, learn_run, strip_notebooklm
├── auto_write/              ← 기존 서비스 모듈 (원본 보존, 호환성 유지)
├── resume_fill.py           ← 이력서 전용 CLI (기존 경로)
├── bizplan_autopilot.py     ← 사업계획서 전용 CLI (기존 경로)
└── tests/                   ← 기존 테스트
```

### 분리 현황 (2026-08-07 기준)

| 구분 | 파일 수 | ownership | 설명 |
|------|---------|-----------|------|
| CORE | 22 | KEEP_CORE | document_ingest, docx_ops, doc_quality_ops, hwpx_fill, hwp_docx_convert 등 |
| RESUME | 7 | MOVE_RESUME | resume_fill_service, resume_extract, hwpx_fill_coverage 등 |
| BIZPLAN | 28 | MOVE_BIZPLAN | cross_form_autofill, psst_fill, quality_rules, submittable_filler 등 |
| MIXED | 1 | MIXED_REFACTOR | cross_form_autofill (범용 유틸 추출 필요) |
| NONE | 7 | KEEP_PACKAGE_META/LEGACY | __init__.py, case scripts |

### 분리 방식

B안 — 같은 저장소 내 폴더 분리 (`app/core/`, `app/resume/`, `app/bizplan/`)
- 원본 `auto_write/`는 호환성을 위해 보존
- 새 도메인 패키지에서 `auto_write.services.*` 절대 import 사용
