---
name: docx-hwp-conversion
description: >-
  한글 파일과 워드 파일을 서로 바꿀 때 써요. “hwp를 docx로”, “docx를 hwp로”, “한글 파일 변환”, “워드로 변환”, “제출용 hwp로 바꿔줘”, “변환 안 됨”, “변환 다시 해줘” 같은 말을 하면 표·서식·그림을 최대한 살려 바꾸고 빠진 부분을 솔직히 알려줘요. 파일이 안 열리는 문제는 ‘안 열리는 한글 파일 고치기’예요.
---
# docx-hwp-conversion — DOCX ↔ HWP/HWPX 양방향 변환

## 실행 환경 (Grok Bot에서 실행할 때)
- 이 스킬에 나오는 `D:\…`, `C:\Users\ekth3\…`, `바탕 화면\…` 경로와 `py -3.11` / `python` / `pwsh` 명령은 다솜님 Windows 노트북 기준이다. Shell·Read에 machineId `b09d5493-c6d4-4760-b6fa-a855d89774e9` 를 넣어 노트북에서 PowerShell로 실행·읽기 한다. 큰 파일이나 바이너리는 CopyToBox로 박스에 가져와 처리하고, 결과물을 노트북에 둬야 하면 CopyFromBox로 돌려놓는다. 노트북이 연결돼 있지 않으면(ListMachines로 확인) 그렇게 알리고 멈춘다.
- 원본 파일은 절대 덮어쓰지 않는다(새 파일로 저장). 삭제·이동·메일 발송·제출 같은 되돌릴 수 없는 일은 사용자가 그 자리에서 분명히 승인했을 때만 한다.
- 원문에 남아 있는 Codex 전용 요소(슬래시 커맨드 `/…`, `.Codex/agents/*` 에이전트, `Agent(...)` 호출, `model: "opus"`, 훅, AGENTS.md 자동주입)는 여기 없다. 슬래시 커맨드는 같은 CLI를 직접 실행하거나 노트북의 `<프로젝트>\.Codex\commands\<이름>.md` 를 읽어 그 절차를 따른다. 에이전트 이름은 '단계/역할'로 읽고 직접 순서대로 수행한다(작성과 검수를 분리해야 하면 검수만 서브에이전트에 맡긴다). 에이전트 정의가 필요하면 `<프로젝트>\.Codex\agents\<이름>.md` 또는 `C:\Users\ekth3\.Codex\agents\<이름>.md` 를 읽는다.
- `docs/…`, `app/…` 같은 상대경로는 해당 프로젝트 폴더(예: `D:\auto_write\docs\…`) 기준이다. `.omc/wiki` 위키는 노트북 `D:\.omc\wiki` 에 있다.
- 다른 스킬 이름(예: `cross-form-submission`)은 Grok Bot 스킬 id와 같다.


> **평생개발목표(북극성): DOCX↔HWP 양방향 변환 일치도 100%.**
> 한 번에 달성하는 게 아니라, 측정 하네스 `conversion_fidelity` 로 baseline%를 내고
> **측정 → 개선 루프**로 끌어올린다. 변환 손실은 항상 **수치로 정직 보고**한다 —
> "완벽/100%"를 단정하지 말 것(거짓 완료 금지). 측정값이 곧 진실이다.

## 무엇을 하나

기존 변환 자산(`app/hwp_docx.py` CLI, `app/auto_write/services/hwp_docx_convert.py`)을
래핑해 한 줄 명령으로 양방향 변환한다. 새 로직을 만들지 말고 **이 CLI를 호출**한다.

- **HWP/HWPX → DOCX**: 정부양식(보통 HWP)을 작업 가능한 DOCX로 연다.
- **DOCX → HWP/HWPX**: 작업·완성된 DOCX를 제출용 한글 파일로 되돌린다.

## 실행 (PowerShell)

```powershell
cd D:\auto_write\app
python hwp_docx.py "양식.hwp"                 # → 양식.docx (HWP/HWPX → DOCX)
python hwp_docx.py "결과.docx" -o "제출.hwp"   # → 제출.hwp (DOCX → HWP, 한글 COM 필요)
python hwp_docx.py "양식.hwp" -o "분석용.docx" # 출력 경로 직접 지정
python hwp_docx.py "양식.hwp" --no-com         # 한글 COM 건너뛰고 구조 변환만(HWP→DOCX 전용)
```

**방향은 확장자로 자동 인식**한다: `.hwp`/`.hwpx` → `.docx`, `.docx` → `.hwp`.
출력을 안 주면 입력과 같은 폴더에 반대 확장자로 만든다.

## 변환 방식 — 3단 폴백 (HWP/HWPX → DOCX)

위에서부터 성공할 때까지 자동으로 내려간다. **품질은 위쪽이 가장 충실**하다.

| 순위 | method | 무엇을 쓰나 | 보존 수준 | 한계 |
|------|--------|------------|-----------|------|
| 1 | `hancom_com` | 한글(Hancom Office) COM 자동화 | 서식·표·이미지 **최충실** | 한글 설치 필요. 백그라운드/서비스 세션에서는 GUI COM 서버가 안 떠 실패 가능 → 자동으로 2단계로 |
| 2 | `unhwp` / `hwpx_xml` | `document_ingest` 구조 변환 재사용 | 문단·**표(병합 포함) 복원** | 글꼴 등 세부 서식 제한 |
| 3 | `prvtext` | HWP 미리보기 텍스트(PrvText) | **텍스트만** | 표 소실·본문 일부 누락 가능 |

**Why 폴백인가:** 가장 정확한 한글 COM은 PC·설치·대화형 세션에 종속된다. 그게
안 되는 환경(CI·백그라운드)에서도 최소한 구조/텍스트는 건지도록 자동으로 한 단계씩
내려간다. 어떤 단계로 변환됐는지는 `ConvertReport.method` 로 항상 확인된다.

## DOCX → HWP/HWPX 는 한글 COM 대화형 PC 전용

DOCX→HWP 자동 경로는 **한글 COM 하나뿐**이다(구조 역변환 폴백 없음).

- **한글이 설치된, 사용자가 직접 연 PowerShell**에서 실행해야 한다.
  백그라운드 세션에서는 한글 GUI가 안 떠 실패할 수 있다.
- 한글 미설치/COM 미등록·실패 시 **예외를 던지지 않고** `ok=False` 리포트 +
  "대화형 PowerShell에서 다시 실행하고 한글 '보안 승인' 대화상자가 뜨면 '허용'을 누르세요"
  같은 **사람이 할 일 안내**를 `notes` 에 담는다(조용히 실패하지 않는다).

## 안전 (불변)

- **원본 절대 미수정.** 출력 경로 = 입력 경로면 `ValueError`(원본 덮어쓰기 금지).
  같은 폴더·반대 확장자 기본값이라 보통 충돌하지 않지만, `-o` 로 입력과 같은 경로를
  주면 막힌다.
- **AI 호출 없음** — 동일 입력, 동일 결과(COM 가용성에 따른 `method` 차이만 존재).
- Secret/키 출력·하드코딩 금지.

## 결과 보고 — ConvertReport 필드

CLI는 변환 결과를 `ConvertReport` 로 돌려준다. 비개발자에게는 "됐다/안 됐다 + 어떤
방식으로"만 전하면 된다.

| 필드 | 뜻 |
|------|-----|
| `direction` | `"hwp->docx"` 또는 `"docx->hwp"` (변환 방향) |
| `method` | 실제로 성공한 방식 (`hancom_com`/`unhwp`/`hwpx_xml`/`prvtext`/공백) |
| `ok` | 성공 여부(`True`/`False`) |
| `output` | 만들어진 파일 경로 |
| `notes` | 폴백·실패·사람이 할 일 안내 등 주의사항 목록 |

## 일치도는 측정하고 정직하게 보고한다

변환이 "끝났다"와 "손실 없이 됐다"는 다르다. 변환 손실(단락·표·셀·이미지·텍스트
일치율)은 측정 하네스 **`conversion_fidelity`** 로 재고, **baseline% + 100% 미달 갭**을
함께 보고한다. 구조 일치도 100%여도 폰트·레이아웃 등 시각 서식은 별개임을 명시한다.
"완벽" 대신 항상 **측정값**으로 말한다.

## 금지

원본 덮어쓰기 · 변환 손실을 측정 없이 "완벽/100%"로 단정 · COM 실패를 조용히 성공 보고 ·
Secret/키 출력 · `hwp_docx.py` 외 새 변환 로직 중복 구현.
