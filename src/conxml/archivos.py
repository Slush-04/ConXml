"""Apertura local multiplataforma, sin pasar rutas por un shell."""
import os
import subprocess
import sys
from pathlib import Path


def abrir_local(ruta: str | Path) -> None:
    ruta = Path(ruta).resolve()
    if sys.platform == 'win32':
        os.startfile(str(ruta))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(ruta)])
