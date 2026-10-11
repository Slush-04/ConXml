"""Configuración local de paths y parámetros del sistema."""

from __future__ import annotations

import os
import json
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
    - La ubicación elegida en el primer inicio se recuerda fuera del directorio de datos.
    - En Windows, instalaciones anteriores conservan %LOCALAPPDATA%/ConXml/data.
    - En Linux: datos junto al ejecutable.
    - Se puede sobreescribir la ruta mediante la variable de entorno CONXML_DATA_DIR.
    """

    @property
    def base(self) -> Path:
        env_dir = os.environ.get("CONXML_DATA_DIR")
        if env_dir:
            return Path(env_dir).resolve()
        if getattr(sys, "frozen", False):
            seleccion = self.ubicacion_guardada
            if seleccion is not None:
                return seleccion
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
    def ubicacion_path(self) -> Path:
        """Registro independiente de los datos y de la versión instalada."""
        if sys.platform == "win32":
            root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ConXml"
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support" / "ConXml"
        else:
            root = Path.home() / ".config" / "ConXml"
        return root / "ubicacion-datos.json"

    @property
    def ubicacion_guardada(self) -> Path | None:
        try:
            value = json.loads(self.ubicacion_path.read_text(encoding="utf-8"))["carpeta_datos"]
        except FileNotFoundError:
            return None
        except (ValueError, KeyError, TypeError) as exc:
            raise OSError("El registro de ubicación de datos no es válido.") from exc
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            raise OSError("La ubicación de datos guardada no es válida.")
        return Path(value)

    def guardar_ubicacion(self, destino: Path) -> None:
        destino = destino.expanduser().resolve()
        destino.mkdir(parents=True, exist_ok=True)
        # Comprueba escritura antes de recordar una ubicación que no funcionaría.
        with tempfile.TemporaryFile(dir=destino) as prueba:
            prueba.write(b"ConXml")
        registro = self.ubicacion_path
        registro.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=registro.parent,
                                         prefix=".ubicacion-", delete=False) as output:
            temporal = Path(output.name)
            json.dump({"carpeta_datos": str(destino)}, output, ensure_ascii=False)
        try:
            os.replace(temporal, registro)
        finally:
            temporal.unlink(missing_ok=True)

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

    @property
    def logs_dir(self) -> Path:
        """Ruta persistente de diagnóstico y registros de ejecución."""
        env_dir = os.environ.get("CONXML_LOG_DIR")
        if env_dir:
            return Path(env_dir).resolve()
        if getattr(sys, "frozen", False):
            if sys.platform == "win32":
                return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ConXml" / "logs"
            if sys.platform == "darwin":
                app_logs = Path.home() / "Library" / "Logs" / "ConXml"
                app_logs.mkdir(parents=True, exist_ok=True)
                return app_logs
            return Path(sys.executable).resolve().parent / "logs"
        return self.base.parent / "logs"

    @property
    def updates_dir(self) -> Path:
        """Ruta de descarga y preparación de actualizaciones."""
        env_dir = os.environ.get("CONXML_UPDATES_DIR")
        if env_dir:
            return Path(env_dir).resolve()
        if getattr(sys, "frozen", False):
            if sys.platform == "win32":
                return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ConXml" / "updates"
            if sys.platform == "darwin":
                updates = Path.home() / "Library" / "Application Support" / "ConXml" / "updates"
                updates.mkdir(parents=True, exist_ok=True)
                return updates
            return Path(sys.executable).resolve().parent / "updates"
        return self.base.parent / "updates"

    def inicializar(self) -> None:
        for ruta in (self.base, self.carpeta_entrada, self.carpeta_boveda,
                     self.carpeta_zip_sat, self.respaldos, self.logs_dir, self.updates_dir):
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
