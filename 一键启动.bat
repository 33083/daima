@echo off
title CodeRAG Launcher

echo ============================================
echo   CodeRAG - Code Repository RAG Assistant
echo   One-Click Launcher
echo ============================================
echo.

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.10+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found! Please install Node.js 18+
    echo Download: https://nodejs.org/
    pause
    exit /b 1
)

:: Check .env file
if not exist "backend\.env" (
    echo [WARNING] backend\.env not found!
    echo Please copy backend\.env.example to backend\.env and fill in API Key
    pause
    exit /b 1
)

:: Check API Key
findstr /c:"YOUR_API_KEY" "backend\.env" >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Please fill in real API Key in backend\.env first!
    pause
    exit /b 1
)

echo [1/4] Checking Python venv...
if not exist "backend\venv" (
    echo   Creating venv...
    cd backend
    python -m venv venv
    cd ..
    echo   venv created
) else (
    echo   venv exists
)

echo.
echo [2/4] Installing backend deps...
cd backend
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
cd ..

echo.
echo [3/4] Installing frontend deps...
if not exist "frontend\node_modules" (
    cd frontend
    call npm install
    cd ..
) else (
    echo   frontend deps already installed, skip
)

echo.
echo [4/4] Starting services...
echo.
echo ============================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Doc:  http://localhost:8000/docs
echo.
echo   Close the windows to stop services
echo ============================================
echo.

:: Start backend in new window
start "CodeRAG Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: Start frontend in new window
start "CodeRAG Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: Wait 5s then open browser
timeout /t 5 /nobreak >nul
start http://localhost:5173

echo.
echo Services started!
echo   Backend window:  CodeRAG Backend
echo   Frontend window: CodeRAG Frontend
echo.
pause
