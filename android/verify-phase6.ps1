[CmdletBinding()]
param(
    [switch]$SkipRelease
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$androidRoot = Join-Path $repositoryRoot 'android'
$backendRoot = Join-Path $repositoryRoot 'backend'
$runningOnWindows = $env:OS -eq 'Windows_NT'
$gradle = Join-Path $androidRoot 'gradlew.bat'

function Assert-LastExitCode([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

function Invoke-BackendTool([string]$Name, [string[]]$Arguments) {
    $uv = if ($env:CLOTHES_MODEL_UV) {
        $env:CLOTHES_MODEL_UV
    } else {
        (Get-Command uv -ErrorAction SilentlyContinue)?.Source
    }
    if ($null -ne $uv -and $uv -ne '') {
        & $uv 'run' '--project' $backendRoot $Name @Arguments
    } else {
        $extension = if ($runningOnWindows) { '.exe' } else { '' }
        $command = Join-Path $backendRoot ('.venv\Scripts\' + $Name + $extension)
        if (-not (Test-Path -LiteralPath $command)) {
            throw "Missing Backend tool '$Name'. Install the locked Backend environment or set CLOTHES_MODEL_UV."
        }
        & $command @Arguments
    }
    Assert-LastExitCode "Backend tool '$Name'"
}

& (Join-Path $repositoryRoot 'contracts\tooling\verify-generated.ps1')
Assert-LastExitCode 'Generated contract verification'

& (Join-Path $repositoryRoot 'contracts\tooling\verify-contract.ps1')
Assert-LastExitCode 'Contract boundary verification'

Push-Location $backendRoot
try {
    Invoke-BackendTool 'ruff' @('check', '.')
    Invoke-BackendTool 'pyright' @()
    $pytestBase = Join-Path ([System.IO.Path]::GetTempPath()) (
        'clothes-model-phase6-pytest-' + [System.Guid]::NewGuid().ToString('N')
    )
    Invoke-BackendTool 'pytest' @('-q', '--basetemp', $pytestBase)
}
finally {
    Pop-Location
}

$gradleTasks = @(
    ':app:assembleDebug',
    ':app:lintDebug',
    ':app:testDebugUnitTest',
    ':app:assembleDebugAndroidTest'
)
if (-not $SkipRelease) {
    $gradleTasks += ':app:assembleRelease'
}

& $gradle '-p' $androidRoot '--no-daemon' @gradleTasks
Assert-LastExitCode 'Android build, lint, unit and instrumentation compilation'

if (-not $SkipRelease) {
    & (Join-Path $androidRoot 'verify-release-boundary.ps1')
    Assert-LastExitCode 'Android release boundary scan'
}

Write-Output 'PHASE 6 ANDROID V1 EXIT GATE PASSED'
