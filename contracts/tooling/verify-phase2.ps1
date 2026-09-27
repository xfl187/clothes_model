$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

function Invoke-Checked {
    param([scriptblock]$Command, [string]$Message)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw $Message }
}

Write-Host 'Phase 2: contract boundaries'
& (Join-Path $PSScriptRoot 'verify-generated.ps1')
& (Join-Path $PSScriptRoot 'verify-phase2-boundaries.ps1')

Write-Host 'Phase 2: backend security, migration, upload, and asset suites'
Push-Location (Join-Path $root 'backend')
try {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Invoke-Checked { uv run ruff check . } 'Backend lint failed.'
        Invoke-Checked { uv run pyright } 'Backend type check failed.'
        Invoke-Checked { uv run pytest -q --basetemp=.phase2-pytest -p no:cacheprovider } 'Backend tests failed.'
    } else {
        Invoke-Checked { & .\.venv\Scripts\ruff.exe check . } 'Backend lint failed.'
        Invoke-Checked { & .\.venv\Scripts\pyright.exe } 'Backend type check failed.'
        Invoke-Checked { & .\.venv\Scripts\pytest.exe -q --basetemp=.phase2-pytest -p no:cacheprovider } 'Backend tests failed.'
    }
} finally { Pop-Location }

Write-Host 'Phase 2: Web Admin session shell'
Push-Location $root
try {
    Invoke-Checked { corepack pnpm@10.34.5 web:lint } 'Web lint failed.'
    Invoke-Checked { corepack pnpm@10.34.5 web:typecheck } 'Web type check failed.'
    Invoke-Checked { corepack pnpm@10.34.5 web:test } 'Web tests failed.'
    Invoke-Checked { corepack pnpm@10.34.5 web:build } 'Web build failed.'
    Invoke-Checked { corepack pnpm@10.34.5 --filter '@clothes-model/web-admin' check:bundle } 'Web bundle credential scan failed.'
} finally { Pop-Location }

Write-Host 'Phase 2: Android connection and import recovery'
Push-Location (Join-Path $root 'android')
try {
    Invoke-Checked { & .\gradlew.bat --no-daemon :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:assembleDebugAndroidTest :app:assembleRelease } 'Android Phase 2 verification failed.'
} finally { Pop-Location }

$scanTargets = @(
    (Join-Path $root 'web-admin\dist'),
    (Join-Path $root 'backend\artifacts'),
    (Join-Path $root 'backend\reports')
) | Where-Object { Test-Path $_ }
if ($scanTargets) {
    $leaks = Get-ChildItem -LiteralPath $scanTargets -File -Recurse -ErrorAction SilentlyContinue |
        Select-String -Pattern 'cm\.(app|admin)\.[A-Za-z0-9_-]{16}\.[A-Za-z0-9_-]{43}'
    if ($leaks) { throw 'Credential-shaped value found in generated reports or bundles.' }
}

Write-Host 'Phase 2 verification passed.'
