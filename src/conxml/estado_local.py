"""Preferencias y sesión locales, con escritura atómica y sin credenciales."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from conxml.config import Config

_LOCK = threading.RLock()


def cargar(ruta: Path | None = None) -> dict:
    ruta = ruta or Config().preferencias_path
    with _LOCK:
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            return datos if isinstance(datos, dict) else {}
        except (OSError, ValueError):
            return {}


def guardar(cambios: dict, ruta: Path | None = None) -> None:
    """Combina preferencias sin perder las de otros módulos."""
    ruta = ruta or Config().preferencias_path
    with _LOCK:
        datos = cargar(ruta)
        datos.update(cambios)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fd, temporal = tempfile.mkstemp(prefix='.preferencias-', dir=ruta.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(datos, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporal, ruta)
        finally:
            Path(temporal).unlink(missing_ok=True)
