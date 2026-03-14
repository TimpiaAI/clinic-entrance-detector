@echo off
echo ==========================================
echo  Clinic System - Single Process Mode
echo ==========================================
echo.

set "SCRIPT_DIR=C:\Users\citob\clinic-entrance-detector\"

echo Starting detector + controller on port 8080...
echo  - Dashboard:  http://localhost:8080
echo  - Player:     http://localhost:8080/player
echo  - Admin:      http://localhost:8080/admin
echo.

:: Open player in Chrome fullscreen after a short delay
start "" cmd /c "timeout /t 8 /nobreak >nul && start chrome --kiosk http://localhost:8080/player"

cd /d "%SCRIPT_DIR%"
python main.py --show-window --controller
