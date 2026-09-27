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
        tests/test_workflow_artifacts.py `
        tests/test_workflow_lifecycle.py `
        tests/test_comfy_node_http.py `
        tests/test_comfyui_adapter.py `
        tests/test_job_workflow_locking.py `
        tests/test_scheduler_recovery.py `
        -q --basetemp .pytest-tmp-phase5-verify -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'Deterministic Phase 5 Comfy/Workflow tests failed.' }
    if ($Credentialed) {
        if ([string]::IsNullOrWhiteSpace($env:CLOTHES_MODEL_PHASE5_COMFY_ENDPOINT)) {
            throw 'Set CLOTHES_MODEL_PHASE5_COMFY_ENDPOINT through a secure environment secret.'
        }
        throw 'Credentialed Phase 5 operator acceptance is manual until the AutoDL node is provisioned.'
    }
} finally {
    Pop-Location
}

$sensitivePatterns = @(
    ('AK' + 'LT'),
    ('Authorization: Bearer ' + 'ey'),
    ('data:image/png;base64,' + 'iVBOR'),
    ('comfy_node_credential' + '_secret')
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

Write-Host "Phase 5 deterministic verification passed (credentialed=$Credentialed)."
