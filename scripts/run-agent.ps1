param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 3210
)

$env:AGENT_HOST = $BindHost
$env:AGENT_PORT = $Port
$env:LOCAL_AGENT_HOST = $BindHost
$env:LOCAL_AGENT_PORT = $Port
python -m app
