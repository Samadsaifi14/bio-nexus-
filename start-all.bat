@echo off
echo ========================================
echo   Bio Nexus - Starting All Services
echo ========================================
echo.

:: Start backend in new window
start "Bio Nexus Backend" cmd /c "cd /d "%~dp0bioai-platform\backend" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend in new window
start "Bio Nexus Frontend" cmd /c "cd /d "%~dp0bioai-platform\frontend" && npm start"

echo.
echo ========================================
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo ========================================
echo.
echo Close the server windows to stop.
pause
