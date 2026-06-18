@echo off
cd /d "%~dp0bioai-platform\backend"
call .venv\Scripts\activate.bat 2>nul || echo No .venv found, using system Python
echo Starting Bio Nexus Backend...
echo API running at http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
