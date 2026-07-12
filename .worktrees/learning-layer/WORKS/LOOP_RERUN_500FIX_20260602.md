# 실제사용승인루프 재실행 (500 오류 수정 후)

- 일시: 2026-06-02
- 트리거: `루프돌려` + Internal Server Error 수정 반영
- 실행 폴더: `D:\auto_write` (실행) / `D:\auto_write\autowrite_repo` (GitHub)

## 이번에 한 일 (Loop 4 재검증 + Loop 5 준비)

| 단계 | 상태 | 내용 |
|------|------|------|
| 500 수정 | 완료 | DOCX 없음 → 한글 오류·리다이렉트, `template_source.docx` 고정 |
| autowrite_repo 동기화 | 완료 | 동일 패치를 `autowrite_repo\app\`에 반영 |
| pytest | **로컬 필요** | 에이전트 shell bkit 훅 차단 |
| 실사용 E2E | **로컬 필요** | 템플릿 DOCX 재업로드 + 새 프로젝트 |

## 0순위 문제 (현재)

- **증상:** 계획서 생성 시 Internal Server Error
- **원인:** `tpl_0731c59c15b5` 등 템플릿 폴더에 **원본 DOCX 없음** (profile JSON만 존재)
- **수정:** 500 대신 프로젝트 화면 상단 빨간 안내 문구

## 로컬 검증 명령 (필수)

```powershell
cd D:\auto_write\app
$env:PYTHONPATH = "D:\auto_write\app"
& "$env:LocalAppData\Programs\Python\Python311\python.exe" -m pytest tests\test_psst_mapping.py tests\test_loop4_sample_generate.py -q --tb=short
```

## 실사용 3단계 (필수)

1. `cd D:\auto_write` → `.\launch.bat`
2. 홈에서 **양식 DOCX 재업로드** → **새 프로젝트** 생성 (기존 `prj_38e92c617752`는 DOCX 고정 없음)
3. PDF·PSST 옵션으로 **계획서 생성 실행** → `D:\auto_write\results\{프로젝트ID}\` 확인

## GitHub (Loop 5)

```powershell
cd D:\auto_write\autowrite_repo
git status
git add app\auto_write\main.py app\auto_write\services\project_service.py app\auto_write\services\render_service.py app\auto_write\templates\project_detail.html app\tests\test_psst_mapping.py
git commit -m "fix: missing template DOCX shows Korean error instead of HTTP 500"
git push -u origin HEAD
```

## 다음 승인 문구

- `승인: GitHub 반영` — 위 커밋·PR (사용자가 push)
- pytest 결과 붙여넣기 — 실패 시 `test-fix`
- `중지: 로컬만 유지`
