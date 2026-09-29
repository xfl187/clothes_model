[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$envFile = Join-Path $repoRoot '.env'

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing $envFile. The same local configuration used to start the Backend is required."
}

& docker compose --env-file $envFile -f $composeFile --profile development stop backend
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed with exit code $LASTEXITCODE."
}

$runningContainer = & docker compose --env-file $envFile -f $composeFile `
    --profile development ps --status running --quiet backend
if ($LASTEXITCODE -ne 0) {
    throw "Unable to verify Backend state; Docker Compose exited with code $LASTEXITCODE."
}
if ($runningContainer) {
    throw 'Development Backend is still running after the stop command.'
}

Write-Host 'Development Backend is stopped. Database, assets, credentials, and Docker volumes were preserved.'
