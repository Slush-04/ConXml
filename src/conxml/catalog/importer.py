"""Importador de carpetas de XML al catálogo, multi-RFC."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from conxml.catalog.db import Catalogo
from conxml.cfdi import CFDIParseError, parse_pagos
from conxml.cfdi.parser import parse_comprobante_con_arbol


@dataclass
class ResultadoImportacion:
    procesados: int = 0
    insertados: int = 0
    omitidos: int = 0
    errores: int = 0
    detalle_errores: list[str] = field(default_factory=list)


def importar_carpeta(
    catalogo: Catalogo,
    carpeta: str | Path,
    cliente: str,
    limpiar_antes: bool = False,
) -> ResultadoImportacion:
    """Importa una sola carpeta de XMLs al catálogo."""
    return importar_carpetas(catalogo, [carpeta], cliente, limpiar_antes=limpiar_antes)


def importar_carpetas(
    catalogo: Catalogo,
    carpetas: list[str | Path] | str | Path,
    cliente: str,
    limpiar_antes: bool = False,
) -> ResultadoImportacion:
    """Recorre las carpetas (recursivo), parsa cada XML y lo guarda en el catálogo.

    Dedupe por UUID: un mismo comprobante ya existente se omite.
    Si limpiar_antes es True, vacía el catálogo antes de importar.
    """
    if limpiar_antes:
        catalogo.limpiar()

    match carpetas:
        case str() | Path():
            lista_carpetas = [Path(carpetas)]
        case _:
            lista_carpetas = [Path(p) for p in carpetas]

    resultado = ResultadoImportacion()
    archivos: list[Path] = []
    for c in lista_carpetas:
        p_carpeta = Path(c)
        if not p_carpeta.is_dir():
            resultado.detalle_errores.append(f"carpeta no encontrada: {p_carpeta}")
            continue
        archivos.extend(p_carpeta.rglob("*.xml"))

    for archivo in sorted(set(archivos)):
        resultado.procesados += 1
        try:
            comprobante, arbol = parse_comprobante_con_arbol(archivo)
            if comprobante.uuid is None:
                raise CFDIParseError(archivo, "sin timbre fiscal (UUID no encontrado)")
            pagos = parse_pagos(comprobante, arbol)
            estado = catalogo.insert_comprobante(cliente, comprobante, pagos)
            if estado == "inserted":
                resultado.insertados += 1
            else:
                resultado.omitidos += 1
        except CFDIParseError as exc:
            resultado.errores += 1
            resultado.detalle_errores.append(str(exc))
            _registrar_error(catalogo, archivo, str(exc))
        except Exception as exc:  # noqa: BLE001 — nunca detener la importación
            mensaje = f"excepción inesperada: {exc!r}"
            resultado.errores += 1
            resultado.detalle_errores.append(f"{archivo}: {mensaje}")
            _registrar_error(catalogo, archivo, mensaje)

    return resultado


def _registrar_error(catalogo: Catalogo, archivo: Path, mensaje: str) -> None:
    """Registra el error en BD sin que un fallo de escritura aborte el lote."""
    import logging

    try:
        catalogo.registrar_error(archivo, mensaje)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("conxml.importer").warning("no se pudo registrar %s: %s", archivo, exc)