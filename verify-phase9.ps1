[CmdletBinding()]
param(
    [switch]$SkipContract,
    [switch]$SkipAndroid
)

# Deterministic Phase 9 V1.1 gate. Proves that ComfyUI, Workflow, and layered
# outfit surfaces remain available in addition to the V1 boundaries.
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path $PSScriptRoot).Path
$backendRoot = Join-Path $repositoryRoot 'backend'
$androidRoot = Join-Path $repositoryRoot 'android'
$hadProductRelease = Test-Path Env:CLOTHES_MODEL_PRODUCT_RELEASE
$previousProductRelease = $env:CLOTHES_MODEL_PRODUCT_RELEASE
$env:CLOTHES_MODEL_PRODUCT_RELEASE = 'v1_1'

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

    Write-Output '==> Backend lint, types, and tests (V1 regression + V1.1 outfits)'
    Push-Location $backendRoot
    try {
        & (Join-Path $backendRoot '.venv\Scripts\ruff.exe') check .
        Assert-LastExitCode 'Backend Ruff'
        & (Join-Path $backendRoot '.venv\Scripts\pyright.exe')
        Assert-LastExitCode 'Backend Pyright'
        $focusedPytestBase = Join-Path ([System.IO.Path]::GetTempPath()) (
            'clothes-model-phase9-boundary-' + [System.Guid]::NewGuid().ToString('N')
        )
        & (Join-Path $backendRoot '.venv\Scripts\python.exe') -m pytest -q --basetemp $focusedPytestBase `
            'tests/test_release_track_boundary.py::test_v1_1_preserves_comfyui_availability' `
            'tests/test_workflow_lifecycle.py' `
            'tests/test_comfy_node_http.py' `
            'tests/test_outfits_http.py' `
            'tests/test_outfits_layers.py'
        Assert-LastExitCode 'V1.1 release boundary'
        $pytestBase = Join-Path ([System.IO.Path]::GetTempPath()) (
            'clothes-model-phase9-pytest-' + [System.Guid]::NewGuid().ToString('N')
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
    if ($hadProductRelease) {
        $env:CLOTHES_MODEL_PRODUCT_RELEASE = $previousProductRelease
    }
    else {
        Remove-Item Env:CLOTHES_MODEL_PRODUCT_RELEASE -ErrorAction SilentlyContinue
    }
}

Write-Output 'PHASE 9 V1.1 LAYERED OUTFIT GATE PASSED'
Write-Output 'Manual release prerequisite: credentialed AutoDL/ComfyUI acceptance (docs/runbooks/node-replacement.md).'
