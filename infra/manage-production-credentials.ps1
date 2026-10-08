[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('bootstrap', 'reset-admin', 'rotate-app')]
    [string]$Command,
    [string]$OutputPath = (Join-Path `
        ([Environment]::GetFolderPath('LocalApplicationData')) `
        'ClothesModel\production-credentials.json')
)

$ErrorActionPreference = 'Stop'

if (-not $IsWindows) {
    throw 'Production credential persistence currently requires Windows PowerShell.'
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$envFile = Join-Path $repoRoot '.env'
$resolvedOutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$repoPrefix = $repoRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar

if ($resolvedOutputPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Production credentials must be stored outside the repository.'
}
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing $envFile. Configure the production environment before managing credentials."
}

function Set-PrivateFileAcl {
    param([Parameter(Mandatory)][string]$Path)

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetOwner($identity.User)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $identity.User,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Read-CurrentCredentials {
    if (-not (Test-Path -LiteralPath $resolvedOutputPath -PathType Leaf)) {
        return [ordered]@{
            schema_version = 1
            updated_at = $null
            app_token = $null
            app_token_updated_at = $null
            admin_token = $null
            admin_token_updated_at = $null
        }
    }

    try {
        $document = Get-Content -Raw -LiteralPath $resolvedOutputPath | ConvertFrom-Json -AsHashtable
    }
    catch {
        throw "Existing credential file is not valid JSON: $resolvedOutputPath"
    }
    if ($document.schema_version -ne 1) {
        throw "Unsupported credential file schema in $resolvedOutputPath"
    }
    foreach ($name in @(
        'updated_at',
        'app_token',
        'app_token_updated_at',
        'admin_token',
        'admin_token_updated_at'
    )) {
        if (-not $document.Contains($name)) {
            $document[$name] = $null
        }
    }
    return $document
}

function Save-CurrentCredentials {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Document,
        [Parameter(Mandatory)][hashtable]$IssuedTokens
    )

    $now = [DateTimeOffset]::UtcNow.ToString('o')
    foreach ($scope in $IssuedTokens.Keys) {
        $Document["${scope}_token"] = $IssuedTokens[$scope]
        $Document["${scope}_token_updated_at"] = $now
    }
    $Document['schema_version'] = 1
    $Document['updated_at'] = $now

    $directory = Split-Path -Parent $resolvedOutputPath
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $temporaryPath = "$resolvedOutputPath.tmp"
    try {
        [System.IO.File]::WriteAllText(
            $temporaryPath,
            ($Document | ConvertTo-Json),
            [System.Text.UTF8Encoding]::new($false)
        )
        Set-PrivateFileAcl -Path $temporaryPath
        Move-Item -LiteralPath $temporaryPath -Destination $resolvedOutputPath -Force
        Set-PrivateFileAcl -Path $resolvedOutputPath
    }
    finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}

$currentCredentials = Read-CurrentCredentials
$outputDirectory = Split-Path -Parent $resolvedOutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$probePath = Join-Path $outputDirectory ([System.IO.Path]::GetRandomFileName())
try {
    [System.IO.File]::WriteAllText($probePath, 'credential-output-probe')
    Set-PrivateFileAcl -Path $probePath
}
finally {
    Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
}

$output = & docker compose --env-file $envFile -f $composeFile --profile production `
    exec -T app clothes-model-security $Command 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Production credential command '$Command' failed with exit code $LASTEXITCODE."
}

$text = $output -join "`n"
$issuedTokens = @{}
foreach ($scope in @('App', 'Admin')) {
    $match = [regex]::Match(
        $text,
        "Created $scope Token \(shown once\): (?<token>\S+)"
    )
    if ($match.Success) {
        $issuedTokens[$scope.ToLowerInvariant()] = $match.Groups['token'].Value
    }
}

if ($issuedTokens.Count -eq 0) {
    if ($Command -eq 'bootstrap' -and $text.Contains('Active App/Admin credentials already exist')) {
        Write-Host 'Active production credentials already exist; no plaintext token was issued or changed.'
        exit 0
    }
    throw "Credential command '$Command' did not return an expected one-time token."
}

$expectedScopes = switch ($Command) {
    'reset-admin' { @('admin') }
    'rotate-app' { @('app') }
    default { @() }
}
foreach ($scope in $expectedScopes) {
    if (-not $issuedTokens.ContainsKey($scope)) {
        throw "Credential command '$Command' did not return the expected $scope token."
    }
}

Save-CurrentCredentials -Document $currentCredentials -IssuedTokens $issuedTokens
Write-Host "Production credentials were updated and saved to: $resolvedOutputPath"
Write-Host 'The plaintext token values were not printed to the console.'

