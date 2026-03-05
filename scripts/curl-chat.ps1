param(
  [Parameter(Mandatory = $true)]
  [string]$Workspace,
  [Parameter(Mandatory = $true)]
  [string]$Message,
  [string]$BaseUrl = "http://127.0.0.1:3210"
)

function Resolve-WorkspaceAuthorization {
  param(
    [string]$Ws,
    [string]$ApiBase
  )

  Write-Host "Allow workspace?"
  Write-Host "[1] Allow once"
  Write-Host "[2] Allow always"
  Write-Host "[3] Deny"
  $choice = Read-Host "Choose"

  if ($choice -eq "3") {
    throw "Workspace denied by user"
  }

  $action = if ($choice -eq "2") { "allow_always" } else { "allow_once" }
  $authBody = @{ workspace = $Ws; action = $action; allowed_commands = @("php", "composer") } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri "$ApiBase/workspace/authorize" -ContentType "application/json" -Body $authBody | Out-Null
}

$bodyObj = @{
  model = "local-qwen2.5-coder-7b-rag"
  workspace = $Workspace
  messages = @(
    @{ role = "user"; content = $Message }
  )
}
$body = $bodyObj | ConvertTo-Json -Depth 8

try {
  $res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/chat/completions" -ContentType "application/json" -Body $body
  $res | ConvertTo-Json -Depth 8
} catch {
  $errorBody = $_.ErrorDetails.Message
  if ($errorBody -match "workspace_not_registered") {
    Resolve-WorkspaceAuthorization -Ws $Workspace -ApiBase $BaseUrl
    $retry = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/chat/completions" -ContentType "application/json" -Body $body
    $retry | ConvertTo-Json -Depth 8
  } else {
    throw
  }
}
