"""FITS Viewer - a quick-look viewer for FITS images and spectra.

Opens a FITS or HDF5 file, lets you pick the extension/dataset, adjust
the stretch and colormap (image) or view the flux curve (spectrum), and
browse the header/attributes - without needing DS9 or a full notebook
for a quick look.

Cross-platform desktop application (macOS, Windows, Linux).
"""

import os

# Make sure pyqtgraph picks the same Qt binding the rest of the app uses.
# Only an env var, no import: kept here (rather than in image_view.py)
# so it's set before ANY module imports pyqtgraph, while still letting
# pure-logic modules (fits_loader, hdf5_loader, image_stretch) be
# imported - and unit-tested - without pulling in pyqtgraph/Qt at all.
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

__version__ = "1.0.0"
