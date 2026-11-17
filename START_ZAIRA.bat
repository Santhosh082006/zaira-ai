@echo off
title Zaira AI Launcher

echo =======================================================
echo          Starting Zaira AI Local Server Suite          
echo =======================================================
echo.

cd /d "%~dp0"

REM 1. Verify Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from python.org and re-run.
    pause
    exit /b 1
)

REM 2. Check or Create Virtual Environment
if not exist "venv\Scripts\pip.exe" (
    echo [SETUP] Virtual environment not detected or incomplete. Creating .\venv ...
    if exist "venv" rd /s /q "venv" >nul 2>&1
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SETUP] Virtual environment created successfully.
    echo [SETUP] Installing backend dependencies...
    call venv\Scripts\python.exe -m pip install --upgrade pip
    call venv\Scripts\pip.exe install -r requirements.txt
)

REM 3. Check Uvicorn
if not exist "venv\Scripts\uvicorn.exe" (
    echo [SETUP] Installing uvicorn into venv...
    call venv\Scripts\pip.exe install uvicorn
)

REM 4. Check Node.js for Frontend
set NODE_OK=0
node --version >nul 2>&1
if not errorlevel 1 (
    set NODE_OK=1
)

if "%NODE_OK%"=="1" (
    if not exist "frontend\node_modules" (
        echo [SETUP] Installing frontend npm packages...
        cd frontend
        call npm install
        cd ..
    )
    if exist "frontend\.next\dev\lock" del /f /q "frontend\.next\dev\lock" >nul 2>&1
) else (
    echo [INFO] Node.js not detected in PATH.
    echo To use Next.js frontend, install Node.js from https://nodejs.org/
)

REM 5. Launch FastAPI Backend
echo.
echo [1/2] Launching FastAPI Backend on Port 8000...
start "Zaira Backend" cmd /k "title Zaira Backend && cd /d "%~dp0" && venv\Scripts\uvicorn.exe backend.api:app --host 0.0.0.0 --port 8000"

REM 6. Launch Next.js Frontend if Node is installed
if "%NODE_OK%"=="1" (
    echo [2/2] Launching Next.js Frontend on Port 3000...
    start "Zaira Frontend" cmd /k "title Zaira Frontend && cd /d "%~dp0frontend" && npm run dev -- -H 127.0.0.1 -p 3000"
    echo.
    echo Waiting 5 seconds for servers to initialize...
    ping 127.0.0.1 -n 6 >nul
    echo Opening browser at http://localhost:3000 ...
    start http://localhost:3000
) else (
    echo.
    echo Waiting 3 seconds for backend to initialize...
    ping 127.0.0.1 -n 4 >nul
    echo Opening backend API docs at http://localhost:8000/docs ...
    start http://localhost:8000/docs
)

echo.
echo =======================================================
echo  Zaira is starting! Keep this window open.
echo =======================================================
echo.
pause