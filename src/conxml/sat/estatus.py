"""Consulta de estatus en lote con throttling, reintentos y caché."""

from __future__ import annotations

import sqlite3
import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, field
from typing import Callable

import requests

from conxml.catalog.db import Catalogo
from conxml.sat.soap import ResultadoEstatus, consultar

ESTADOS_FINALES = frozenset({"Vigente", "Cancelado", "No Encontrado"})
COMMIT_CADENCIA = 100
DETALLE_MAX = 500


@dataclass
class ConfigLote:
    delay_segundos: float = 2.0
    reintentos: int = 2
    timeout: float = 15.0
    trabajadores: int = 1


@dataclass
class ResultadoLote:
    consultados: int = 0
    vigentes: int = 0
    cancelados: int = 0
    no_encontrados: int = 0
    desconocidos: int = 0
    fallos: int = 0
    detalle: list[str] = field(default_factory=list)


def consultar_lote(
    catalogo: Catalogo,
    config: ConfigLote | None = None,
    cliente: str | None = None,
    force: bool = False,
    progreso: Callable[[int, int], None] | None = None,
    uuids: set[str] | None = None,
) -> ResultadoLote:
    """Consulta el estatus de los comprobantes del catálogo sin estatus.

    Escribe el resultado en la columna `estatus` del catálogo (caché).
    Con `force=True` re-consulta también los ya validados. `cliente` limita
    la consulta a un cliente. Solo persisten los estados finales
    (Vigente/Cancelado/No Encontrado); "Desconocido" y errores de red no se
    escriben, de modo que se reintentan en la siguiente corrida.
    `uuids` limita la consulta a la selección/vista (vacío no consulta nada).
    `progreso` recibe los completados, incluidos fallos, como fn(procesados, total).
    """
    config = config or ConfigLote()
    # Materializar antes de crear hilos: SQLite se consulta y escribe únicamente
    # desde el hilo dueño del catálogo. Un conjunto vacío no valida todo.
    registros = [
        {clave: fila[clave] for clave in ("uuid", "emisor_rfc", "receptor_rfc", "total")}
        for fila in catalogo.consulta(cliente=cliente, sin_estatus=not force)
        if uuids is None or fila["uuid"] in uuids
    ]
    total = len(registros)
    resultado = ResultadoLote()
    for indice, (fila, estatus_sat, error) in enumerate(_consultar_registros(registros, config), start=1):
        if error is not None:
            resultado.fallos += 1
            if len(resultado.detalle) < DETALLE_MAX:
                resultado.detalle.append(f"{fila['uuid']}: {error}")
        else:
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
                    fila["uuid"], estatus_sat.estado,
                    es_cancelable=estatus_sat.es_cancelable,
                    estatus_cancelacion=estatus_sat.estatus_cancelacion,
                )
                if resultado.consultados % COMMIT_CADENCIA == 0:
                    catalogo.commit()
        if progreso is not None:
            progreso(indice, total)

    catalogo.commit()
    return resultado


def _consultar_registros(registros, config):
    """Concurrencia acotada y una sesión HTTP reutilizable por trabajador."""
    if not registros:
        return
    trabajadores = min(3, max(1, config.trabajadores), len(registros))
    local = threading.local()
    sesiones = []

    def inicializar():
        local.sesion = requests.Session()
        local.usada = False
        sesiones.append(local.sesion)

    def consultar_fila(fila):
        if local.usada and config.delay_segundos > 0:
            time.sleep(config.delay_segundos)
        local.usada = True
        try:
            respuesta = _consultar_con_reintentos(fila, config=config, sesion=local.sesion)
            return fila, respuesta, None
        except Exception as exc:
            return fila, None, exc

    try:
        if trabajadores == 1:
            inicializar()
            for fila in registros:
                yield consultar_fila(fila)
        else:
            # No encolar todo el catálogo: como máximo hay tres solicitudes en vuelo.
            with ThreadPoolExecutor(max_workers=trabajadores, initializer=inicializar) as executor:
                pendientes = iter(registros)
                futuros = {executor.submit(consultar_fila, next(pendientes)) for _ in range(trabajadores)}
                while futuros:
                    terminados, futuros = wait(futuros, return_when=FIRST_COMPLETED)
                    for futuro in terminados:
                        yield futuro.result()
                        fila = next(pendientes, None)
                        if fila is not None:
                            futuros.add(executor.submit(consultar_fila, fila))
    finally:
        for sesion in sesiones:
            sesion.close()


def _consultar_con_reintentos(
    fila: sqlite3.Row, config: ConfigLote, sesion: requests.Session
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
        except Exception as exc:
            if intento == config.reintentos:
                raise
            espera = min(2 ** intento, 8)
            respuesta = getattr(exc, "response", None)
            if respuesta is not None and respuesta.status_code in (429, 503):
                try:
                    espera = max(espera, min(60, float(respuesta.headers.get("Retry-After", 0))))
                except (TypeError, ValueError):
                    pass
            time.sleep(espera)
