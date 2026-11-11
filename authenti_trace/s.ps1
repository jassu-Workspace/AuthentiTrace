[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $root 'backend'
$frontendPath = Join-Path $root 'frontend'

if (-not (Test-Path $backendPath)) {
    throw "Backend directory not found: $backendPath"
}

if (-not (Test-Path $frontendPath)) {
    throw "Frontend directory not found: $frontendPath"
}

function Get-PythonExe {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return 'py'
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return 'python'
    }
    throw 'Python launcher not found. Install Python or ensure py/python is on PATH.'
}

$pyExe = Get-PythonExe

# Check frontend node_modules
if (-not (Test-Path (Join-Path $frontendPath 'node_modules'))) {
    Write-Host 'Frontend node_modules not detected. Installing dependencies...' -ForegroundColor Yellow
    Push-Location $frontendPath
    try {
        npm install
    } finally {
        Pop-Location
    }
}

# Launch Backend
if (-not $FrontendOnly) {
    Write-Host 'Starting AuthentiTrace Backend on http://127.0.0.1:8000 ...' -ForegroundColor Cyan
    $backendStartup = "`$host.UI.RawUI.WindowTitle = 'AuthentiTrace Backend (Port 8000)'; `$env:PYTHONPATH = '$backendPath'; Set-Location '$backendPath'; $pyExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
    Start-Process powershell -ArgumentList @('-NoExit', '-Command', $backendStartup)
    Start-Sleep -Seconds 2
}

# Launch Frontend
if (-not $BackendOnly) {
    Write-Host 'Starting AuthentiTrace Frontend on http://localhost:3000 ...' -ForegroundColor Green
    $frontendStartup = "`$host.UI.RawUI.WindowTitle = 'AuthentiTrace Frontend (Port 3000)'; Set-Location '$frontendPath'; npm run dev"
    Start-Process powershell -ArgumentList @('-NoExit', '-Command', $frontendStartup)
    Start-Sleep -Seconds 4
}

# Open Browser
if (-not $NoBrowser -and -not $BackendOnly) {
    Write-Host 'Opening AuthentiTrace in browser at http://localhost:3000 ...' -ForegroundColor Magenta
    Start-Process 'http://localhost:3000'
}

Write-Host 'AuthentiTrace startup complete.' -ForegroundColor Green
