"""Configuración local de paths y parámetros del sistema."""

from __future__ import annotations

import os
import sys
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Rutas del sistema.

    En un ejecutable empaquetado (PyInstaller):
    - En macOS (.app bundle o binario): se utiliza ~/Library/Application Support/ConXml
      para cumplir con los permisos del sistema operativo y no alterar el bundle.
    - En Windows: %LOCALAPPDATA%/ConXml/data, persistente y escribible por usuario.
    - En Linux: datos junto al ejecutable.
    - Se puede sobreescribir la ruta mediante la variable de entorno CONXML_DATA_DIR.
    """

    @property
    def base(self) -> Path:
        env_dir = os.environ.get("CONXML_DATA_DIR")
        if env_dir:
            return Path(env_dir).resolve()
        if getattr(sys, "frozen", False):
            if sys.platform == "win32":
                base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ConXml" / "data"
                migrar_datos_windows(Path(sys.executable).resolve().parent / "data", base)
                return base
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

    def inicializar(self) -> None:
        for ruta in (self.base, self.carpeta_entrada, self.carpeta_boveda,
                     self.carpeta_zip_sat, self.respaldos):
            ruta.mkdir(parents=True, exist_ok=True)


def migrar_datos_windows(anterior: Path, destino: Path) -> None:
    """Copia instalaciones anteriores sin modificar el original ni mezclar catálogos.

    Los paths XML absolutos antiguos siguen apuntando al original, que se conserva.
    Una carpeta persistente existente siempre tiene prioridad.
    """
    if destino.exists() or not anterior.is_dir() or anterior.resolve() == destino.resolve():
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".migracion-", dir=destino.parent))
    try:
        shutil.copytree(anterior, stage, dirs_exist_ok=True)
        stage.rename(destino)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
