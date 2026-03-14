@echo off
title Clinic Entrance Detector - Kiosk 24/7
cd /d "%~dp0"

echo ============================================
echo  Clinic Entrance Detector - KIOSK 24/7
echo  Ctrl+Shift+K in browser = exit kiosk
echo  Ctrl+C here = stop everything
echo ============================================
echo.

:: Prevent Windows sleep/screen off
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change monitor-timeout-dc 0

:: Kill any leftover python processes from previous runs
taskkill /F /IM python.exe >nul 2>&1

:restart_loop
echo.
echo [%date% %time%] Starting detector...
start /B python main.py > detector_kiosk.log 2>&1

:: Wait for dashboard to be ready (up to 2 minutes)
echo Waiting for dashboard...
set /a retries=0
:wait_loop
timeout /t 3 /nobreak >nul
curl -s http://localhost:8080/api/state >nul 2>&1
if not errorlevel 1 goto dashboard_ready
set /a retries+=1
if %retries% GEQ 40 (
    echo Dashboard failed to start after 2 minutes, restarting...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 5 /nobreak >nul
    goto restart_loop
)
goto wait_loop

:dashboard_ready
echo [%date% %time%] Dashboard ready!

:: Wait for YOLO model to load
timeout /t 5 /nobreak >nul

:: Launch browser in kiosk mode (only if not already open)
tasklist /FI "WINDOWTITLE eq *kiosk*" 2>nul | find /i "msedge" >nul
if errorlevel 1 (
    echo Launching kiosk browser...
    if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
        start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk --disable-infobars --disable-session-crashed-bubble --noerrdialogs --disable-translate --no-first-run --start-fullscreen "http://localhost:8080/?kiosk"
    ) else if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
        start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk --disable-infobars --disable-session-crashed-bubble --noerrdialogs --no-first-run --start-fullscreen "http://localhost:8080/?kiosk"
    ) else (
        start "" msedge --kiosk --start-fullscreen "http://localhost:8080/?kiosk"
    )
)

echo [%date% %time%] System running - monitoring...
echo.

:: Monitor loop - check every 30s, restart if detector dies
:monitor_loop
timeout /t 30 /nobreak >nul
curl -s http://localhost:8080/api/state >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] Detector crashed! Restarting in 5 seconds...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 5 /nobreak >nul
    goto restart_loop
)
goto monitor_loop
