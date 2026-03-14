@echo off
echo Installing Clinic Detector kiosk autostart...

:: Create shortcut in Windows Startup folder
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set TARGET=%~dp0run_kiosk.bat
set SHORTCUT=%STARTUP%\ClinicDetectorKiosk.lnk

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Save()"

if exist "%SHORTCUT%" (
    echo Autostart installed successfully!
    echo Shortcut: %SHORTCUT%
    echo The kiosk will start automatically on login.
) else (
    echo Failed to create shortcut.
)

echo.
echo To remove autostart, delete:
echo   %SHORTCUT%
echo.
pause
