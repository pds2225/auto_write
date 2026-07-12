# 강조 로직 튜닝 변경만 커밋 (bkit/omc 런타임·개인정보 제외)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location 'D:\auto_write'

Write-Host '== git status ==' -ForegroundColor Cyan
git status -sb

$files = @(
    'app/auto_write/services/doc_quality_ops.py',
    '.claude/skills/content-emphasis.md',
    'RESUME.md'
)

foreach ($f in $files) {
    if (-not (Test-Path $f)) {
        throw "Missing file: $f"
    }
    git add $f
}

$msg = @'
fix: 과잉 강조 방지 — 비율 기반 emphasize_key_sentences 튜닝

원본 Bold 단락을 예산에서 차감해 멱등성을 확보하고, 숫자 필수·8자 이상 필터로
오탐을 줄였다. 미래큐러스 실검증: 강조 40.6%→29.3%, 총점 49.2→54.2, pytest 72 passed.
'@

git commit -m $msg
Write-Host "`n== done ==" -ForegroundColor Green
git log -1 --oneline
git status -sb
