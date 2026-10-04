"""Guardado local de paquetes SAT según las preferencias del usuario."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from conxml.boveda import clave_segura, copiar_xmls, direccion_comprobante, ruta_cliente
from conxml.cfdi import parse_comprobante
from conxml.config import Config
from conxml.sat.descarga_masiva import guardar_paquete_zip


@dataclass
class ResultadoGuardado:
    copiados: int = 0
    errores: int = 0
    archivos: list[Path] = field(default_factory=list)
    zip_guardado: Path | None = None


def guardar_paquete(
    contenido: bytes, config: Config, cliente: str, rfc: str,
    solicitud: str, paquete: str, *, modo: str,
) -> ResultadoGuardado:
    """En modo ZIP conserva los bytes; en organizado copia XML a la bóveda.

    Nunca lee ni escribe credenciales. El llamador importa ``archivos`` al
    catálogo sólo en modo organizado, después de recuperar todos los paquetes.
    """
    if modo == "zip":
        carpeta = config.carpeta_zip_sat / clave_segura(cliente) / clave_segura(solicitud)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / (clave_segura(paquete) + ".zip")
        fd, nombre = tempfile.mkstemp(prefix=".sat-", dir=carpeta)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(contenido)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(nombre, destino)
        finally:
            Path(nombre).unlink(missing_ok=True)
        return ResultadoGuardado(zip_guardado=destino)
    if modo != "organizado":
        raise ValueError("Modo de descarga desconocido")
    with tempfile.TemporaryDirectory(prefix="conxml-sat-") as temporal:
        extraidos = guardar_paquete_zip(contenido, temporal)
        copia = copiar_xmls(temporal, config, cliente, rfc)
        resultado = ResultadoGuardado(copiados=copia.copiados, errores=copia.errores)
        for archivo in extraidos:
            try:
                cfdi = parse_comprobante(archivo)
                if not cfdi.uuid:
                    continue
                destino = (
                    ruta_cliente(config, cliente) / direccion_comprobante(cfdi.emisor_rfc, rfc)
                    / f"{cfdi.fecha.year:04d}" / f"{cfdi.fecha.month:02d}" / archivo.name
                )
                if destino.is_file():
                    resultado.archivos.append(destino)
            except Exception:
                continue  # copiar_xmls ya contabiliza los errores del lote
        return resultado
