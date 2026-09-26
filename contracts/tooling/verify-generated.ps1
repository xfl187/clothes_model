[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backendRoot = Join-Path $repositoryRoot 'backend'
$androidSource = Join-Path $repositoryRoot 'android\core\api-contract\src\main\kotlin'
$webGenerated = Join-Path $repositoryRoot 'web-admin\src\api\generated'
$uvCommand = if ($env:CLOTHES_MODEL_UV) { $env:CLOTHES_MODEL_UV } else { 'uv' }

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

& (Join-Path $PSScriptRoot 'check-generated.ps1')
Assert-LastExitCode 'Generated artifact drift check'

Push-Location $backendRoot
try {
    & $uvCommand run pyright
    Assert-LastExitCode 'Backend generated model type-check'
}
finally {
    Pop-Location
}

& corepack 'pnpm@10.34.5' '--dir' $PSScriptRoot 'run' 'typecheck:web-generated'
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

$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-kotlin-compile-' + [System.Guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Force -Path (Join-Path $temporaryRoot 'src\main') | Out-Null

try {
    Copy-Item -LiteralPath $androidSource `
        -Destination (Join-Path $temporaryRoot 'src\main\kotlin') `
        -Recurse
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'templates\kotlin-compile-build.gradle') `
        -Destination (Join-Path $temporaryRoot 'build.gradle')
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'templates\kotlin-compile-settings.gradle') `
        -Destination (Join-Path $temporaryRoot 'settings.gradle')

    $gradleCommand = if ($env:CLOTHES_MODEL_GRADLE) {
        $env:CLOTHES_MODEL_GRADLE
    }
    elseif (Test-Path -LiteralPath (Join-Path $repositoryRoot 'android\gradlew.bat')) {
        Join-Path $repositoryRoot 'android\gradlew.bat'
    }
    else {
        $resolvedGradle = Get-Command gradle -ErrorAction SilentlyContinue
        if ($null -eq $resolvedGradle) {
            throw 'Gradle is unavailable. Set CLOTHES_MODEL_GRADLE or complete the Task 7 wrapper.'
        }
        $resolvedGradle.Source
    }

    & $gradleCommand '-p' $temporaryRoot '--no-daemon' 'clean' 'compileKotlin'
    Assert-LastExitCode 'Android generated client compilation'
}
finally {
    $temporaryFullPath = [System.IO.Path]::GetFullPath($temporaryRoot)
    $systemTempPrefix = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (
        $temporaryFullPath.StartsWith($systemTempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $temporaryFullPath -Leaf).StartsWith('clothes-model-kotlin-compile-')
    ) {
        Remove-Item -LiteralPath $temporaryFullPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Output 'GENERATED CONTRACT VERIFICATION PASSED'
