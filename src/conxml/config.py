"""Configuración local de paths y parámetros del sistema."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Rutas del sistema.

    En un ejecutable empaquetado (PyInstaller):
    - En macOS (.app bundle o binario): se utiliza ~/Library/Application Support/ConXml
      para cumplir con los permisos del sistema operativo y no alterar el bundle.
    - En Windows / Linux: los datos se guardan junto al ejecutable para máxima portabilidad.
    - Se puede sobreescribir la ruta mediante la variable de entorno CONXML_DATA_DIR.
    """

    @property
    def base(self) -> Path:
        env_dir = os.environ.get("CONXML_DATA_DIR")
        if env_dir:
            return Path(env_dir).resolve()
        if getattr(sys, "frozen", False):
            if sys.platform == "darwin":
                app_support = Path.home() / "Library" / "Application Support" / "ConXml"
                app_support.mkdir(parents=True, exist_ok=True)
                return app_support
            return Path(sys.executable).resolve().parent / "data"
        return Path(__file__).resolve().parents[2] / "data"

    @property
    def db_path(self) -> Path:
        return self.base / "catalogo.db"

    @property
    def carpeta_entrada(self) -> Path:
        return self.base / "muestra"

    @property
    def carpeta_boveda(self) -> Path:
        """Raíz del archivo organizado de XML por cliente, tipo y periodo."""
        destino = self.opciones_descarga_sat.get("carpeta_xml")
        return Path(destino).expanduser().resolve() if destino else self.base / "boveda"

    @property
    def opciones_descarga_sat(self) -> dict:
        from conxml.estado_local import cargar
        opciones = cargar(self.preferencias_path).get("descargas_sat", {})
        return opciones if isinstance(opciones, dict) else {}

    @property
    def modo_descarga_sat(self) -> str:
        return "zip" if self.opciones_descarga_sat.get("modo") == "zip" else "organizado"

    @property
    def carpeta_zip_sat(self) -> Path:
        destino = self.opciones_descarga_sat.get("carpeta_zip")
        return Path(destino).expanduser().resolve() if destino else self.base / "descargas_sat"

    @property
    def preferencias_path(self) -> Path:
        """Preferencias locales de la interfaz, separadas del catálogo SQLite."""
        return self.base / "preferencias.json"

    @property
    def respaldos(self) -> Path:
        return self.base / "respaldos"
