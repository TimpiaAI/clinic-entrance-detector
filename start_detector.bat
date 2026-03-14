@echo off
cd /d C:\Users\citob\clinic-entrance-detector
echo Starting detector... webcam takes ~30 seconds to initialize.
echo Please wait...
C:\Users\citob\AppData\Local\Programs\Python\Python311\python.exe main.py --show-window
pause
