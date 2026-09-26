[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-codegen-check-' + [System.Guid]::NewGuid().ToString('N')
)
$generatedRoots = @(
    'contracts\generated\openapi.yaml',
    'backend\src\clothes_model\generated',
    'android\core\api-contract\README.md',
    'android\core\api-contract\src\main\kotlin',
    'web-admin\src\api\generated'
)

function Get-RelativeChildPath([string]$BasePath, [string]$ChildPath) {
    $base = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\', '/') + `
        [System.IO.Path]::DirectorySeparatorChar
    $child = [System.IO.Path]::GetFullPath($ChildPath)
    if (-not $child.StartsWith($base, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is not a child of its generation root: $child"
    }
    return $child.Substring($base.Length)
}

function Get-GeneratedManifest([string]$Root) {
    $manifest = @{}
    foreach ($relativeRoot in $generatedRoots) {
        $target = Join-Path $Root $relativeRoot
        if (-not (Test-Path -LiteralPath $target)) {
            throw "Missing generated target: $target"
        }
        $item = Get-Item -LiteralPath $target
        $files = if ($item.PSIsContainer) {
            Get-ChildItem -LiteralPath $target -Recurse -File | Where-Object {
                $_.FullName -notmatch '[\\/](build|__pycache__|\.gradle)[\\/]' -and
                $_.Extension -ne '.pyc'
            }
        }
        else {
            @($item)
        }
        foreach ($file in $files) {
            $relative = Get-RelativeChildPath $Root $file.FullName
            $manifest[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        }
    }
    return $manifest
}

try {
    & (Join-Path $PSScriptRoot 'generate-contracts.ps1') -OutputRoot $temporaryRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Temporary contract generation failed with exit code $LASTEXITCODE."
    }

    $expected = Get-GeneratedManifest $repositoryRoot
    $actual = Get-GeneratedManifest $temporaryRoot
    $differences = @()

    foreach ($path in ($expected.Keys + $actual.Keys | Sort-Object -Unique)) {
        if (-not $expected.ContainsKey($path)) {
            $differences += "unexpected generated file: $path"
        }
        elseif (-not $actual.ContainsKey($path)) {
            $differences += "missing generated file: $path"
        }
        elseif ($expected[$path] -ne $actual[$path]) {
            $differences += "changed generated file: $path"
        }
    }

    if ($differences.Count -gt 0) {
        throw "Generated artifacts are stale:`n$($differences -join "`n")"
    }

    Write-Output "Generated artifact drift check passed ($($expected.Count) files)."
}
finally {
    $temporaryFullPath = [System.IO.Path]::GetFullPath($temporaryRoot)
    $systemTempPrefix = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (
        $temporaryFullPath.StartsWith($systemTempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $temporaryFullPath -Leaf).StartsWith('clothes-model-codegen-check-')
    ) {
        Remove-Item -LiteralPath $temporaryFullPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}
