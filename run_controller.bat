@echo off
title Robot Controller - 24/7
echo ==========================================
echo  Robot Controller (VLC + Webhook) - 24/7
echo ==========================================

set "PYTHON=C:\Users\citob\AppData\Local\Programs\Python\Python311\python.exe"
set "SCRIPT_DIR=C:\Users\citob\clinic-entrance-detector\"

:loop
echo.
echo [%date% %time%] Starting controller...
cd /d "%SCRIPT_DIR%"
"%PYTHON%" controller.py
echo.
echo [%date% %time%] Controller stopped (exit code: %ERRORLEVEL%). Restarting in 5 seconds...
echo Press Ctrl+C to stop.
timeout /t 5 /nobreak >nul
goto loop
