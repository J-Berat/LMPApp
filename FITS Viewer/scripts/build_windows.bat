@echo off
REM Build FITS Viewer as a standalone Windows .exe.
REM Run this on Windows, with Python 3.10+ and the dependencies installed:
REM   pip install -r requirements.txt pyinstaller
cd /d "%~dp0\.."

pyinstaller --noconfirm --clean --windowed --onefile --name "FITS Viewer" ^
    --icon "assets\AppIcon.ico" ^
    --collect-all astropy ^
    --collect-all pyqtgraph ^
    --collect-all h5py ^
    main.py

echo Executable created at dist\FITS Viewer.exe
