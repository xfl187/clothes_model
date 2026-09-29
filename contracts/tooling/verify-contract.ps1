[CmdletBinding()]
param(
    [int]$MockPort = 4010
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$source = Join-Path $repositoryRoot 'contracts\openapi\openapi.yaml'
$bundleDirectory = Join-Path $repositoryRoot 'contracts\generated'
$bundle = Join-Path $bundleDirectory 'openapi.yaml'
$redoclyConfig = Join-Path $PSScriptRoot 'redocly.yaml'
$toolExtension = if ($env:OS -eq 'Windows_NT') { '.cmd' } else { '' }
$redocly = Join-Path $PSScriptRoot ('node_modules\.bin\redocly' + $toolExtension)
$prismEntry = Join-Path $PSScriptRoot 'node_modules\@stoplight\prism-cli\dist\index.js'
$node = (Get-Command node).Source

foreach ($tool in @($redocly, $prismEntry)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        throw 'Missing contract tooling. Run corepack pnpm install --frozen-lockfile in contracts/tooling.'
    }
}

New-Item -ItemType Directory -Force $bundleDirectory | Out-Null

Push-Location $repositoryRoot
try {
    & $redocly 'lint' $source '--config' $redoclyConfig
    if ($LASTEXITCODE -ne 0) {
        throw "OpenAPI lint failed with exit code $LASTEXITCODE."
    }

    & $redocly 'bundle' $source '--config' $redoclyConfig '--output' $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "OpenAPI bundle failed with exit code $LASTEXITCODE."
    }

    $bundledText = Get-Content -Raw -LiteralPath $bundle
    $referenceLines = @(
        $bundledText -split "`n" |
            Where-Object { $_ -match '^\s*\$ref:' }
    )
    $externalReferenceLines = @(
        $referenceLines |
            Where-Object { $_ -notmatch '#/components/' }
    )
    if ($externalReferenceLines.Count -gt 0) {
        throw 'Bundled OpenAPI still contains external $ref entries.'
    }

    & (Join-Path $PSScriptRoot 'verify-additive-contract.ps1') -Current $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Additive compatibility verification failed with exit code $LASTEXITCODE."
    }
    & (Join-Path $PSScriptRoot 'verify-phase2-boundaries.ps1') -Current $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 boundary verification failed with exit code $LASTEXITCODE."
    }
    & (Join-Path $PSScriptRoot 'verify-phase3-boundaries.ps1') -Current $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3 boundary verification failed with exit code $LASTEXITCODE."
    }
    & (Join-Path $PSScriptRoot 'verify-phase5-boundaries.ps1') -Current $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 5 boundary verification failed with exit code $LASTEXITCODE."
    }
    & (Join-Path $PSScriptRoot 'verify-phase6-boundaries.ps1') -Current $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 6 boundary verification failed with exit code $LASTEXITCODE."
    }
    & (Join-Path $PSScriptRoot 'verify-local-first-boundaries.ps1') -Current $bundle
    if ($LASTEXITCODE -ne 0) {
        throw "Local-first boundary verification failed with exit code $LASTEXITCODE."
    }

    $requiredContractTokens = @(
        'UploadSession',
        'AssetPage',
        'TryOnJob',
        'JobItem',
        'GeneratedOutput',
        'ProviderConfig',
        'WorkflowVersion',
        'DefaultProviderConfiguration',
        'StorageStatus',
        'DiagnosticJobDetail',
        'queued',
        'waiting_provider',
        'preparing',
        'running',
        'needs_attention',
        'succeeded',
        'partially_succeeded',
        'failed',
        'cancelled',
        'Idempotency-Key',
        'next_cursor',
        'has_more',
        'ProblemDetails',
        'authentication_required',
        'ProviderConfigRef',
        'WorkflowVersionRef',
        'VersionSnapshot',
        'ProviderSnapshot',
        'next_attempt_at',
        'superseded_by_job_item_id',
        'job_state_conflict',
        'provider_not_usable',
        'ProviderCapabilities',
        'manual_mask',
        'interrupt_running',
        'storage_capacity',
        'getAdminSession',
        'updateAsset',
        'deleteAssetContent',
        'listAssetReferences',
        'insufficient_scope',
        'csrf_rejected',
        'authentication_throttled',
        'idempotency_key_reused',
        'upload_offset_conflict',
        'asset_referenced',
        'invalid_image'
        'WorkflowArtifactMetadata'
        'WorkflowCompatibilityResult'
        'retireWorkflowVersion'
        'logical_provider_id'
        'workflow_sha256'
        'manifest_sha256'
    )

    foreach ($token in $requiredContractTokens) {
        if (-not $bundledText.Contains($token)) {
            throw "Bundled OpenAPI is missing required token: $token"
        }
    }

    if ($bundledText -match '/api/v1/outfits(?:/|:)') {
        throw 'V1.1 Outfit paths must not be present in the Phase 1 contract.'
    }
    if ($bundledText -match '(?m)^\s*Outfit(?:Session|Revision|Layer):') {
        throw 'V1.1 Outfit resource schemas must not be present in the Phase 1 contract.'
    }

    $stdout = Join-Path ([System.IO.Path]::GetTempPath()) "clothes-model-prism-$MockPort.stdout.log"
    $stderr = Join-Path ([System.IO.Path]::GetTempPath()) "clothes-model-prism-$MockPort.stderr.log"
    $process = Start-Process -FilePath $node `
        -ArgumentList @($prismEntry, 'mock', $bundle, '--host', '127.0.0.1', '--port', "$MockPort") `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru

    try {
        $mockUrl = "http://127.0.0.1:$MockPort/health/live"
        $response = $null
        for ($attempt = 1; $attempt -le 60; $attempt++) {
            if ($process.HasExited) {
                $errorOutput = if (Test-Path $stderr) { Get-Content -Raw $stderr } else { '' }
                throw "Prism exited before becoming ready. $errorOutput"
            }
            try {
                $response = Invoke-WebRequest -Uri $mockUrl -UseBasicParsing -TimeoutSec 2
                break
            }
            catch {
                Start-Sleep -Milliseconds 500
            }
        }

        if ($null -eq $response -or $response.StatusCode -ne 200) {
            throw 'Prism mock server did not return HTTP 200 for /health/live.'
        }

        Write-Output "Contract mock returned HTTP $($response.StatusCode) from $mockUrl"

        $placeholderHeaders = @{
            Authorization = 'Bearer contract-placeholder'
            'X-CSRF-Token' = 'contract-placeholder'
        }
        $webSession = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
        $webSession.Cookies.Add(
            [System.Net.Cookie]::new(
                'clothes_admin_session',
                'contract-placeholder',
                '/',
                '127.0.0.1'
            )
        )
        $exampleProbes = @(
            @{
                Name = 'job'
                Url = "http://127.0.0.1:$MockPort/api/v1/jobs/01992b5a-0000-7000-8000-000000000002"
                Example = 'partiallySucceeded'
                Token = 'partially_succeeded'
            },
            @{
                Name = 'provider capabilities'
                Url = "http://127.0.0.1:$MockPort/api/v1/providers"
                Example = 'availableProviders'
                Token = 'manual_mask'
            },
            @{
                Name = 'storage'
                Url = "http://127.0.0.1:$MockPort/api/v1/admin/storage"
                Example = 'blocked'
                Token = 'storage_capacity'
            },
            @{
                Name = 'diagnostics'
                Url = "http://127.0.0.1:$MockPort/api/v1/admin/diagnostics/jobs"
                Example = 'snapshot'
                Token = 'snapshot_at'
            }
        )

        foreach ($probe in $exampleProbes) {
            $headers = $placeholderHeaders.Clone()
            $headers['Prefer'] = "example=$($probe.Example)"
            $exampleResponse = Invoke-WebRequest `
                -Uri $probe.Url `
                -Headers $headers `
                -WebSession $webSession `
                -UseBasicParsing `
                -TimeoutSec 5
            if (
                $exampleResponse.StatusCode -ne 200 -or
                -not $exampleResponse.Content.Contains($probe.Token)
            ) {
                throw "Prism did not return the configured $($probe.Name) example."
            }
            Write-Output "Contract mock returned configured $($probe.Name) example."
        }

        $assetId = '01992b5a-0000-7000-8000-000000000101'
        $uploadId = '01992b5a-0000-7000-8000-000000000201'
        $successProbes = @(
            @{
                Name = 'admin session inspection'
                Method = 'GET'
                Url = "http://127.0.0.1:$MockPort/api/v1/admin/auth/session"
                Example = 'active'
                Token = 'csrf_token'
            },
            @{
                Name = 'asset favorite update'
                Method = 'PATCH'
                Url = "http://127.0.0.1:$MockPort/api/v1/assets/$assetId"
                Example = 'favorite'
                Token = '"favorite":true'
                Body = '{"favorite":true}'
                ContentType = 'application/json'
            },
            @{
                Name = 'asset content deletion'
                Method = 'DELETE'
                Url = "http://127.0.0.1:$MockPort/api/v1/assets/$assetId/content"
                Example = 'deleted'
                Token = 'content_deleted'
            },
            @{
                Name = 'asset reference page'
                Method = 'GET'
                Url = "http://127.0.0.1:$MockPort/api/v1/assets/$assetId/references"
                Example = 'blockers'
                Token = 'source_kind'
            }
        )

        foreach ($probe in $successProbes) {
            $headers = $placeholderHeaders.Clone()
            $headers['Prefer'] = "example=$($probe.Example)"
            $request = @{
                Uri = $probe.Url
                Method = $probe.Method
                Headers = $headers
                WebSession = $webSession
                UseBasicParsing = $true
                TimeoutSec = 5
            }
            if ($probe.Body) {
                $request['Body'] = $probe.Body
                $request['ContentType'] = $probe.ContentType
            }
            $probeResponse = Invoke-WebRequest @request
            if (
                $probeResponse.StatusCode -ne 200 -or
                -not $probeResponse.Content.Contains($probe.Token)
            ) {
                throw "Prism did not return the configured $($probe.Name) success example."
            }
            Write-Output "Contract mock returned configured $($probe.Name) success example."
        }

        $uploadRequest = '{"asset_kind":"person","filename":"person.jpg","content_type":"image/jpeg","size_bytes":4}'
        $completeRequest = '{"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
        $errorProbes = @(
            @{
                Name = 'invalid credentials'
                Method = 'GET'
                Url = "http://127.0.0.1:$MockPort/api/v1/auth/status"
                Status = 401
                Example = 'invalidToken'
                Token = 'authentication_required'
            },
            @{
                Name = 'wrong scope'
                Method = 'PATCH'
                Url = "http://127.0.0.1:$MockPort/api/v1/assets/$assetId"
                Status = 403
                Example = 'wrongScope'
                Token = 'insufficient_scope'
                Body = '{"favorite":true}'
                ContentType = 'application/json'
            },
            @{
                Name = 'CSRF rejection'
                Method = 'DELETE'
                Url = "http://127.0.0.1:$MockPort/api/v1/admin/auth/session"
                Status = 403
                Example = 'csrfRejected'
                Token = 'csrf_rejected'
            },
            @{
                Name = 'upload offset conflict'
                Method = 'PATCH'
                Url = "http://127.0.0.1:$MockPort/api/v1/uploads/$uploadId/content"
                Status = 409
                Example = 'uploadOffsetConflict'
                Token = 'upload_offset_conflict'
                Body = 'test'
                ContentType = 'application/offset+octet-stream'
                UploadOffset = '0'
            },
            @{
                Name = 'idempotency conflict'
                Method = 'POST'
                Url = "http://127.0.0.1:$MockPort/api/v1/uploads"
                Status = 409
                Example = 'idempotencyConflict'
                Token = 'idempotency_key_reused'
                Body = $uploadRequest
                ContentType = 'application/json'
                IdempotencyKey = 'contract-idempotency-key-0001'
            },
            @{
                Name = 'referenced asset'
                Method = 'DELETE'
                Url = "http://127.0.0.1:$MockPort/api/v1/assets/$assetId/content"
                Status = 409
                Example = 'assetReferenced'
                Token = 'asset_referenced'
            },
            @{
                Name = 'storage insufficient'
                Method = 'POST'
                Url = "http://127.0.0.1:$MockPort/api/v1/uploads"
                Status = 507
                Example = 'storageCapacity'
                Token = 'storage_capacity'
                Body = $uploadRequest
                ContentType = 'application/json'
                IdempotencyKey = 'contract-idempotency-key-0002'
            },
            @{
                Name = 'invalid image'
                Method = 'POST'
                Url = "http://127.0.0.1:$MockPort/api/v1/uploads/$uploadId/complete"
                Status = 422
                Example = 'invalidImage'
                Token = 'invalid_image'
                Body = $completeRequest
                ContentType = 'application/json'
                IdempotencyKey = 'contract-idempotency-key-0003'
            }
        )

        foreach ($probe in $errorProbes) {
            $headers = $placeholderHeaders.Clone()
            $headers['Prefer'] = "code=$($probe.Status), example=$($probe.Example)"
            if ($probe.UploadOffset) {
                $headers['Upload-Offset'] = $probe.UploadOffset
            }
            if ($probe.IdempotencyKey) {
                $headers['Idempotency-Key'] = $probe.IdempotencyKey
            }
            $request = @{
                Uri = $probe.Url
                Method = $probe.Method
                Headers = $headers
                WebSession = $webSession
                UseBasicParsing = $true
                SkipHttpErrorCheck = $true
                TimeoutSec = 5
            }
            if ($probe.Body) {
                $request['Body'] = $probe.Body
                $request['ContentType'] = $probe.ContentType
            }
            $probeResponse = Invoke-WebRequest @request
            $responseBody = if ($probeResponse.Content -is [byte[]]) {
                [System.Text.Encoding]::UTF8.GetString($probeResponse.Content)
            }
            else {
                [string]$probeResponse.Content
            }
            if (
                $probeResponse.StatusCode -ne $probe.Status -or
                -not $responseBody.Contains($probe.Token)
            ) {
                throw (
                    "Prism did not return the configured $($probe.Name) error example. " +
                    "Status=$($probeResponse.StatusCode) Body=$responseBody"
                )
            }
            Write-Output "Contract mock returned configured $($probe.Name) error example."
        }
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $process.WaitForExit()
        }
    }

    Write-Output 'CONTRACT VERIFICATION PASSED'
}
finally {
    Pop-Location
}
