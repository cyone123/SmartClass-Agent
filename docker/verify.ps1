[CmdletBinding()]
param(
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$EnvFile = "",
    [switch]$SkipBuild,
    [switch]$SkipStart
)

$ErrorActionPreference = "Stop"

$ComposeFile = Join-Path $ProjectDir "docker-compose.yml"
if (-not $EnvFile) {
    $EnvFile = Join-Path $ProjectDir ".env.docker"
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Read-EnvFile {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $index = $trimmed.IndexOf("=")
        if ($index -lt 1) {
            continue
        }

        $name = $trimmed.Substring(0, $index).Trim()
        $value = $trimmed.Substring($index + 1).Trim().Trim('"').Trim("'")
        $values[$name] = $value
    }
    return $values
}

function Get-EnvValue {
    param(
        [hashtable]$Values,
        [string]$Name,
        [string]$Default
    )
    if ($Values.ContainsKey($Name) -and $Values[$Name]) {
        return $Values[$Name]
    }
    return $Default
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)
    & docker compose --project-directory $ProjectDir --env-file $EnvFile -f $ComposeFile @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($ComposeArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $response
            }
        }
        catch {
            $lastError = $_
        }
        Start-Sleep -Seconds 3
    }

    throw "Timed out waiting for $Url. Last error: $lastError"
}

if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "Compose file not found: $ComposeFile"
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Docker env file not found: $EnvFile. Copy .env.docker.example to .env.docker and fill required values first."
}

$envValues = Read-EnvFile -Path $EnvFile
$frontendPort = Get-EnvValue $envValues "FRONTEND_PORT" "8080"
$backendPort = Get-EnvValue $envValues "BACKEND_PORT" "8000"
$prometheusPort = Get-EnvValue $envValues "PROMETHEUS_PORT" "9090"
$grafanaPort = Get-EnvValue $envValues "GRAFANA_PORT" "3000"
$postgresUser = Get-EnvValue $envValues "POSTGRES_USER" "smartclass"
$postgresDb = Get-EnvValue $envValues "POSTGRES_DB" "smartclass"

Write-Step "Validating Compose config"
Invoke-Compose @("config", "--quiet")

if (-not $SkipBuild) {
    Write-Step "Building backend and frontend images"
    Invoke-Compose @("build", "backend", "frontend")
}

if (-not $SkipStart) {
    Write-Step "Starting the Docker stack"
    Invoke-Compose @("up", "-d")
}

Write-Step "Checking backend health"
$backendHealth = Wait-Http -Url "http://localhost:$backendPort/health" -TimeoutSeconds 180
Write-Host $backendHealth.Content

Write-Step "Checking frontend health"
$frontendHealth = Wait-Http -Url "http://localhost:$frontendPort/healthz" -TimeoutSeconds 120
Write-Host $frontendHealth.Content

Write-Step "Checking OnlyOffice script through frontend origin"
$onlyofficeScript = Wait-Http -Url "http://localhost:$frontendPort/web-apps/apps/api/documents/api.js" -TimeoutSeconds 180
Write-Host "OnlyOffice script status: $($onlyofficeScript.StatusCode)"

Write-Step "Checking PostgreSQL pgvector extension"
Invoke-Compose @("exec", "-T", "postgres", "psql", "-U", $postgresUser, "-d", $postgresDb, "-c", "SELECT extname FROM pg_extension WHERE extname = 'vector';")

Write-Step "Checking backend runtime tools"
Invoke-Compose @("exec", "-T", "backend", "ffmpeg", "-version")
Invoke-Compose @("exec", "-T", "backend", "soffice", "--version")
Invoke-Compose @("exec", "-T", "backend", "node", "-e", "require('pptxgenjs'); require('docx'); console.log('node artifact dependencies ok')")

Write-Step "Checking Prometheus target API"
$prometheusTargets = Wait-Http -Url "http://localhost:$prometheusPort/api/v1/targets" -TimeoutSeconds 180
if ($prometheusTargets.Content -notmatch "smartclass-backend") {
    throw "Prometheus targets response does not include smartclass-backend."
}
Write-Host "Prometheus target response includes smartclass-backend."

Write-Step "Checking Grafana health"
$grafanaHealth = Wait-Http -Url "http://localhost:$grafanaPort/api/health" -TimeoutSeconds 180
Write-Host $grafanaHealth.Content

Write-Step "Scripted checks complete"
Write-Host "Manual checks still required: frontend login, /api calls, /api/chat/stream SSE, knowledge upload through MinIO, artifact download/HTML preview, and OnlyOffice save callback."
