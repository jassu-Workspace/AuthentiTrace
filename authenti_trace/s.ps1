$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $root 'backend'
$frontendPath = Join-Path $root 'frontend'

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return 'py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload'
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload'
    }

    throw 'Python launcher not found. Install Python or ensure py/python is on PATH.'
}

if (-not (Test-Path $backendPath)) {
    throw "Backend directory not found: $backendPath"
}

if (-not (Test-Path $frontendPath)) {
    throw "Frontend directory not found: $frontendPath"
}

$backendCommand = Get-PythonCommand
$backendStartup = "Set-Location '$backendPath'; $backendCommand"
$frontendStartup = "Set-Location '$frontendPath'; npm run dev"

Write-Host 'Starting backend server on http://127.0.0.1:8000 ...'
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $backendStartup)

Start-Sleep -Seconds 2

Write-Host 'Starting frontend server on http://localhost:3000 ...'
Start-Process powershell -ArgumentList @('-NoExit', '-Command', $frontendStartup)

Start-Sleep -Seconds 6

Write-Host 'Opening browser at http://localhost:3000 ...'
Start-Process 'http://localhost:3000'

Write-Host 'AuthentiTrace startup script completed.'
