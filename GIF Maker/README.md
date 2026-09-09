# GIF Maker

Application de bureau pour transformer une séquence d'images en GIF animé
ou en vidéo MP4. Fonctionne à l'identique sur **macOS, Windows et Linux**.

## Installation (pour tout le monde)

Aucune connaissance technique ni installation de Python n'est nécessaire :

1. Va dans l'onglet **[Releases](../../releases)** de ce dépôt.
2. Télécharge le fichier correspondant à ton système :
   - **macOS** : `GIF-Maker-macOS.zip` → dézippe, puis glisse `GIF Maker.app` dans le dossier Applications.
   - **Windows** : `GIF-Maker-Windows.zip` → dézippe, puis double-clique sur `GIF Maker.exe`.
   - **Linux** : `GIF-Maker-Linux.zip` → dézippe, rends le fichier exécutable (`chmod +x "GIF Maker"`), puis lance-le.
3. Au premier lancement, l'OS peut afficher un avertissement car l'application
   n'est pas signée par un développeur payant (normal pour un projet
   personnel) :
   - **macOS** : clic droit sur l'app → "Ouvrir", puis confirmer. Si un
     message "application endommagée" apparaît, ouvrir Terminal et lancer :
     `xattr -cr "/Applications/GIF Maker.app"`
   - **Windows** : "Informations complémentaires" → "Exécuter quand même"
     dans la fenêtre SmartScreen.

Ces fichiers sont générés et republiés automatiquement à chaque nouvelle
version (voir `.github/workflows/build.yml`), il n'y a jamais de
compilation à faire soi-même pour simplement utiliser l'application.

## Fonctionnalités

- Ajout d'images par glisser-déposer ou via un sélecteur de fichiers
- Réorganisation de la séquence (glisser-déposer dans la liste)
- Suppression d'images individuelles ou de toute la séquence
- Aperçu animé en temps réel, avec lecture/pause
- Réglages : délai entre les images, boucle infinie ou lecture unique,
  redimensionnement (avec ou sans conservation des proportions)
- Export en **GIF animé** (via Pillow)
- Export en **vidéo MP4** (H.264, via un ffmpeg embarqué — aucune
  installation système requise)

## Pour les développeurs

### Lancer depuis le code source

Nécessite Python 3.10 ou plus récent. Sur macOS (Homebrew) et les
distributions Linux récentes, Python est « externally managed » : utilisez
un environnement virtuel :

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python3 main.py
```

### Compiler soi-même un exécutable

Chaque système d'exploitation doit compiler son propre exécutable (pas de
compilation croisée). Installez PyInstaller (`pip install pyinstaller`)
puis lancez le script de la plateforme concernée :

| Plateforme | Commande                    | Résultat              |
|------------|------------------------------|------------------------|
| macOS      | `./scripts/build_mac.sh`     | `dist/GIF Maker.app`   |
| Linux      | `./scripts/build_linux.sh`   | `dist/GIF Maker`       |
| Windows    | `scripts\build_windows.bat`  | `dist\GIF Maker.exe`   |

### Publier une nouvelle version (déclenche la compilation automatique)

```bash
git tag gif-maker-v1.0.1
git push origin gif-maker-v1.0.1
```

GitHub Actions compile alors les trois versions et crée automatiquement
une Release avec les trois fichiers `.zip` prêts à télécharger.

### Structure du projet

```
gifmaker/
  model.py           # Modèle de données (images, réglages)
  gif_exporter.py    # Export GIF (Pillow)
  video_exporter.py  # Export MP4 (imageio + ffmpeg embarqué)
  main_window.py      # Interface graphique PySide6
main.py               # Point d'entrée
scripts/               # Scripts de compilation par plateforme
.github/workflows/     # Compilation + publication automatique des releases
```

## Historique

La version précédente de cette application (macOS uniquement, SwiftUI)
avait été perdue : seul le binaire compilé restait installé, sans son code
source. Cette version Python reproduit les mêmes fonctionnalités et ajoute
le support Windows/Linux, l'export MP4, et une distribution automatisée
via GitHub Releases.
