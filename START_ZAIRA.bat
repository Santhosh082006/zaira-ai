@echo off
title Zaira AI — One-Click Launcher
echo =======================================================
echo          Starting Zaira AI Local Server Suite          
echo =======================================================
echo.

cd /d "%~dp0"

echo [1/3] Clearing any stale Next.js dev locks...
if exist "frontend\.next\dev\lock" del /f /q "frontend\.next\dev\lock" >nul 2>&1

echo [2/3] Launching FastAPI Backend (Port 8000)...
start "Zaira Backend (Port 8000)" cmd /k "title Zaira Backend && venv\Scripts\uvicorn.exe backend.api:app --host 127.0.0.1 --port 8000"

echo [3/3] Launching Next.js Frontend (Port 3000)...
start "Zaira Frontend (Port 3000)" cmd /k "title Zaira Frontend && cd frontend && npm run dev -- -H 127.0.0.1 -p 3000"

echo.
echo Waiting 5 seconds for servers to initialize...
timeout /t 5 /nobreak >nul

echo Opening browser at http://localhost:3000 ...
start http://localhost:3000

echo.
echo =======================================================
echo  Zaira is running! Keep the backend & frontend windows 
echo  open while using the application.
echo =======================================================
pause
