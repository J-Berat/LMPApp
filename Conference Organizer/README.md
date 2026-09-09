# Conference Organizer

Manage speakers, schedule and abstracts for a seminar series or small
conference, on your own computer. No account, no server, no data sharing —
everything is stored in a single local file. Works the same way on
**macOS, Windows and Linux**.

## Installation

No technical knowledge or Python installation required:

1. Go to the **[Releases](../../releases)** tab of this repository.
2. Download the file for your system:
   - **macOS**: `ConferenceOrganizer-macOS.zip` → unzip, then drag `Conference Organizer.app` into your Applications folder.
   - **Windows**: `ConferenceOrganizer-Windows.zip` → unzip, then double-click `Conference Organizer.exe`.
   - **Linux**: `ConferenceOrganizer-Linux.zip` → unzip, make the file executable (`chmod +x "Conference Organizer"`), then run it.
3. On first launch, your OS may show a warning because the app isn't
   signed by a paid developer account (expected for a personal project):
   - **macOS**: right-click the app → "Open", then confirm. If you see a
     "damaged app" message, open Terminal and run:
     `xattr -cr "/Applications/Conference Organizer.app"`
   - **Windows**: click "More info" → "Run anyway" in the SmartScreen
     window.

Your data (speakers, sessions, abstracts) is saved automatically to a
local file the first time you launch the app — nothing to configure.

These installer files are built and published automatically for every new
release (see `.github/workflows/build.yml` at the repository root) —
there is never any compiling to do yourself just to use the application.
