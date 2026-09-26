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
$corepack = (Get-Command corepack).Source

New-Item -ItemType Directory -Force $bundleDirectory | Out-Null

Push-Location $repositoryRoot
try {
    & $corepack 'pnpm@10.34.5' '--dir' $PSScriptRoot 'exec' 'redocly' `
        'lint' $source '--config' $redoclyConfig
    if ($LASTEXITCODE -ne 0) {
        throw "OpenAPI lint failed with exit code $LASTEXITCODE."
    }

    & $corepack 'pnpm@10.34.5' '--dir' $PSScriptRoot 'exec' 'redocly' `
        'bundle' $source '--config' $redoclyConfig '--output' $bundle
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
        'ProviderCapabilities',
        'manual_mask',
        'interrupt_running',
        'storage_capacity'
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
    $process = Start-Process -FilePath $corepack `
        -ArgumentList @('pnpm@10.34.5', '--dir', $PSScriptRoot, 'exec', 'prism', 'mock', $bundle, '--host', '127.0.0.1', '--port', "$MockPort") `
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
    }
    finally {
        if (-not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F | Out-Null
            $process.WaitForExit()
        }
    }

    Write-Output 'TASK 2 CONTRACT VERIFICATION PASSED'
}
finally {
    Pop-Location
}
