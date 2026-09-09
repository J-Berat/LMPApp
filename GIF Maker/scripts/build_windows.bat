@echo off
REM Compile GIF Maker en .exe autonome pour Windows.
REM A executer sur Windows, avec Python 3.10+ et les dependances installees :
REM   pip install -r requirements.txt pyinstaller
cd /d "%~dp0\.."

pyinstaller --noconfirm --clean --windowed --onefile --name "GIF Maker" ^
    --icon "assets\AppIcon.ico" ^
    --collect-all imageio_ffmpeg ^
    --collect-all imageio ^
    main.py

echo Executable cree dans dist\GIF Maker.exe
