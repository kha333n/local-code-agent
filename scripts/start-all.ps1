param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 3210,
  [switch]$SkipWarmup
)

$ErrorActionPreference = "Stop"

function Wait-HttpReady {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$Retries = 30,
    [int]$DelaySeconds = 2
  )

  for ($i = 0; $i -lt $Retries; $i++) {
    try {
      $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
      return $true
    } catch {
      Start-Sleep -Seconds $DelaySeconds
    }
  }
  return $false
}

function Get-AgentProcessByPort {
  param([int]$LocalPort)
  try {
    $conn = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $LocalPort -State Listen -ErrorAction Stop | Select-Object -First 1
    if ($conn) {
      return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    }
  } catch {}
  return $null
}

function Write-Banner {
  Write-Host ""
  Write-Host "========================================="
  Write-Host " Starting Local Cursor Agent Environment "
  Write-Host "========================================="
  Write-Host ""
}

Write-Banner

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = (Resolve-Path (Join-Path $scriptDir "..")).Path
$runtimeDir = Join-Path $project ".runtime"
$pidFile = Join-Path $runtimeDir "agent.pid"
$logDir = Join-Path $runtimeDir "logs"
$outLog = Join-Path $logDir "agent.out.log"
$errLog = Join-Path $logDir "agent.err.log"

New-Item -ItemType Directory -Force $runtimeDir | Out-Null
New-Item -ItemType Directory -Force $logDir | Out-Null

Set-Location $project

Write-Host "Starting Qdrant..."
& (Join-Path $scriptDir "start-qdrant.ps1")

Write-Host "Waiting for Qdrant to be ready..."
if (Wait-HttpReady -Url "http://127.0.0.1:6333/collections" -Retries 25 -DelaySeconds 2) {
  Write-Host "Qdrant is ready."
} else {
  Write-Host "WARNING: Qdrant readiness check timed out."
}

Write-Host ""
Write-Host "Checking Ollama..."
if (Wait-HttpReady -Url "http://127.0.0.1:11434/api/tags" -Retries 15 -DelaySeconds 2) {
  Write-Host "Ollama is running."
} else {
  Write-Host "WARNING: Ollama API not responding."
}

Write-Host ""
Write-Host "Starting Agent Server..."

$existing = Get-AgentProcessByPort -LocalPort $Port
if ($existing) {
  Write-Host "Agent already listening on $BindHost`:$Port (PID: $($existing.Id))."
  Set-Content -Path $pidFile -Value $existing.Id -Encoding ascii
} else {
  $env:AGENT_HOST = $BindHost
  $env:AGENT_PORT = $Port
  $env:LOCAL_AGENT_HOST = $BindHost
  $env:LOCAL_AGENT_PORT = $Port

  $proc = Start-Process `
    -FilePath "python" `
    -ArgumentList "-m app" `
    -WorkingDirectory $project `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

  Set-Content -Path $pidFile -Value $proc.Id -Encoding ascii
  Write-Host "Agent process started (PID: $($proc.Id))."
}

Write-Host "Waiting for Agent API..."
$healthUrl = "http://$BindHost`:$Port/healthz"
if (Wait-HttpReady -Url $healthUrl -Retries 30 -DelaySeconds 2) {
  Write-Host "Agent API is ready."
} else {
  Write-Host "Agent not responding yet. Check logs:"
  Write-Host $outLog
  Write-Host $errLog
}

if (-not $SkipWarmup) {
  Write-Host ""
  Write-Host "Warming up model (optional)..."
  try {
    $body = @{
      model = "qwen2.5-coder:7b"
      messages = @(@{ role = "user"; content = "hello" })
      stream = $false
    } | ConvertTo-Json -Depth 5

    Invoke-RestMethod `
      -Uri "http://127.0.0.1:11434/api/chat" `
      -Method Post `
      -ContentType "application/json" `
      -Body $body | Out-Null

    Write-Host "Model warmed up."
  } catch {
    Write-Host "Model warmup skipped."
  }
}

Write-Host ""
Write-Host "================================="
Write-Host " System Ready"
Write-Host ""
Write-Host "API Endpoint:"
Write-Host "http://$BindHost`:$Port/v1"
Write-Host ""
Write-Host "Health:"
Write-Host "http://$BindHost`:$Port/healthz"
Write-Host ""
Write-Host "Logs:"
Write-Host $outLog
Write-Host $errLog
Write-Host ""
Write-Host "================================="
