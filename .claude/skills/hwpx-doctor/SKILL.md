---
name: hwpx-doctor
description: >-
  한글 파일이 안 열리거나 빈 문서로 뜰 때 써요. “hwpx 안 열려”, “한글 파일 안 열림”, “빈 문서로 열려”, “한글 문서 깨졌어”, “한글 2024로 만든 파일이 2022에서 안 열려”, “한컴계정으로 열면안되고”, “한글2022로 열어야함”, “한글 또 안열린다” 같은 말을 하면 원인을 찾아 원본은 두고 고친 사본을 만들어요.
---
# hwpx-doctor — 안 열리는 한글 파일 진단·수정

## 실행 환경 (Grok Bot에서 실행할 때)
- 이 스킬에 나오는 `D:\…`, `C:\Users\ekth3\…`, `바탕 화면\…` 경로와 `py -3.11` / `python` / `pwsh` 명령은 다솜님 Windows 노트북 기준이다. Shell·Read에 machineId `b09d5493-c6d4-4760-b6fa-a855d89774e9` 를 넣어 노트북에서 PowerShell로 실행·읽기 한다. 큰 파일이나 바이너리는 CopyToBox로 박스에 가져와 처리하고, 결과물을 노트북에 둬야 하면 CopyFromBox로 돌려놓는다. 노트북이 연결돼 있지 않으면(ListMachines로 확인) 그렇게 알리고 멈춘다.
- 원본 파일은 절대 덮어쓰지 않는다(새 파일로 저장). 삭제·이동·메일 발송·제출 같은 되돌릴 수 없는 일은 사용자가 그 자리에서 분명히 승인했을 때만 한다.
- 원문에 남아 있는 Claude Code 전용 요소(슬래시 커맨드 `/…`, `.claude/agents/*` 에이전트, `Agent(...)` 호출, `model: "opus"`, 훅, CLAUDE.md 자동주입)는 여기 없다. 슬래시 커맨드는 같은 CLI를 직접 실행하거나 노트북의 `<프로젝트>\.claude\commands\<이름>.md` 를 읽어 그 절차를 따른다. 에이전트 이름은 '단계/역할'로 읽고 직접 순서대로 수행한다(작성과 검수를 분리해야 하면 검수만 서브에이전트에 맡긴다). 에이전트 정의가 필요하면 `<프로젝트>\.claude\agents\<이름>.md` 또는 `C:\Users\ekth3\.claude\agents\<이름>.md` 를 읽는다.
- `docs/…`, `app/…` 같은 상대경로는 해당 프로젝트 폴더(예: `D:\auto_write\docs\…`) 기준이다. `.omc/wiki` 위키는 노트북 `D:\.omc\wiki` 에 있다.
- 다른 스킬 이름(예: `cross-form-submission`)은 Grok Bot 스킬 id와 같다.
- 노트북 파일이 아니라 사용자가 채팅/드라이브로 준 파일이면 박스(/workspace)에서 같은 방법(파이썬)으로 처리해도 된다. 단 한글 COM(.hwp 저장)은 노트북에서만 된다.


## 언제 쓰나
프로그램(auto_write 등)으로 만들거나 편집한 hwpx가 **한글에서 안 열리거나 빈 문서로 뜰 때.**
파일 구조(zip/XML)는 멀쩡한데 한글이 거부하는 경우, 원인은 대개 아래 둘 중 하나다.

**A. 의미 규칙 위반 (파일 내부 모순)**
- **표 격자 깨짐**(가장 흔함): 셀 주소(rowAddr/colAddr)가 물리 위치와 어긋나 겹치거나 비어 있음.
  실측(박다솜 프로필 v3~v7): 채움 스크립트가 행 추가 시 rowAddr를 안 늘려 마지막 행이 겹침.
- **ID 참조 오류**: section이 header에 없는 charPr/paraPr/style/borderFill id를 참조.
- **itemCnt 불일치**: 헤더 refList의 itemCnt가 실제 항목 수와 다름.

**B. 상위 버전 전용 속성 (파일은 멀쩡, 한글이 못 알아들음)** ← 위 검사를 다 통과했는데도 안 열리면 여기
- 한글 **2024(appVersion 13)** 가 저장한 hwpx에는 `hh:paraPr` 마다 **`textDir="AUTO"`** 가 붙는다.
  한글 **2022(appVersion 12)** 는 이 속성을 모르므로 **파일 자체를 거부**한다.
- 증상 특징: **`.hwp` 는 잘 열리는데 `.hwpx` 만 안 열린다** / 구조 검사는 전부 OK / 오류 없이 그냥 안 열림.

## ⚠ 진단 순서 — 대조군부터 (가장 중요)
안 되는 파일 하나만 파헤치면 오래 걸린다. **되는 파일과 나란히 비교**가 최단경로다(오답노트 L137).

```powershell
# 1) 되는 파일 확보 — 한글이 직접 저장한 사본, 과거 제출 완료본 등
# 2) 두 파일의 속성 집합을 diff (파이썬 두 줄)
py -3.11 -c "
import zipfile,re
def attrs(p): 
    return set(re.findall(r'\s([a-zA-Z:]+)=\"', zipfile.ZipFile(p).read('Contents/header.xml').decode('utf-8')))
a,b=attrs(r'안되는것.hwpx'),attrs(r'되는것.hwpx')
print('안되는것에만:',sorted(a-b)); print('되는것에만:',sorted(b-a))"
# 3) 후보가 나오면 전 파일 상관표(되는것 vs 안되는것 × 후보속성)로 확인 후 결론
```

버전 계보는 이 한 줄로 바로 본다(13=한글 2024 / 12=한글 2022):
```powershell
py -3.11 -c "
import zipfile,re,sys
z=zipfile.ZipFile(sys.argv[1]); v=z.read('version.xml').decode('utf-8')
h=z.read('Contents/header.xml').decode('utf-8')
print('appVersion:',re.search(r'appVersion=\"([^\"]+)\"',v).group(1),'/ textDir:',h.count('textDir'))" "문서.hwpx"
```

## 먼저 확인 (환경 vs 파일)
"안 열림"이 **파일** 문제인지 **한글 앱** 문제인지 먼저 가른다:
- 다른 한글 파일은 열리는데 이 파일만 안 열림 → **파일 문제** → 이 스킬로 진단·수정.
- 한글 자체가 무응답/모든 파일 안 열림(COM Version 공백 등) → **한글 앱 문제** → PC 재부팅/재활성화 안내.
- **`.hwp` 는 열리고 `.hwpx` 만 안 열림** → 위 **B(상위 버전 속성)** 를 1순위로 의심.
  파일 연결이 어느 한글로 되어 있는지도 함께 확인:
  `reg query "HKCU\Software\...\FileExts\.hwpx\UserChoice"` (ProgID 끝 `120`=2022 / `130`=2024)

## 실행 (PowerShell)
```powershell
cd D:\auto_write\app
# 1) 진단 — 무엇이 문제인지 (종료코드 0=정상 / 2=결함)
python hwpx_doctor.py diagnose "C:\경로\문서.hwpx"
# 2) 수정 — 깨진 표 격자 자동 교정한 수정본 생성 (원본 보존)
python hwpx_doctor.py repair "C:\경로\문서.hwpx"            # → 문서_수정.hwpx
python hwpx_doctor.py repair "문서.hwpx" -o "고친것.hwpx"
```
> ⚠ 이 CLI 는 **A(의미 규칙)만** 본다. "정상"이 나와도 **B는 미검사**다 —
> 사용자에게 보고할 땐 반드시 **검사 범위를 밝힌다**("격자·ID·itemCnt 3항목 통과, 그 외 미검사").
> "이제 열립니다" 같은 단정은 **실제로 열어본 뒤에만** 쓴다(오답노트 L136).

### B 교정 — 한글 2022 호환본 만들기
`textDir` 속성만 걷어내고 버전 표기를 12로 되돌린다. **내용·서식은 한 글자도 안 바뀐다.**
```python
import zipfile, re, os
def to_hangul2022(src, dst):
    """한글 2024 전용 속성을 제거해 한글 2022 에서 열리는 사본을 만든다(원본 보존)."""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError("원본 덮어쓰기 금지")
    zin = zipfile.ZipFile(src)
    with zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "Contents/header.xml":
                data = re.sub(r'\s+textDir="[^"]*"', "", data.decode("utf-8")).encode("utf-8")
            elif info.filename == "version.xml":
                data = re.sub(r'appVersion="13,[^"]*"',
                              'appVersion="12, 0, 0, 893 WIN32LEWindows_10"',
                              data.decode("utf-8")).encode("utf-8")
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type   # mimetype 은 반드시 비압축(0) 유지
            zout.writestr(zi, data)
```
만든 뒤 `hwpx_doctor.py diagnose` 로 구조가 여전히 정상인지 확인하고, **사용자가 실제로 열어보게 한다.**

## 동작 원리 (엔진)
- 진단·교정 엔진 = `app/auto_write/services/hwpx_layout_fix.py`
  - `check_hwpx_semantics(path)` — itemCnt·ID참조·표격자 검사(읽기 전용).
  - `validate_table_grid(tbl)` — 표 격자 타일링 검증(P0).
  - `repair_table_grid(tbl)` / `repair_all_table_grids(section)` — 깨진 표 자동 재주소화.
- **자동 예방**: `finalize_layout_hwpx(..., repair_grid=True)`(기본)에 배선돼, hwpx_submit 등
  제출·마감 경로로 나가는 모든 hwpx가 저장 직전 격자 자동교정된다 → 깨진 파일이 애초에 안 나감.

## 안전 원칙 (불변)
- **원본 미수정**: 항상 새 파일(`_수정`·`_2022호환`)로 저장. 출력=입력이면 거부.
- **병합 표 보호**: rowSpan/colSpan>1 병합이 있는 표는 자동 교정하지 않는다(정상 병합을
  깨뜨릴 위험 → 사람 확인). 1×1 셀 표의 명백한 주소 오류만 고친다.
- **멱등**: 이미 정상인 문서엔 아무것도 바꾸지 않는다.
- **mimetype 보존**: 재압축 시 `mimetype` 은 반드시 **첫 항목·비압축(compress_type=0)**.
- 자동 교정으로 못 고치는 결함(ID참조·itemCnt·병합 표)은 정직하게 보고하고 수동 확인 안내.

## 이 PC 환경 (되돌리지 말 것)
- 한글 **2022 · 2024 둘 다 설치**. 편집은 **2022**(2024는 읽기전용 라이선스).
- `.hwp` / `.hwpx` 기본 연결 프로그램 = **2022**(`Hwp.Document(.hwpx).120`) — 바꾸지 말 것.
- 그래서 **2024로 만들어진 hwpx 는 이 PC에서 못 연다** → 위 B 교정이 상시 필요하다.
