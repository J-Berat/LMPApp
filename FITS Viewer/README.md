# FITS Viewer

A quick-look viewer for FITS images and spectra: open a file, adjust the
stretch and colormap (or view the flux curve for a spectrum), and browse
the header — without needing DS9 or a full notebook just to take a look.
Works the same way on **macOS, Windows and Linux**.

## Installation

No technical knowledge or Python installation required:

1. Go to the **[Releases](../../releases)** tab of this repository.
2. Download the file for your system:
   - **macOS**: `FITS-Viewer-macOS.zip` → unzip, then drag `FITS Viewer.app` into your Applications folder.
   - **Windows**: `FITS-Viewer-Windows.zip` → unzip, then double-click `FITS Viewer.exe`.
   - **Linux**: `FITS-Viewer-Linux.zip` → unzip, make the file executable (`chmod +x "FITS Viewer"`), then run it.
3. On first launch, your OS may show a warning because the app isn't
   signed by a paid developer account (expected for a personal project):
   - **macOS**: right-click the app → "Open", then confirm. If you see a
     "damaged app" message, open Terminal and run:
     `xattr -cr "/Applications/FITS Viewer.app"`
   - **Windows**: click "More info" → "Run anyway" in the SmartScreen
     window.

These files are built and published automatically for every new release
(see `.github/workflows/build.yml` at the repository root) — there is
never any compiling to do yourself just to use the application.

## Building from source

If you want to build the app yourself from the current code instead of
waiting for a released version:

1. Make sure Python 3.10+ is installed.
2. Open a terminal in this folder and set up a virtual environment
   (skip this step if you already have one):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt pyinstaller
   ```
3. Build the app for your system (run from this folder, not from
   inside `scripts/`):
   - **macOS**: `bash scripts/build_mac.sh`
   - **Windows**: `scripts\build_windows.bat`
   - **Linux**: `bash scripts/build_linux.sh`
4. The application is created inside the `dist/` folder. On macOS,
   install it with:
   ```bash
   cp -R "dist/FITS Viewer.app" /Applications/
   xattr -cr "/Applications/FITS Viewer.app"
   ```
