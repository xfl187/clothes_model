[CmdletBinding()]
param(
    [string]$GradleCommand
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$androidSource = Join-Path $repositoryRoot 'android\core\api-contract\src\main\kotlin'
$resolvedGradle = if (-not [string]::IsNullOrWhiteSpace($GradleCommand)) {
    $GradleCommand
}
elseif ($env:CLOTHES_MODEL_GRADLE) {
    $env:CLOTHES_MODEL_GRADLE
}
elseif (Test-Path -LiteralPath (Join-Path $repositoryRoot 'android\gradlew.bat')) {
    Join-Path $repositoryRoot 'android\gradlew.bat'
}
else {
    $gradle = Get-Command gradle -ErrorAction SilentlyContinue
    if ($null -eq $gradle) {
        throw 'Gradle is unavailable. Set CLOTHES_MODEL_GRADLE to a compatible Gradle 8.13+ executable.'
    }
    $gradle.Source
}

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

    & $resolvedGradle '-p' $temporaryRoot '--no-daemon' 'clean' 'compileKotlin'
    if ($LASTEXITCODE -ne 0) {
        throw "Android generated client compilation failed with exit code $LASTEXITCODE."
    }
    Write-Output 'Android generated client compilation passed.'
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
