"""Configuración local de paths y parámetros del sistema."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Rutas del sistema.

    En un ejecutable empaquetado (PyInstaller) los datos se guardan junto al
    .exe para que la herramienta sea independiente y portátil.
    """

    @property
    def base(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent / "data"
        return Path("data")

    @property
    def db_path(self) -> Path:
        return self.base / "catalogo.db"

    @property
    def carpeta_entrada(self) -> Path:
        return self.base / "muestra"