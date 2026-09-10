# Conference Organizer

Manage speakers, schedule and abstracts for a seminar series or small
conference, on your own computer. No account, no server, no data sharing —
everything is stored in a single local file. Works the same way on
**macOS, Windows and Linux**.

## Installation

No technical knowledge or Python installation required:

1. Go to the **[Releases](https://github.com/J-Berat/LMPApp/releases)** tab of this repository.
2. Download the file for your system:
   - **macOS**: `ConferenceOrganizer-macOS.zip` → unzip, then drag `Conference Organizer.app` into your Applications folder.
   - **Windows**: `ConferenceOrganizer-Windows.zip` → unzip, then double-click `Conference Organizer.exe`.
   - **Linux**: `ConferenceOrganizer-Linux.zip` → unzip, make the file executable (`chmod +x "Conference Organizer"`), then run it.
3. On first launch, your OS may show a warning because the app isn't
   signed by a paid developer account (expected for a personal project):
   - **macOS**: the first time you open it, macOS will likely refuse,
     saying it "cannot be opened because it is from an unidentified
     developer" or that it "could not be verified... may be dangerous".
     This is expected for an app that isn't signed by a paid Apple
     developer account — it doesn't mean anything is actually wrong with
     the app. To get past it:
     - **Most reliable**: open Terminal and run
       `xattr -cr "/Applications/Conference Organizer.app"`, then open the app
       normally.
     - **Without Terminal**: try to open the app once (it will be
       blocked), then go to **System Settings → Privacy & Security**,
       scroll down to the notice about this app being blocked, and click
       **"Open Anyway"**.
   - **Windows**: click "More info" → "Run anyway" in the SmartScreen
     window.

Your data (speakers, sessions, abstracts) is saved automatically to a
local file the first time you launch the app — nothing to configure.

These installer files are built and published automatically for every new
release (see `.github/workflows/build.yml` at the repository root) —
there is never any compiling to do yourself just to use the application.

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
   cp -R "dist/Conference Organizer.app" /Applications/
   xattr -cr "/Applications/Conference Organizer.app"
   ```
