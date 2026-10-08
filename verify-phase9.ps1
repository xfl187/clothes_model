[CmdletBinding()]
param(
    [switch]$SkipAndroid
)

# Deterministic Phase 9 V1.1 layered-outfit gate. Reuses the V1 contract/Backend
# boundaries and adds the outfit-focused Backend tests plus the Android build.
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path $PSScriptRoot).Path
$backendRoot = Join-Path $repositoryRoot 'backend'
$androidRoot = Join-Path $repositoryRoot 'android'

function Assert-LastExitCode([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed with exit code $LASTEXITCODE." }
}

Push-Location $repositoryRoot
try {
    Write-Output '==> Contract generation and boundaries'
    & pwsh -NoProfile -File (Join-Path $repositoryRoot 'contracts\tooling\verify-generated.ps1')
    Assert-LastExitCode 'Generated contract verification'
    & pwsh -NoProfile -File (Join-Path $repositoryRoot 'contracts\tooling\verify-contract.ps1')
    Assert-LastExitCode 'Contract verification'

    Write-Output '==> Backend lint, types, and tests (V1 regression + V1.1 outfits)'
    Push-Location $backendRoot
    try {
        & (Join-Path $backendRoot '.venv\Scripts\ruff.exe') check .
        Assert-LastExitCode 'Backend Ruff'
        & (Join-Path $backendRoot '.venv\Scripts\pyright.exe')
        Assert-LastExitCode 'Backend Pyright'
        $pytestBase = Join-Path ([System.IO.Path]::GetTempPath()) (
            'clothes-model-phase9-pytest-' + [System.Guid]::NewGuid().ToString('N')
        )
        & (Join-Path $backendRoot '.venv\Scripts\python.exe') -m pytest -q --basetemp $pytestBase
        Assert-LastExitCode 'Backend pytest'
    }
    finally {
        Pop-Location
    }

    if (-not $SkipAndroid) {
        Write-Output '==> Android build, unit tests, and lint'
        & (Join-Path $androidRoot 'gradlew.bat') '-p' $androidRoot '--no-daemon' '--console=plain' `
            ':app:assembleDebug' ':app:testDebugUnitTest' ':app:lintDebug'
        Assert-LastExitCode 'Android build and unit tests'
    }
    else {
        Write-Output '==> Android skipped (-SkipAndroid)'
    }
}
finally {
    Pop-Location
}

Write-Output 'PHASE 9 V1.1 LAYERED OUTFIT GATE PASSED'
