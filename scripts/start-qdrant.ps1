param(
  [string]$ContainerName = "local-cursor-agent-qdrant"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker CLI not found. Install Docker Desktop and ensure 'docker' is on PATH."
}

try {
  docker info | Out-Null
} catch {
  throw "Docker daemon is not running. Start Docker Desktop first."
}

$existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if (-not $existing) {
  docker run -d --name $ContainerName -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest | Out-Null
  Write-Host "Qdrant started in new container: $ContainerName"
  exit 0
}

$isRunning = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $ContainerName }
if (-not $isRunning) {
  docker start $ContainerName | Out-Null
  Write-Host "Qdrant container started: $ContainerName"
} else {
  Write-Host "Qdrant already running: $ContainerName"
}
