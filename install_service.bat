@echo off
:: Must run as Administrator
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Run this as Administrator!
    echo Right-click -> Run as administrator
    pause
    exit /b 1
)

cd /d "%~dp0"

echo ============================================
echo  Installing ClinicDetector Windows Service
echo ============================================

:: Remove old service if exists
nssm.exe stop ClinicDetector >nul 2>&1
nssm.exe remove ClinicDetector confirm >nul 2>&1

:: Find python path
for /f "tokens=*" %%i in ('where python') do set PYTHON=%%i
echo Python: %PYTHON%

:: Install service
nssm.exe install ClinicDetector "%PYTHON%" "main.py"
nssm.exe set ClinicDetector AppDirectory "%~dp0"
nssm.exe set ClinicDetector DisplayName "Clinic Entrance Detector"
nssm.exe set ClinicDetector Description "Clinic entrance detection and patient signin system"
nssm.exe set ClinicDetector Start SERVICE_AUTO_START
nssm.exe set ClinicDetector AppStdout "%~dp0logs\service_stdout.log"
nssm.exe set ClinicDetector AppStderr "%~dp0logs\service_stderr.log"
nssm.exe set ClinicDetector AppStdoutCreationDisposition 4
nssm.exe set ClinicDetector AppStderrCreationDisposition 4
nssm.exe set ClinicDetector AppRotateFiles 1
nssm.exe set ClinicDetector AppRotateBytes 10485760
:: Auto-restart on failure (wait 5 seconds)
nssm.exe set ClinicDetector AppExit Default Restart
nssm.exe set ClinicDetector AppRestartDelay 5000

:: Create logs directory
if not exist "%~dp0logs" mkdir "%~dp0logs"

:: Disable sleep
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0

:: Start the service
nssm.exe start ClinicDetector

echo.
echo ============================================
echo  Service installed and started!
echo  - Auto-starts on Windows boot
echo  - Auto-restarts if it crashes (5s delay)
echo  - Logs: %~dp0logs\
echo  - To stop: nssm stop ClinicDetector
echo  - To remove: nssm remove ClinicDetector confirm
echo ============================================
pause
