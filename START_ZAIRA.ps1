# Zaira AI - PowerShell Launcher
$Host.UI.RawUI.WindowTitle = "Zaira AI Launcher"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "         Starting Zaira AI Local Server Suite          " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = Get-Location }
Set-Location $ScriptDir

# Auto-detect Node.js path if not in current PowerShell session PATH
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    if (Test-Path "C:\Program Files\nodejs\node.exe") {
        $env:Path = "C:\Program Files\nodejs;$env:Path"
    } elseif (Test-Path "C:\Program Files (x86)\nodejs\node.exe") {
        $env:Path = "C:\Program Files (x86)\nodejs;$env:Path"
    }
}

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://python.org/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# 2. Check / Create venv
if (-not (Test-Path "$ScriptDir\venv\Scripts\pip.exe")) {
    Write-Host "[SETUP] Virtual environment not detected or incomplete. Creating .\venv ..." -ForegroundColor Yellow
    if (Test-Path "$ScriptDir\venv") { Remove-Item "$ScriptDir\venv" -Recurse -Force }
    python -m venv --system-site-packages venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[SETUP] Virtual environment created. Installing backend dependencies..." -ForegroundColor Yellow
    & "$ScriptDir\venv\Scripts\python.exe" -m pip install --upgrade pip
    & "$ScriptDir\venv\Scripts\pip.exe" install -r "$ScriptDir\requirements.txt"
}

# 3. Check Uvicorn
if (-not (Test-Path "$ScriptDir\venv\Scripts\uvicorn.exe")) {
    Write-Host "[SETUP] Installing uvicorn into venv..." -ForegroundColor Yellow
    & "$ScriptDir\venv\Scripts\pip.exe" install uvicorn
}

# 4. Check Node.js
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$hasNode = $false
if ($nodeCmd) {
    $hasNode = $true
    if (-not (Test-Path "$ScriptDir\frontend\node_modules")) {
        Write-Host "[SETUP] Installing frontend npm packages (this only happens once)..." -ForegroundColor Yellow
        Push-Location "$ScriptDir\frontend"
        npm install
        Pop-Location
    }
    if (Test-Path "$ScriptDir\frontend\.next\dev\lock") {
        Remove-Item "$ScriptDir\frontend\.next\dev\lock" -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "[INFO] Node.js is not found in PATH." -ForegroundColor Yellow
    Write-Host "To run the Next.js frontend, install Node.js 18+ from https://nodejs.org/" -ForegroundColor DarkGray
    Write-Host "FastAPI Backend is starting on http://127.0.0.1:8000" -ForegroundColor Green
}

# 5. Launch Backend
Write-Host ""
Write-Host "[1/2] Launching FastAPI Backend on Port 8000..." -ForegroundColor Green
Start-Process cmd.exe -ArgumentList "/k", "title Zaira Backend && cd /d `"$ScriptDir`" && `"$ScriptDir\venv\Scripts\uvicorn.exe`" backend.api:app --host 0.0.0.0 --port 8000"

# 6. Launch Frontend if Node available
if ($hasNode) {
    Write-Host "[2/2] Launching Next.js Frontend on Port 3000..." -ForegroundColor Green
    Start-Process cmd.exe -ArgumentList "/k", "title Zaira Frontend && cd /d `"$ScriptDir\frontend`" && npm run dev -- -H 127.0.0.1 -p 3000"
    Write-Host "Waiting 5 seconds for servers to initialize..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
    Start-Process "http://localhost:3000"
} else {
    Write-Host "Waiting 3 seconds for backend to initialize..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8000/docs"
}

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host " Zaira is starting! Keep the server windows open.      " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
