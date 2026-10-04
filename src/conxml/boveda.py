"""Archivo físico organizado de XML para cada cliente.

La bóveda es deliberadamente independiente del catálogo SQLite: guardar un XML
no lo activa en las tablas hasta que el usuario carga una selección desde la
pantalla de bóveda.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from conxml.cfdi import CFDIParseError, parse_comprobante
from conxml.config import Config

DIRECCIONES = ("Recibidos", "Emitidos")
CARPETA_MASIVO = "Masivo"


@dataclass
class ResultadoBoveda:
    procesados: int = 0
    copiados: int = 0
    omitidos: int = 0
    errores: int = 0
    detalle_errores: list[str] = field(default_factory=list)


def clave_segura(valor: str) -> str:
    """Convierte una clave visible en un nombre de carpeta estable."""
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "_", valor.strip())
    return limpio.strip("._") or "sin-cliente"


def ruta_cliente(config: Config, cliente: str) -> Path:
    return config.carpeta_boveda / clave_segura(cliente)


def inicializar_boveda(config: Config, cliente: str) -> Path:
    """Crea la estructura inicial de la bóveda para un cliente."""
    raiz = ruta_cliente(config, cliente)
    for direccion in DIRECCIONES:
        (raiz / direccion / CARPETA_MASIVO).mkdir(parents=True, exist_ok=True)
    return raiz


def rutas_masivo(config: Config, cliente: str) -> dict[str, Path]:
    """Devuelve las carpetas donde se pueden pegar XML descargados del SAT."""
    raiz = inicializar_boveda(config, cliente)
    return {direccion: raiz / direccion / CARPETA_MASIVO for direccion in DIRECCIONES}


def procesar_masivo(config: Config, cliente: str, cliente_rfc: str = "") -> ResultadoBoveda:
    """Clasifica los XML pegados en las dos carpetas ``Masivo``."""
    resultado = ResultadoBoveda()
    for carpeta in rutas_masivo(config, cliente).values():
        parcial = copiar_xmls(carpeta, config, cliente, cliente_rfc)
        resultado.procesados += parcial.procesados
        resultado.copiados += parcial.copiados
        resultado.omitidos += parcial.omitidos
        resultado.errores += parcial.errores
        resultado.detalle_errores.extend(parcial.detalle_errores)
    return resultado


def instrucciones_boveda_ocultas(config: Config) -> bool:
    """Indica si el usuario pidió no volver a mostrar las instrucciones."""
    try:
        datos = json.loads(config.preferencias_path.read_text(encoding="utf-8"))
        return bool(datos.get("ocultar_instrucciones_boveda", False))
    except (OSError, ValueError, AttributeError):
        return False


def ocultar_instrucciones_boveda(config: Config) -> None:
    """Guarda la preferencia de ocultar el aviso de Bóveda."""
    ruta = config.preferencias_path
    try:
        datos = {}
        if ruta.is_file():
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except ValueError:
                datos = {}
        ruta.parent.mkdir(parents=True, exist_ok=True)
        datos["ocultar_instrucciones_boveda"] = True
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # La preferencia es opcional; nunca debe bloquear la importación.
        return


def direccion_comprobante(emisor_rfc: str | None, cliente_rfc: str | None) -> str:
    """Clasifica un comprobante según el RFC del cliente seleccionado."""
    if cliente_rfc and emisor_rfc and emisor_rfc.strip().upper() == cliente_rfc.strip().upper():
        return "Emitidos"
    return "Recibidos"


def copiar_xmls(
    origen: str | Path,
    config: Config,
    cliente: str,
    cliente_rfc: str = "",
) -> ResultadoBoveda:
    """Copia recursivamente XML válidos en ``cliente/dirección/año/mes``."""
    origen = Path(origen)
    resultado = ResultadoBoveda()
    if not origen.is_dir():
        resultado.errores = 1
        resultado.detalle_errores.append(f"No existe la carpeta: {origen}")
        return resultado

    destino_base = inicializar_boveda(config, cliente)
    archivos = sorted(p for p in origen.rglob("*") if p.is_file() and p.suffix.lower() == ".xml")
    for archivo in archivos:
        resultado.procesados += 1
        try:
            comprobante = parse_comprobante(archivo)
            if comprobante.uuid is None:
                raise CFDIParseError(archivo, "sin UUID")
            fecha = comprobante.fecha
            direccion = direccion_comprobante(comprobante.emisor_rfc, cliente_rfc)
            destino = destino_base / direccion / f"{fecha.year:04d}" / f"{fecha.month:02d}"
            destino.mkdir(parents=True, exist_ok=True)
            salida = destino / archivo.name
            if salida.exists():
                resultado.omitidos += 1
                continue
            shutil.copy2(archivo, salida)
            resultado.copiados += 1
        except Exception as exc:  # noqa: BLE001 - un XML inválido no detiene el lote
            resultado.errores += 1
            resultado.detalle_errores.append(f"{archivo}: {exc}")
    return resultado


def seleccionar_xmls(
    config: Config,
    cliente: str,
    direccion: str = "Todos",
    anio: str = "Todos",
    mes: str = "Todos",
) -> list[Path]:
    """Devuelve XML ubicados en la estructura física de la bóveda.

    Para Emitidos y Recibidos solo se consideran carpetas de año y mes:
    con mes ``Todos`` se incluyen XML sueltos en la carpeta del año y XML
    dentro de subcarpetas de mes; con un mes concreto solo se consulta esa
    carpeta mensual. Los archivos de Masivo conservan su lectura recursiva.
    """
    raiz = ruta_cliente(config, cliente)
    if not raiz.is_dir():
        return []
    es_masivo = direccion == CARPETA_MASIVO
    direcciones = DIRECCIONES if direccion in ("Todos", CARPETA_MASIVO) else (direccion,)
    archivos: list[Path] = []
    for actual in direcciones:
        base = raiz / actual / CARPETA_MASIVO if es_masivo else raiz / actual
        if not base.is_dir():
            continue
        if es_masivo:
            for archivo in base.rglob("*.xml"):
                if not archivo.is_file():
                    continue
                if anio != "Todos" or mes != "Todos":
                    try:
                        fecha = parse_comprobante(archivo).fecha
                    except Exception:
                        continue
                    if anio != "Todos" and f"{fecha.year:04d}" != anio:
                        continue
                    if mes != "Todos" and f"{fecha.month:02d}" != mes:
                        continue
                archivos.append(archivo)
            continue

        # La vista anual se basa en las carpetas que realmente existen y
        # nunca busca por fecha CFDI fuera de ellas.
        carpetas_anio = (
            [base / anio]
            if anio != "Todos"
            else sorted(
                carpeta for carpeta in base.iterdir()
                if carpeta.is_dir() and re.fullmatch(r"\d{4}", carpeta.name)
            )
        )
        for carpeta_anio in carpetas_anio:
            if not carpeta_anio.is_dir():
                continue
            if mes != "Todos":
                carpetas = [carpeta_anio / mes]
            else:
                # Al consultar un año completo, incluir tanto XML colocados
                # directamente en el año como los de carpetas mensuales.
                carpetas = [carpeta_anio, *sorted(
                    carpeta for carpeta in carpeta_anio.iterdir()
                    if carpeta.is_dir() and re.fullmatch(r"\d{2}", carpeta.name)
                )]
            for carpeta in carpetas:
                if carpeta.is_dir():
                    archivos.extend(
                        archivo for archivo in carpeta.glob("*.xml")
                        if archivo.is_file()
                    )
    return sorted(archivos)


def periodos_disponibles(config: Config, cliente: str) -> tuple[list[str], list[str]]:
    """Obtiene años y meses de las carpetas físicas de Emitidos/Recibidos."""
    raiz = ruta_cliente(config, cliente)
    anios: set[str] = set()
    meses: set[str] = set()
    for direccion in DIRECCIONES:
        base = raiz / direccion
        if not base.is_dir():
            continue
        for carpeta_anio in base.iterdir():
            if not carpeta_anio.is_dir() or not re.fullmatch(r"\d{4}", carpeta_anio.name):
                continue
            anios.add(carpeta_anio.name)
            meses.update(
                carpeta_mes.name for carpeta_mes in carpeta_anio.iterdir()
                if carpeta_mes.is_dir() and re.fullmatch(r"\d{2}", carpeta_mes.name)
            )
    return sorted(anios, reverse=True), sorted(meses)
