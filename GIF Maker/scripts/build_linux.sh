#!/usr/bin/env bash
# Compile GIF Maker en exécutable Linux autonome.
# À exécuter sur Linux, avec Python 3.10+ et les dépendances installées :
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --onefile --name "GIF Maker" \
    --icon "assets/AppIcon.png" \
    --collect-all imageio_ffmpeg \
    --collect-all imageio \
    main.py

echo "Exécutable créé dans dist/GIF Maker"
