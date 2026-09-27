param([switch]$Credentialed)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'

Push-Location $backend
try {
    & .\.venv\Scripts\ruff.exe check src tests scripts
    if ($LASTEXITCODE -ne 0) { throw 'Backend lint failed.' }
    & .\.venv\Scripts\pyright.exe
    if ($LASTEXITCODE -ne 0) { throw 'Backend type check failed.' }
    & .\.venv\Scripts\pytest.exe `
        tests/test_provider_contract.py `
        tests/test_volcengine_ark_adapter.py `
        tests/test_provider_config_http.py `
        tests/test_scheduler_execution.py `
        -q --basetemp .pytest-tmp-phase4-verify -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'Deterministic Phase 4 Provider tests failed.' }
    if ($Credentialed) {
        if ([string]::IsNullOrWhiteSpace($env:CLOTHES_MODEL_PHASE4_ARK_API_KEY)) {
            throw 'Set CLOTHES_MODEL_PHASE4_ARK_API_KEY through a secure environment secret.'
        }
        & .\.venv\Scripts\python.exe scripts/credentialed_seedream_smoke.py
        if ($LASTEXITCODE -ne 0) { throw 'Credentialed Seedream smoke failed.' }
    }
} finally {
    Pop-Location
}

$sensitivePatterns = @(
    ('AK' + 'LT'),
    ('Authorization: Bearer ' + 'ey'),
    ('data:image/png;base64,' + 'iVBOR')
)
$trackedFiles = & git -C $root ls-files
foreach ($relativePath in $trackedFiles) {
    $path = Join-Path $root $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
    $content = Get-Content -LiteralPath $path -Raw -ErrorAction SilentlyContinue
    foreach ($pattern in $sensitivePatterns) {
        if ($content -and $content.Contains($pattern)) {
            throw "Sensitive marker '$pattern' found in tracked file $relativePath"
        }
    }
}

Write-Host "Phase 4 deterministic verification passed (credentialed=$Credentialed)."
