@echo off
REM Build GIF Maker as a standalone Windows .exe.
REM Run this on Windows, with Python 3.10+ and the dependencies installed:
REM   pip install -r requirements.txt pyinstaller
cd /d "%~dp0\.."

pyinstaller --noconfirm --clean --windowed --onefile --name "GIF Maker" ^
    --icon "assets\AppIcon.ico" ^
    --collect-all imageio_ffmpeg ^
    --collect-all imageio ^
    main.py

echo Executable created at dist\GIF Maker.exe
