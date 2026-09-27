param(
    [string]$BaseUrl = 'https://localhost:8443',
    [string]$ComposeFile = (Join-Path $PSScriptRoot 'compose.yaml')
)

$ErrorActionPreference = 'Stop'

function Wait-Ready {
    param([int]$Attempts = 45)
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $ready = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -SkipCertificateCheck
            if ($ready.status -eq 'ok' -and $ready.checks.scheduler -eq 'owned') { return }
        } catch {
            if ($attempt -eq $Attempts) { throw }
        }
        Start-Sleep -Seconds 2
    }
    throw 'Backend did not become ready.'
}

function Invoke-Json {
    param(
        [Parameter(Mandatory)] [string]$Method,
        [Parameter(Mandatory)] [string]$Uri,
        [hashtable]$Headers = @{},
        [object]$Body,
        [Microsoft.PowerShell.Commands.WebRequestSession]$WebSession
    )
    $parameters = @{
        Method = $Method
        Uri = $Uri
        Headers = $Headers
        SkipCertificateCheck = $true
    }
    if ($null -ne $Body) {
        $parameters.ContentType = 'application/json'
        $parameters.Body = $Body | ConvertTo-Json -Compress
    }
    if ($null -ne $WebSession) { $parameters.WebSession = $WebSession }
    Invoke-RestMethod @parameters
}

Wait-Ready

$bootstrapOutput = & docker compose -f $ComposeFile --profile production exec -T app `
    clothes-model-security bootstrap 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Credential bootstrap failed.' }
$bootstrapText = $bootstrapOutput -join "`n"
$appMatch = [regex]::Match($bootstrapText, 'Created App Token \(shown once\): (?<token>\S+)')
$adminMatch = [regex]::Match($bootstrapText, 'Created Admin Token \(shown once\): (?<token>\S+)')
if (-not $appMatch.Success -or -not $adminMatch.Success) {
    throw 'Fresh deployment did not issue both credentials.'
}
$appToken = $appMatch.Groups['token'].Value
$adminToken = $adminMatch.Groups['token'].Value
$appHeaders = @{ Authorization = "Bearer $appToken" }

$auth = Invoke-Json -Method Get -Uri "$BaseUrl/api/v1/auth/status" -Headers $appHeaders
if (-not $auth.authenticated) { throw 'App authentication failed.' }

try {
    Invoke-Json -Method Get -Uri "$BaseUrl/api/v1/admin/storage" -Headers $appHeaders | Out-Null
    throw 'App credential unexpectedly reached an Admin resource.'
} catch {
    if ($_.Exception.Response.StatusCode -ne 401) { throw }
}

$imageBytes = [Convert]::FromBase64String(
    'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAFElEQVR4nGOskAtgwAaYsIrSSQIAiToA8qLNJ9cAAAAASUVORK5CYII='
)
$imageSha = [Convert]::ToHexString(
    [System.Security.Cryptography.SHA256]::HashData($imageBytes)
).ToLowerInvariant()
$createHeaders = @{
    Authorization = "Bearer $appToken"
    'Idempotency-Key' = "deployment-create-$([guid]::NewGuid())"
}
$upload = Invoke-Json -Method Post -Uri "$BaseUrl/api/v1/uploads" -Headers $createHeaders -Body @{
    asset_kind = 'person'
    filename = 'deployment-smoke.png'
    content_type = 'image/png'
    size_bytes = $imageBytes.Length
}
$midpoint = [Math]::Floor($imageBytes.Length / 2)
$firstChunk = $imageBytes[0..($midpoint - 1)]
$secondChunk = $imageBytes[$midpoint..($imageBytes.Length - 1)]

$appendHeaders = @{
    Authorization = "Bearer $appToken"
    'Upload-Offset' = '0'
}
$firstChunkPath = [System.IO.Path]::GetTempFileName()
$secondChunkPath = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllBytes($firstChunkPath, $firstChunk)
[System.IO.File]::WriteAllBytes($secondChunkPath, $secondChunk)
try {
    $firstResult = Invoke-WebRequest -Method Patch `
        -Uri "$BaseUrl/api/v1/uploads/$($upload.id)/content" `
        -Headers $appendHeaders -ContentType 'application/offset+octet-stream' `
        -InFile $firstChunkPath -SkipCertificateCheck
} finally {
    Remove-Item -LiteralPath $firstChunkPath -Force -ErrorAction SilentlyContinue
}
if (($firstResult.Content | ConvertFrom-Json).uploaded_bytes -ne $midpoint) {
    throw 'First upload offset was not confirmed.'
}

& docker compose -f $ComposeFile --profile production restart app | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Backend restart failed.' }
Wait-Ready

$resumed = Invoke-Json -Method Get -Uri "$BaseUrl/api/v1/uploads/$($upload.id)" -Headers $appHeaders
if ($resumed.uploaded_bytes -ne $midpoint) { throw 'Confirmed upload offset was not restored.' }
$appendHeaders['Upload-Offset'] = [string]$midpoint
try {
    $secondResult = Invoke-WebRequest -Method Patch `
        -Uri "$BaseUrl/api/v1/uploads/$($upload.id)/content" `
        -Headers $appendHeaders -ContentType 'application/offset+octet-stream' `
        -InFile $secondChunkPath -SkipCertificateCheck
} finally {
    Remove-Item -LiteralPath $secondChunkPath -Force -ErrorAction SilentlyContinue
}
if (($secondResult.Content | ConvertFrom-Json).uploaded_bytes -ne $imageBytes.Length) {
    throw 'Resumed upload did not reach the declared size.'
}

$completeHeaders = @{
    Authorization = "Bearer $appToken"
    'Idempotency-Key' = "deployment-complete-$([guid]::NewGuid())"
}
$asset = Invoke-Json -Method Post `
    -Uri "$BaseUrl/api/v1/uploads/$($upload.id)/complete" `
    -Headers $completeHeaders -Body @{ sha256 = $imageSha }
$downloadPath = Join-Path ([System.IO.Path]::GetTempPath()) "clothes-model-$($asset.id).jpg"
try {
    Invoke-WebRequest -Method Get -Uri "$BaseUrl/api/v1/assets/$($asset.id)/content" `
        -Headers $appHeaders -OutFile $downloadPath -SkipCertificateCheck
    if ((Get-Item -LiteralPath $downloadPath).Length -le 0) {
        throw 'Private asset download was empty.'
    }
} finally {
    Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue
}

try {
    Invoke-WebRequest -Method Get -Uri "$BaseUrl/api/v1/assets/$($asset.id)/content" `
        -SkipCertificateCheck | Out-Null
    throw 'Private asset content was reachable without authentication.'
} catch {
    if ($_.Exception.Response.StatusCode -ne 401) { throw }
}

$adminSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$login = Invoke-Json -Method Post -Uri "$BaseUrl/api/v1/admin/auth/session" `
    -Body @{ admin_token = $adminToken } -WebSession $adminSession
if (-not $login.authenticated -or [string]::IsNullOrWhiteSpace($login.csrf_token)) {
    throw 'Admin login did not create a usable session.'
}
$restored = Invoke-Json -Method Get -Uri "$BaseUrl/api/v1/admin/auth/session" `
    -WebSession $adminSession
if (-not $restored.authenticated -or [string]::IsNullOrWhiteSpace($restored.csrf_token)) {
    throw 'Admin cookie session did not restore.'
}
Invoke-WebRequest -Method Delete -Uri "$BaseUrl/api/v1/admin/auth/session" `
    -Headers @{ 'X-CSRF-Token' = $restored.csrf_token; Origin = $BaseUrl } `
    -WebSession $adminSession -SkipCertificateCheck | Out-Null

$shell = Invoke-WebRequest -Method Get -Uri "$BaseUrl/" -SkipCertificateCheck
if ($shell.Content -notmatch '<div id="root"></div>') { throw 'Web Admin shell was not served.' }

Write-Host "Phase 2 deployment smoke passed (upload $($upload.id), asset $($asset.id))."
