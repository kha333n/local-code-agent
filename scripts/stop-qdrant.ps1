param(
  [string]$ContainerName = "local-cursor-agent-qdrant"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker CLI not found; skipping Qdrant stop."
  exit 0
}

$existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if (-not $existing) {
  Write-Host "Qdrant container does not exist: $ContainerName"
  exit 0
}

$isRunning = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if ($isRunning) {
  docker stop $ContainerName | Out-Null
  Write-Host "Qdrant container stopped: $ContainerName"
} else {
  Write-Host "Qdrant not running: $ContainerName"
}
