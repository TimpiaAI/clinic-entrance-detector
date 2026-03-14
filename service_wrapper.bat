@echo off
cd /d C:\Users\citob\clinic-entrance-detector
:loop
python main.py >> logs\service.log 2>&1
echo [%date% %time%] Detector stopped, restarting in 5 seconds... >> logs\service.log
timeout /t 5 /nobreak >/dev/null
goto loop
