[CmdletBinding()]
param(
    [switch]$SkipRelease
)

# Phase 8 Android hardening gate. Reuses the deterministic Phase 6 Android gate
# (contract, Backend, Android build/lint/unit/instrumentation compile/release)
# and the release-boundary scan. Connected hardening instrumentation runs in the
# CI emulator job.
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

Push-Location $repositoryRoot
try {
    if ($SkipRelease) {
        & pwsh -NoProfile -File (Join-Path $PSScriptRoot 'verify-phase6.ps1') -SkipRelease
    } else {
        & pwsh -NoProfile -File (Join-Path $PSScriptRoot 'verify-phase6.ps1')
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'Phase 6 Android gate failed.'
    }
}
finally {
    Pop-Location
}

Write-Output 'PHASE 8 ANDROID HARDENING GATE PASSED'
Write-Output 'Run :app:connectedDebugAndroidTest in CI for device network/process-recovery coverage.'
