[CmdletBinding()]
param(
    [switch]$SkipKotlinCompile
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$runningOnWindows = $env:OS -eq 'Windows_NT'
$backendRoot = Join-Path $repositoryRoot 'backend'
$androidSource = Join-Path $repositoryRoot 'android\core\api-contract\src\main\kotlin'
$webGenerated = Join-Path $repositoryRoot 'web-admin\src\api\generated'
$uvCommand = if ($env:CLOTHES_MODEL_UV) {
    $env:CLOTHES_MODEL_UV
}
else {
    $resolvedUv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $resolvedUv) { $resolvedUv.Source } else { $null }
}

function Assert-LastExitCode([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE."
    }
}

function Assert-Contains([string]$Path, [string]$Value) {
    $content = [System.IO.File]::ReadAllText($Path)
    if (-not $content.Contains($Value)) {
        throw "Expected generated fallback '$Value' in $Path."
    }
}

function Invoke-BackendTool([string]$Name, [string[]]$Arguments) {
    if ($null -ne $uvCommand) {
        & $uvCommand 'run' '--project' $backendRoot $Name @Arguments
    }
    elseif ($Name -eq 'pyright') {
        $python = Join-Path $backendRoot '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $python)) {
            throw "Missing Backend Python. Install the locked Backend environment or set CLOTHES_MODEL_UV."
        }
        & $python '-m' 'pyright' @Arguments
    }
    else {
        $extension = if ($runningOnWindows) { '.exe' } else { '' }
        $command = Join-Path $backendRoot ('.venv\Scripts\' + $Name + $extension)
        if (-not (Test-Path -LiteralPath $command)) {
            throw "Missing Backend tool '$Name'. Install the locked Backend environment or set CLOTHES_MODEL_UV."
        }
        & $command @Arguments
    }
    Assert-LastExitCode "Backend tool '$Name'"
}

& (Join-Path $PSScriptRoot 'check-generated.ps1')
Assert-LastExitCode 'Generated artifact drift check'

Push-Location $backendRoot
try {
    Invoke-BackendTool 'pyright' @()
}
finally {
    Pop-Location
}

$tscExtension = if ($runningOnWindows) { '.cmd' } else { '' }
$tscCommand = Join-Path $PSScriptRoot ('node_modules\.bin\tsc' + $tscExtension)
if (-not (Test-Path -LiteralPath $tscCommand)) {
    throw 'Missing TypeScript compiler. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
}
& $tscCommand '--project' (Join-Path $PSScriptRoot 'tsconfig.web-generated.json')
Assert-LastExitCode 'Web generated client type-check'

Assert-Contains `
    (Join-Path $androidSource 'com\clothesmodel\contract\model\JobState.kt') `
    '?: JobState.unknown_default_open_api'
Assert-Contains `
    (Join-Path $webGenerated 'models\JobState.ts') `
    'UnknownDefaultOpenApi'
Assert-Contains `
    (Join-Path $backendRoot 'src\clothes_model\generated\models.py') `
    'code: str'
Assert-Contains `
    (Join-Path $androidSource 'com\clothesmodel\contract\model\ProblemDetails.kt') `
    'val code: kotlin.String'
Assert-Contains `
    (Join-Path $webGenerated 'models\ProblemDetails.ts') `
    'code: string'

if (-not $SkipKotlinCompile) {
    & (Join-Path $PSScriptRoot 'compile-generated-kotlin.ps1')
    Assert-LastExitCode 'Android generated client compilation'
}

Write-Output 'GENERATED CONTRACT VERIFICATION PASSED'
