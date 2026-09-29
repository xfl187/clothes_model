[CmdletBinding()]
param(
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$envFile = Join-Path $repoRoot '.env'

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing $envFile. Create it from the documented development settings first."
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([^#][^=]*)=(.*)$') {
        $settings[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$required = @(
    'CLOTHES_MODEL_BACKEND_PORT',
    'CLOTHES_MODEL_SCHEDULER_ENABLED',
    'CLOTHES_MODEL_ENCRYPTION_MASTER_KEY_FILE_SOURCE'
)
foreach ($name in $required) {
    if ([string]::IsNullOrWhiteSpace($settings[$name])) {
        throw "Missing $name in $envFile."
    }
}

if ($settings['CLOTHES_MODEL_SCHEDULER_ENABLED'] -ne 'true') {
    throw 'Development job execution requires CLOTHES_MODEL_SCHEDULER_ENABLED=true.'
}

$keyPath = $settings['CLOTHES_MODEL_ENCRYPTION_MASTER_KEY_FILE_SOURCE']
if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
    throw "Encryption master-key file does not exist: $keyPath"
}

$composeArgs = @(
    'compose',
    '--env-file', $envFile,
    '-f', $composeFile,
    '--profile', 'development',
    'up', '-d'
)
if ($Build) {
    $composeArgs += '--build'
}
$composeArgs += 'backend'

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE."
}

$healthUrl = "http://127.0.0.1:$($settings['CLOTHES_MODEL_BACKEND_PORT'])/health/ready"
$deadline = (Get-Date).AddSeconds(60)
do {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
        if ($health.status -eq 'ok' -and $health.checks.scheduler -eq 'owned') {
            Write-Host "Development Backend is ready at $healthUrl (scheduler: owned)."
            exit 0
        }
    }
    catch {
        # The container may still be starting; retry until the deadline.
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

throw "Development Backend did not become ready with scheduler ownership within 60 seconds: $healthUrl"
