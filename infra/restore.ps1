param(
    [Parameter(Mandatory)] [string]$ArchivePath,
    [Parameter(Mandatory)] [string]$DatabasePath,
    [Parameter(Mandatory)] [string]$StoragePath,
    [switch]$Force
)

# Restores a backup produced by backup.ps1 into a clean or explicitly forced
# target. Stop the Backend before restoring; running tasks must not resume on a
# half-restored pair.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ArchivePath)) {
    throw "Archive not found: $ArchivePath"
}
if ((Test-Path -LiteralPath $DatabasePath) -and -not $Force) {
    throw "Refusing to overwrite $DatabasePath without -Force"
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) (
    'clothes-model-restore-' + [System.Guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Force -Path $staging | Out-Null
try {
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $staging -Force
    $sourceDatabase = Join-Path $staging 'app.db'
    $sourceStorage = Join-Path $staging 'storage'
    if (-not (Test-Path -LiteralPath $sourceDatabase)) {
        throw 'Archive does not contain app.db.'
    }
    if (-not (Test-Path -LiteralPath $sourceStorage)) {
        throw 'Archive does not contain a storage directory.'
    }

    $databaseParent = Split-Path -Parent $DatabasePath
    if ($databaseParent) { New-Item -ItemType Directory -Force -Path $databaseParent | Out-Null }
    if (Test-Path -LiteralPath $DatabasePath) { Remove-Item -LiteralPath $DatabasePath -Force }
    if (Test-Path -LiteralPath $StoragePath) {
        Remove-Item -LiteralPath $StoragePath -Recurse -Force
    }
    Copy-Item -LiteralPath $sourceDatabase -Destination $DatabasePath
    Copy-Item -LiteralPath $sourceStorage -Destination $StoragePath -Recurse
}
finally {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "Restored database to $DatabasePath and storage to $StoragePath"
