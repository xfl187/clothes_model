[CmdletBinding()]
param(
    [switch]$SkipAndroid
)

# Deterministic Phase 8 V1 release gate. Aggregates every quality boundary.
# The real credentialed AutoDL/Comfy acceptance remains a documented manual
# release prerequisite and is not executed here.
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path $PSScriptRoot).Path
$backendRoot = Join-Path $repositoryRoot 'backend'

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

    Write-Output '==> Backend lint, types, and tests'
    Push-Location $backendRoot
    try {
        & (Join-Path $backendRoot '.venv\Scripts\ruff.exe') check .
        Assert-LastExitCode 'Backend Ruff'
        & (Join-Path $backendRoot '.venv\Scripts\pyright.exe')
        Assert-LastExitCode 'Backend Pyright'
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
}

Write-Output 'PHASE 8 V1 RELEASE GATE PASSED'
Write-Output 'Manual release prerequisite: real credentialed AutoDL/Comfy acceptance (docs/runbooks/node-replacement.md).'
