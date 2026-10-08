[CmdletBinding()]
param(
    [switch]$SkipContract,
    [switch]$SkipAndroid
)

# Deterministic Phase 8 V1 release gate. Aggregates every quality boundary and
# proves that V1 exposes only direct-model generation surfaces.
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path $PSScriptRoot).Path
$backendRoot = Join-Path $repositoryRoot 'backend'
$hadProductRelease = Test-Path Env:CLOTHES_MODEL_PRODUCT_RELEASE
$previousProductRelease = $env:CLOTHES_MODEL_PRODUCT_RELEASE
$env:CLOTHES_MODEL_PRODUCT_RELEASE = 'v1'

function Assert-LastExitCode([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed with exit code $LASTEXITCODE." }
}

Push-Location $repositoryRoot
try {
    if (-not $SkipContract) {
        Write-Output '==> Contract generation and boundaries'
        & pwsh -NoProfile -File (Join-Path $repositoryRoot 'contracts\tooling\verify-generated.ps1')
        Assert-LastExitCode 'Generated contract verification'
        & pwsh -NoProfile -File (Join-Path $repositoryRoot 'contracts\tooling\verify-contract.ps1')
        Assert-LastExitCode 'Contract verification'
    }
    else {
        Write-Output '==> Contract generation and boundaries skipped (-SkipContract)'
    }

    Write-Output '==> Backend lint, types, and tests'
    Push-Location $backendRoot
    try {
        & (Join-Path $backendRoot '.venv\Scripts\ruff.exe') check .
        Assert-LastExitCode 'Backend Ruff'
        & (Join-Path $backendRoot '.venv\Scripts\pyright.exe')
        Assert-LastExitCode 'Backend Pyright'
        $focusedPytestBase = Join-Path ([System.IO.Path]::GetTempPath()) (
            'clothes-model-phase8-boundary-' + [System.Guid]::NewGuid().ToString('N')
        )
        & (Join-Path $backendRoot '.venv\Scripts\python.exe') -m pytest -q --basetemp $focusedPytestBase `
            'tests/test_release_track_boundary.py::test_v1_hides_and_rejects_v1_1_surfaces' `
            'tests/test_jobs_http.py::test_mask_job_requires_provider_capability'
        Assert-LastExitCode 'V1 release boundary'
        $pytestBase = Join-Path ([System.IO.Path]::GetTempPath()) (
            'clothes-model-phase8-pytest-' + [System.Guid]::NewGuid().ToString('N')
        )
        & (Join-Path $backendRoot '.venv\Scripts\python.exe') -m pytest -q --basetemp $pytestBase
        Assert-LastExitCode 'Backend pytest'
    }
    finally {
        Pop-Location
    }

    Write-Output '==> Web Admin'
    & pwsh -NoProfile -File (Join-Path $repositoryRoot 'web-admin\verify-phase7.ps1') -SkipContract
    Assert-LastExitCode 'Web Admin gate'

    Write-Output '==> Backup and restore'
    & pwsh -NoProfile -File (Join-Path $repositoryRoot 'infra\verify-backup-restore.ps1')
    Assert-LastExitCode 'Backup/restore verification'

    if (-not $SkipAndroid) {
        Write-Output '==> Android hardening'
        & pwsh -NoProfile -File (Join-Path $repositoryRoot 'android\verify-phase8.ps1')
        Assert-LastExitCode 'Android hardening gate'
    }
    else {
        Write-Output '==> Android hardening skipped (-SkipAndroid)'
    }
}
finally {
    Pop-Location
    if ($hadProductRelease) {
        $env:CLOTHES_MODEL_PRODUCT_RELEASE = $previousProductRelease
    }
    else {
        Remove-Item Env:CLOTHES_MODEL_PRODUCT_RELEASE -ErrorAction SilentlyContinue
    }
}

Write-Output 'PHASE 8 V1 RELEASE GATE PASSED'
Write-Output 'Credentialed AutoDL/ComfyUI acceptance belongs to the V1.1 release gate.'
