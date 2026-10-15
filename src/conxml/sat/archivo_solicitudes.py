"""Copias temporales para volver a bajar solicitudes durante catorce días."""
from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from conxml.boveda import clave_segura
from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.descarga_masiva import guardar_paquete_zip

DIAS_DISPONIBLES = 14


def carpeta_solicitud(config: Config, cliente: str, solicitud: str) -> Path:
    return config.base / 'cache_sat' / clave_segura(cliente) / clave_segura(solicitud)


def conservar_paquete(contenido: bytes, config: Config, cliente: str, solicitud: str, paquete: str) -> Path:
    carpeta = carpeta_solicitud(config, cliente, solicitud)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / (clave_segura(paquete) + '.zip')
    fd, temporal = tempfile.mkstemp(prefix='.paquete-', dir=carpeta)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(contenido)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporal, destino)
    finally:
        Path(temporal).unlink(missing_ok=True)
    return destino


def paquetes_locales(config: Config, cliente: str, solicitud: str) -> list[Path]:
    return sorted(carpeta_solicitud(config, cliente, solicitud).glob('*.zip'))


def exportar_paquetes(paquetes: list[Path], destino: Path, *, xml: bool = False) -> None:
    if not paquetes:
        raise ValueError('Esta solicitud todavía no tiene paquetes disponibles.')
    if xml:
        # El extractor existente comprueba rutas y límites del ZIP antes de escribir.
        for paquete in paquetes:
            guardar_paquete_zip(paquete.read_bytes(), destino / paquete.stem)
    elif len(paquetes) == 1:
        shutil.copy2(paquetes[0], destino)
    else:
        with zipfile.ZipFile(destino, 'w', compression=zipfile.ZIP_DEFLATED) as salida:
            for paquete in paquetes:
                salida.write(paquete, paquete.name)


def limpiar_vencidas(config: Config, db_path: Path, ahora: datetime | None = None) -> int:
    """Elimina historial y caché vencidos; nunca toca XML de la bóveda."""
    limite = (ahora or datetime.now()) - timedelta(days=DIAS_DISPONIBLES)
    with Catalogo(db_path) as cat:
        filas = cat.conn.execute(
            'SELECT cliente, id_sat FROM solicitudes_descarga WHERE creada_en <= ?',
            (limite.isoformat(timespec='seconds'),),
        ).fetchall()
        for cliente, solicitud in filas:
            carpeta = carpeta_solicitud(config, cliente, solicitud)
            if carpeta.is_symlink():
                carpeta.unlink()
            elif carpeta.exists():
                shutil.rmtree(carpeta)
            cat.conn.execute('DELETE FROM sat_solicitudes_periodicas WHERE id_sat = ?', (solicitud,))
            cat.conn.execute('DELETE FROM solicitudes_descarga WHERE id_sat = ?', (solicitud,))
        cat.commit()
    return len(filas)
