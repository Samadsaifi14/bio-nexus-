@echo off
cd /d "C:\Users\hp\Desktop\bio-nexus\bioai-platform\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
