# Bio Nexus - Auto-start script
# Run this once to register both servers in Windows startup

$frontendDir = Join-Path $PSScriptRoot "bioai-platform\frontend"
$backendDir = Join-Path $PSScriptRoot "bioai-platform\backend"

$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
  Write-Host "[ERROR] Backend venv not found: $backendPython" -ForegroundColor Red
  Write-Host "Run: python -m venv --system-site-packages .venv ; .venv\Scripts\python -m pip install -r requirements.txt"
  exit 1
}

Start-Process -WindowStyle Hidden -FilePath "npm" -ArgumentList "start" -WorkingDirectory $frontendDir
Start-Process -WindowStyle Hidden -FilePath $backendPython -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory $backendDir
