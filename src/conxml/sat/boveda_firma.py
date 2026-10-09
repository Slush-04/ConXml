"""Resguardo local de archivos e.firma por cliente; nunca almacena contraseñas."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from conxml.boveda import clave_segura
from conxml.config import Config


def carpeta_firma(config: Config, cliente: str) -> Path:
    return config.base / "clientes" / clave_segura(cliente) / "efirma"


def archivos_guardados(config: Config, cliente: str) -> tuple[Path, Path] | None:
    carpeta = carpeta_firma(config, cliente)
    cer, key = carpeta / "certificado.cer", carpeta / "llave_privada.key"
    return (cer, key) if cer.is_file() and key.is_file() else None


def guardar_archivos(config: Config, cliente: str, cer: str | Path, key: str | Path) -> tuple[Path, Path]:
    origen_cer, origen_key = Path(cer), Path(key)
    if origen_cer.suffix.lower() not in {".cer", ".crt"} or origen_key.suffix.lower() != ".key":
        raise ValueError("Selecciona un certificado .cer y una llave privada .key válidos.")
    if not origen_cer.is_file() or not origen_key.is_file():
        raise ValueError("No se encuentran los archivos de e.firma seleccionados.")

    carpeta = carpeta_firma(config, cliente)
    carpeta.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        carpeta.chmod(0o700)
    destinos = (carpeta / "certificado.cer", carpeta / "llave_privada.key")
    temporales: list[Path] = []
    try:
        for origen in (origen_cer, origen_key):
            descriptor, nombre = tempfile.mkstemp(prefix=".firma-", dir=carpeta)
            temporal = Path(nombre)
            temporales.append(temporal)
            try:
                with os.fdopen(descriptor, "wb") as salida, origen.open("rb") as entrada:
                    shutil.copyfileobj(entrada, salida)
                if os.name == "posix":
                    temporal.chmod(0o600)
            except Exception:
                temporal.unlink(missing_ok=True)
                raise
        for temporal, destino in zip(temporales, destinos):
            temporal.replace(destino)
        return destinos
    finally:
        for temporal in temporales:
            temporal.unlink(missing_ok=True)


def quitar_archivos(config: Config, cliente: str) -> None:
    carpeta = carpeta_firma(config, cliente)
    for nombre in ("certificado.cer", "llave_privada.key"):
        (carpeta / nombre).unlink(missing_ok=True)
