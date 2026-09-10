#!/usr/bin/env bash
# Build FITS Viewer as a standalone macOS application (.app).
# Run this on a Mac, with Python 3.10+ and the dependencies installed:
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --windowed --name "FITS Viewer" \
    --icon "assets/AppIcon.icns" \
    --collect-all astropy \
    --collect-all pyqtgraph \
    --collect-all h5py \
    main.py

echo "Application created at dist/FITS Viewer.app"
