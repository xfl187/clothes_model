param(
    [string]$BaseUrl = 'https://localhost:8443'
)

# Phase 8 security smoke for an already-running production profile. It uses no
# credentials so it can run after the Phase 2 deployment smoke without sharing
# its one-time bootstrap tokens.
$ErrorActionPreference = 'Stop'

function Assert-Status {
    param(
        [Parameter(Mandatory)] [string]$Uri,
        [Parameter(Mandatory)] [int]$Status
    )
    $response = Invoke-WebRequest -Uri $Uri -SkipCertificateCheck -SkipHttpErrorCheck
    if ([int]$response.StatusCode -ne $Status) {
        throw "Expected HTTP $Status from $Uri but received $($response.StatusCode)."
    }
    return $response
}

$ready = Assert-Status -Uri "$BaseUrl/health/ready" -Status 200
$readyBody = $ready.Content | ConvertFrom-Json
if ($readyBody.status -ne 'ok') { throw 'Readiness did not report ok.' }

# Anonymous callers must not reach admin or private content.
Assert-Status -Uri "$BaseUrl/api/v1/admin/system/overview" -Status 401 | Out-Null
Assert-Status -Uri "$BaseUrl/api/v1/assets/missing/content" -Status 401 | Out-Null

# The served Web shell must not leak credential material.
$shell = Assert-Status -Uri "$BaseUrl/" -Status 200
foreach ($marker in @('BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY', 'admin_token', 'super-secret')) {
    if ($shell.Content -like "*$marker*") {
        throw "Served Web shell contains forbidden marker: $marker"
    }
}

Write-Output 'PHASE 8 SECURITY DEPLOYMENT SMOKE PASSED'
