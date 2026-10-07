"""Arranque protegido de la GUI y diagnóstico de fallos tempranos."""

from __future__ import annotations

import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox


def log_path() -> Path:
    """Devuelve una ruta persistente y escribible para fallos de arranque."""
    override = os.environ.get("CONXML_LOG_DIR")
    if override:
        return Path(override).expanduser() / "startup.log"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ConXml" / "logs" / "startup.log"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "ConXml" / "startup.log"
    return Path.home() / ".local" / "state" / "conxml" / "logs" / "startup.log"


def write_startup_error(exc: BaseException) -> Path:
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write("\n" + "=" * 72 + "\n")
            output.write(f"Fecha UTC: {datetime.now().astimezone().isoformat()}\n")
            output.write(f"Versión de Python: {platform.python_version()}\n")
            output.write(f"Sistema: {platform.platform()}\n")
            output.write(f"Ejecutable: {sys.executable}\n")
            output.write(f"Directorio actual: {Path.cwd()}\n")
            output.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
            output.write("Traceback:\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=output)
        return path
    except Exception:
        # El diagnóstico nunca debe ocultar el error original.
        return path


def run_gui(entrypoint) -> None:
    """Ejecuta la GUI y muestra/loguea excepciones no controladas."""
    try:
        entrypoint()
    except BaseException as exc:
        path = write_startup_error(exc)
        try:
            messagebox.showerror(
                "ConXml no pudo iniciar",
                "ConXml encontró un error al iniciar.\n\n"
                f"Se guardó un diagnóstico en:\n{path}\n\n{exc}",
            )
        except Exception:
            pass
        raise
