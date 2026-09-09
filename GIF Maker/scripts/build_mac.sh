#!/usr/bin/env bash
# Compile GIF Maker en application macOS autonome (.app).
# À exécuter sur un Mac, avec Python 3.10+ et les dépendances installées :
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --windowed --name "GIF Maker" \
    --icon "assets/AppIcon.icns" \
    --collect-all imageio_ffmpeg \
    --collect-all imageio \
    main.py

echo "Application créée dans dist/GIF Maker.app"
