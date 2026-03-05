param(
  [switch]$KeepQdrant
)

$ErrorActionPreference = "Stop"

function Stop-AgentByPidFile {
  param([string]$PidFilePath)

  if (-not (Test-Path $PidFilePath)) {
    return $false
  }

  $pidRaw = (Get-Content -Raw $PidFilePath).Trim()
  if (-not $pidRaw) {
    Remove-Item -Force $PidFilePath -ErrorAction SilentlyContinue
    return $false
  }

  $agentPid = [int]$pidRaw
  $proc = Get-Process -Id $agentPid -ErrorAction SilentlyContinue
  if ($proc) {
    Stop-Process -Id $agentPid -Force
    Write-Host "Stopped agent process $agentPid from PID file."
  } else {
    Write-Host "PID file found, but process $agentPid is not running."
  }

  Remove-Item -Force $PidFilePath -ErrorAction SilentlyContinue
  return $true
}

function Stop-AgentFallback {
  $found = $false
  $procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match "^python(\.exe)?$" -and
    $_.CommandLine -match "python(\.exe)?\s+-m\s+app" -and
    $_.CommandLine -match "local-cursor-agent"
  }

  foreach ($p in $procs) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped fallback agent process $($p.ProcessId)."
    $found = $true
  }
  return $found
}

Write-Host ""
Write-Host "========================================="
Write-Host " Stopping Local Cursor Agent Environment "
Write-Host "========================================="
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = (Resolve-Path (Join-Path $scriptDir "..")).Path
$runtimeDir = Join-Path $project ".runtime"
$pidFile = Join-Path $runtimeDir "agent.pid"

Write-Host "Stopping agent server..."
$stopped = Stop-AgentByPidFile -PidFilePath $pidFile
if (-not $stopped) {
  if (-not (Stop-AgentFallback)) {
    Write-Host "No running agent process found."
  }
}

if (-not $KeepQdrant) {
  Write-Host ""
  Write-Host "Stopping Qdrant..."
  & (Join-Path $scriptDir "stop-qdrant.ps1")
} else {
  Write-Host ""
  Write-Host "Qdrant left running because -KeepQdrant was provided."
}

Write-Host ""
Write-Host "Ollama remains running (recommended)."
Write-Host ""
Write-Host "System stopped."
Write-Host ""
