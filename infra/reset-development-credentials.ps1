[CmdletBinding()]
param(
    [string]$OutputPath = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'ClothesModel\development-credentials.json')
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$envFile = Join-Path $repoRoot '.env'

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing $envFile. Start the development environment before resetting credentials."
}

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envFile) {
    if ($line -match '^\s*([^#][^=]*)=(.*)$') {
        $settings[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$backendPort = $settings['CLOTHES_MODEL_BACKEND_PORT']
if ([string]::IsNullOrWhiteSpace($backendPort)) {
    throw "Missing CLOTHES_MODEL_BACKEND_PORT in $envFile."
}

$outputDirectory = Split-Path -Parent $OutputPath
if ([string]::IsNullOrWhiteSpace($outputDirectory)) {
    throw 'OutputPath must include a parent directory.'
}
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$probePath = Join-Path $outputDirectory ([System.IO.Path]::GetRandomFileName())
try {
    [System.IO.File]::WriteAllText($probePath, 'credential-output-probe')
}
finally {
    Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
}

function Invoke-SecurityCommand {
    param(
        [Parameter(Mandatory)]
        [ValidateSet('reset-admin', 'rotate-app')]
        [string]$Command,
        [Parameter(Mandatory)]
        [string]$Scope
    )

    $output = & docker compose --env-file $envFile -f $composeFile --profile development `
        exec -T backend clothes-model-security $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Credential command '$Command' failed with exit code $LASTEXITCODE."
    }

    $text = $output -join "`n"
    $match = [regex]::Match($text, "Created $Scope Token \(shown once\): (?<token>\S+)")
    if (-not $match.Success) {
        throw "Credential command '$Command' did not return the expected $Scope Token."
    }
    return $match.Groups['token'].Value
}

$issuedAt = [DateTimeOffset]::UtcNow.ToString('o')
$adminToken = Invoke-SecurityCommand -Command 'reset-admin' -Scope 'Admin'

# Persist the recoverable Admin credential before rotating the App credential.
$partial = [ordered]@{
    schema_version = 1
    generated_at = $issuedAt
    backend_url = "http://127.0.0.1:$backendPort"
    app_token = $null
    admin_token = $adminToken
}
$temporaryPath = "$OutputPath.tmp"
$partial | ConvertTo-Json | Set-Content -LiteralPath $temporaryPath -Encoding utf8
Move-Item -LiteralPath $temporaryPath -Destination $OutputPath -Force

$appToken = Invoke-SecurityCommand -Command 'rotate-app' -Scope 'App'
$credentials = [ordered]@{
    schema_version = 1
    generated_at = $issuedAt
    backend_url = "http://127.0.0.1:$backendPort"
    app_token = $appToken
    admin_token = $adminToken
}
$credentials | ConvertTo-Json | Set-Content -LiteralPath $temporaryPath -Encoding utf8
Move-Item -LiteralPath $temporaryPath -Destination $OutputPath -Force

Write-Host "Development App/Admin credentials were replaced and saved to: $OutputPath"
Write-Host 'The previous App/Admin Tokens are now invalid.'
