# Bio Nexus - Auto-start script
# Run this once to register both servers in Windows startup

$frontendDir = Join-Path $PSScriptRoot "bioai-platform\frontend"
$backendDir = Join-Path $PSScriptRoot "bioai-platform\backend"

Start-Process -WindowStyle Hidden -FilePath "npm" -ArgumentList "start" -WorkingDirectory $frontendDir
Start-Process -WindowStyle Hidden -FilePath "python" -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory $backendDir
