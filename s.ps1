$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectScript = Join-Path $root 'authenti_trace\s.ps1'

if (-not (Test-Path $projectScript)) {
    throw "Target script not found: $projectScript"
}

& $projectScript
