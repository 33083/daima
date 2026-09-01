@echo off
title CodeRAG Stop

echo ============================================
echo   CodeRAG - Stop All Services
echo ============================================
echo.

echo Stopping backend (uvicorn)...
taskkill /fi "WINDOWTITLE eq CodeRAG Backend*" /f >nul 2>&1

echo Stopping frontend (vite)...
taskkill /fi "WINDOWTITLE eq CodeRAG Frontend*" /f >nul 2>&1

echo.
echo All services stopped.
echo.
pause
