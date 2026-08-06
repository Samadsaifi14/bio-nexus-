@echo off
cd /d "%~dp0bioai-platform\backend"
set "PY=%~dp0bioai-platform\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ERROR] Backend venv not found at %PY%
  echo Run:  python -m venv --system-site-packages .venv
  echo        .venv\Scripts\python -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo Starting Bio Nexus Backend (venv)...
echo API running at http://localhost:8000
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
