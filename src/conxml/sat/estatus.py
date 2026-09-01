"""Consulta de estatus en lote con concurrencia, throttling, reintentos y caché."""

from __future__ import annotations

import concurrent.futures
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Callable

import requests
from requests.adapters import HTTPAdapter

from conxml.catalog.db import Catalogo
from conxml.sat.soap import ResultadoEstatus, consultar

ESTADOS_FINALES = frozenset({"Vigente", "Cancelado", "No Encontrado"})
COMMIT_CADENCIA = 50
DETALLE_MAX = 500


@dataclass
class ConfigLote:
    delay_segundos: float = 0.0
    reintentos: int = 2
    timeout: float = 12.0
    max_workers: int = 8


@dataclass
class ResultadoLote:
    consultados: int = 0
    vigentes: int = 0
    cancelados: int = 0
    no_encontrados: int = 0
    desconocidos: int = 0
    fallos: int = 0
    detalle: list[str] = field(default_factory=list)


def _aplicar_estatus(
    fila: dict | sqlite3.Row,
    estatus_sat: ResultadoEstatus,
    catalogo: Catalogo,
    resultado: ResultadoLote,
) -> None:
    resultado.consultados += 1
    if estatus_sat.es_vigente:
        resultado.vigentes += 1
    elif estatus_sat.es_cancelado:
        resultado.cancelados += 1
    elif estatus_sat.estado == "No Encontrado":
        resultado.no_encontrados += 1
    else:
        resultado.desconocidos += 1

    if estatus_sat.estado in ESTADOS_FINALES:
        catalogo.asignar_estatus(
            fila["uuid"],
            estatus_sat.estado,
            es_cancelable=estatus_sat.es_cancelable,
            estatus_cancelacion=estatus_sat.estatus_cancelacion,
        )
        if resultado.consultados % COMMIT_CADENCIA == 0:
            catalogo.commit()


def _procesar_fila(
    fila: dict | sqlite3.Row,
    config: ConfigLote,
    sesion: requests.Session,
    catalogo: Catalogo,
    resultado: ResultadoLote,
) -> None:
    try:
        estatus_sat = _consultar_con_reintentos(fila, config=config, sesion=sesion)
        _aplicar_estatus(fila, estatus_sat, catalogo, resultado)
    except Exception as exc:  # noqa: BLE001
        resultado.fallos += 1
        if len(resultado.detalle) < DETALLE_MAX:
            resultado.detalle.append(f"{fila['uuid']}: {exc}")


def consultar_lote(
    catalogo: Catalogo,
    config: ConfigLote | None = None,
    cliente: str | None = None,
    force: bool = False,
    progreso: Callable[[int, int], None] | None = None,
) -> ResultadoLote:
    """Consulta el estatus de los comprobantes del catálogo sin estatus.

    Escribe el resultado en la columna `estatus` del catálogo (caché).
    Con `force=True` re-consulta también los ya validados. `cliente` limita
    la consulta a un cliente. Solo persisten los estados finales
    (Vigente/Cancelado/No Encontrado); "Desconocido" y errores de red no se
    escriben, de modo que se reintentan en la siguiente corrida.
    Soporta ejecución paralela con `config.max_workers`.
    """
    config = config or ConfigLote()
    total = catalogo.contar_consulta(cliente=cliente, sin_estatus=not force)
    resultado = ResultadoLote()
    if total == 0:
        return resultado

    registros = [dict(f) for f in catalogo.consulta(cliente=cliente, sin_estatus=not force)]

    adapter = HTTPAdapter(
        pool_connections=max(10, config.max_workers * 2),
        pool_maxsize=max(10, config.max_workers * 2),
    )

    with requests.Session() as sesion:
        sesion.mount("https://", adapter)
        sesion.mount("http://", adapter)

        if config.max_workers <= 1:
            for indice, fila in enumerate(registros, start=1):
                if progreso is not None:
                    progreso(indice, total)
                _procesar_fila(fila, config, sesion, catalogo, resultado)
                if indice < total and config.delay_segundos:
                    time.sleep(config.delay_segundos)
        else:
            completados = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                futuros = {
                    executor.submit(_consultar_con_reintentos, fila, config, sesion): fila
                    for fila in registros
                }
                for futuro in concurrent.futures.as_completed(futuros):
                    fila = futuros[futuro]
                    completados += 1
                    if progreso is not None:
                        progreso(completados, total)
                    try:
                        estatus_sat = futuro.result()
                        _aplicar_estatus(fila, estatus_sat, catalogo, resultado)
                    except Exception as exc:  # noqa: BLE001
                        resultado.fallos += 1
                        if len(resultado.detalle) < DETALLE_MAX:
                            resultado.detalle.append(f"{fila['uuid']}: {exc}")

    catalogo.commit()
    return resultado


def _consultar_con_reintentos(
    fila: dict | sqlite3.Row, config: ConfigLote, sesion: requests.Session
) -> ResultadoEstatus:
    """Consulta un folio con reintentos; relanza el último error si se agotan."""
    for intento in range(config.reintentos + 1):
        try:
            return consultar(
                uuid=fila["uuid"],
                rfc_emisor=fila["emisor_rfc"],
                rfc_receptor=fila["receptor_rfc"],
                total=fila["total"],
                timeout=config.timeout,
                session=sesion,
            )
        except Exception:
            if intento == config.reintentos:
                raise
            time.sleep(min(2**intento, config.delay_segundos or 0.5))