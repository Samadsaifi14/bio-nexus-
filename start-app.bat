@echo off
cd /d "%~dp0bioai-platform\frontend"
start /min "Bio-Nexus Frontend" cmd /c "npm start"
cd /d "%~dp0bioai-platform\backend"
start /min "Bio-Nexus Backend" cmd /c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo Bio Nexus started successfully!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
