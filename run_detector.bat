@echo off
title Clinic Entrance Detector - 24/7
echo ==========================================
echo  Clinic Entrance Detector - 24/7 Mode
echo ==========================================

set "PYTHON=C:\Users\citob\AppData\Local\Programs\Python\Python311\python.exe"
set "SCRIPT_DIR=C:\Users\citob\clinic-entrance-detector\"

:loop
echo.
echo [%date% %time%] Starting detector...
cd /d "%SCRIPT_DIR%"
"%PYTHON%" main.py --show-window
echo.
echo [%date% %time%] Detector stopped (exit code: %ERRORLEVEL%). Restarting in 5 seconds...
echo Press Ctrl+C to stop.
timeout /t 5 /nobreak >nul
goto loop
