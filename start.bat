@echo off
title Arogya Path - SGMH Rewa
cd /d "%~dp0"
where python >nul 2>nul || (echo Python not found. Install Python and tick Add to PATH, then run again. & pause & exit /b 1)
if not exist venv\Scripts\python.exe (
  echo Creating Python virtual environment...
  python -m venv venv
)
echo Checking Python packages...
venv\Scripts\python.exe -m pip install -q -r requirements.txt
echo.
echo Starting server. Open http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop.
start "" http://127.0.0.1:5000
venv\Scripts\python.exe app.py
pause
