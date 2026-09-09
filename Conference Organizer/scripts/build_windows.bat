@echo off
REM Build Conference Organizer as a standalone Windows .exe.
REM Run this on Windows, with Python 3.10+ and the dependencies installed:
REM   pip install -r requirements.txt pyinstaller
cd /d "%~dp0\.."

pyinstaller --noconfirm --clean --windowed --onefile --name "Conference Organizer" ^
    --icon "assets\AppIcon.ico" ^
    main.py

echo Executable created at dist\Conference Organizer.exe
