param(
    [string]$ApkPath = (Join-Path $PSScriptRoot 'app/build/outputs/apk/release/app-release-unsigned.apk')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $ApkPath)) {
    throw "Release APK not found: $ApkPath"
}

$forbiddenValues = @(
    '10.0.2.2',
    'contract-placeholder',
    '01992b5a-0000-7000-8000-000000000001'
)

$archive = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $ApkPath))
try {
    foreach ($entry in $archive.Entries) {
        if ($entry.Length -eq 0) {
            continue
        }

        $stream = $entry.Open()
        try {
            $memory = [System.IO.MemoryStream]::new()
            $stream.CopyTo($memory)
            $content = [System.Text.Encoding]::UTF8.GetString($memory.ToArray())
            foreach ($value in $forbiddenValues) {
                if ($content.Contains($value, [System.StringComparison]::Ordinal)) {
                    throw "Release APK contains forbidden debug value '$value' in $($entry.FullName)."
                }
            }
        }
        finally {
            $stream.Dispose()
        }
    }
}
finally {
    $archive.Dispose()
}

Write-Output "Release boundary verified: $ApkPath"
