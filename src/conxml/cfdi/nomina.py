"""Modelos y parser del Complemento de Nómina 1.2 (nomina12).

Extrae el encabezado de la nómina, emisor/receptor y, sobre todo, los
nodos Percepciones (con sus HorasExtra) y Deducciones con montos gravados
y exentos. Las facturas normales devuelven None (tolerante), lo que permite
al importador procesar toda la carpeta sin distinguir tipos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from lxml import etree

from conxml.cfdi._common import NSMAP, PARSER as _PARSER, _dec, _fecha, _int, cargar_arbol
from conxml.cfdi.models import Comprobante
from conxml.cfdi.parser import CFDIParseError

NOMINA_NS = "http://www.sat.gob.mx/nomina12"


@dataclass
class HorasExtra:
    dias: int | None
    tipo_horas: str
    horas_extra: Decimal | None
    importe_pagado: Decimal | None


@dataclass
class Percepcion:
    tipo_percepcion: str
    clave: str
    concepto: str
    importe_gravado: Decimal | None
    importe_exento: Decimal | None
    horas_extra: HorasExtra | None = None


@dataclass
class Deduccion:
    tipo_deduccion: str
    clave: str
    concepto: str
    importe: Decimal | None


@dataclass
class Nomina:
    tipo_nomina: str
    fecha_pago: datetime
    fecha_inicial_pago: datetime
    fecha_final_pago: datetime
    num_dias_pagados: Decimal | None
    total_percepciones: Decimal | None
    total_deducciones: Decimal | None
    total_otros_pagos: Decimal | None
    registro_patronal: str | None = None
    curp: str | None = None
    num_empleado: str | None = None
    puesto: str | None = None
    periodicidad_pago: str | None = None
    salario_base_cot_apor: Decimal | None = None
    salario_diario_integrado: Decimal | None = None
    total_sueldos: Decimal | None = None
    total_gravado: Decimal | None = None
    total_exento: Decimal | None = None
    total_impuestos_retenidos: Decimal | None = None
    percepciones: list[Percepcion] = field(default_factory=list)
    deducciones: list[Deduccion] = field(default_factory=list)


def _int(value: str | None) -> int | None:  # compat: ahora en _common
    from conxml.cfdi._common import entero

    return entero(value)


def _attr(nodos: list, nombre: str):
    return nodos[0].get(nombre) if nodos else None


def _parse_horas_extra(percepcion_el: etree._Element, nsmap: dict) -> HorasExtra | None:
    el = percepcion_el.xpath("n12:HorasExtra", namespaces=nsmap)
    if not el:
        return None
    return HorasExtra(
        dias=_int(el[0].get("Dias")),
        tipo_horas=el[0].get("TipoHoras", ""),
        horas_extra=_dec(el[0].get("HorasExtra")),
        importe_pagado=_dec(el[0].get("ImportePagado")),
    )


def _parse_percepciones(el: etree._Element | None, nsmap: dict) -> tuple[list[Percepcion], Decimal | None, Decimal | None, Decimal | None]:
    if el is None:
        return [], None, None, None
    totales = el.xpath("n12:Percepciones", namespaces=nsmap)
    if not totales:
        return [], None, None, None
    nodo = totales[0]
    percepciones = [
        Percepcion(
            tipo_percepcion=per.get("TipoPercepcion", ""),
            clave=per.get("Clave", ""),
            concepto=per.get("Concepto", ""),
            importe_gravado=_dec(per.get("ImporteGravado")),
            importe_exento=_dec(per.get("ImporteExento")),
            horas_extra=_parse_horas_extra(per, nsmap),
        )
        for per in nodo.xpath("n12:Percepcion", namespaces=nsmap)
    ]
    return (
        percepciones,
        _dec(nodo.get("TotalSueldos")),
        _dec(nodo.get("TotalGravado")),
        _dec(nodo.get("TotalExento")),
    )


def _parse_deducciones(el: etree._Element | None, nsmap: dict) -> tuple[list[Deduccion], Decimal | None]:
    if el is None:
        return [], None
    totales = el.xpath("n12:Deducciones", namespaces=nsmap)
    if not totales:
        return [], None
    nodo = totales[0]
    deducciones = [
        Deduccion(
            tipo_deduccion=d.get("TipoDeduccion", ""),
            clave=d.get("Clave", ""),
            concepto=d.get("Concepto", ""),
            importe=_dec(d.get("Importe")),
        )
        for d in nodo.xpath("n12:Deduccion", namespaces=nsmap)
    ]
    return deducciones, _dec(nodo.get("TotalImpuestosRetenidos"))


def parse_nomina_desde_raiz(root: etree._Element) -> Nomina | None:
    """Extrae nómina desde raíz ya parseada (sin re-leer disco)."""
    nsmap = {**NSMAP, "n12": NOMINA_NS}
    nodos = root.xpath("cfdi:Complemento/n12:Nomina", namespaces=nsmap)
    if not nodos:
        return None
    el = nodos[0]

    emisor = el.xpath("n12:Emisor", namespaces=nsmap)
    receptor = el.xpath("n12:Receptor", namespaces=nsmap)
    percepciones, total_sueldos, total_gravado, total_exento = _parse_percepciones(el, nsmap)
    deducciones, total_impuestos_retenidos = _parse_deducciones(el, nsmap)

    return Nomina(
        tipo_nomina=el.get("TipoNomina", ""),
        fecha_pago=_fecha(el.get("FechaPago")) or datetime.min,
        fecha_inicial_pago=_fecha(el.get("FechaInicialPago")) or datetime.min,
        fecha_final_pago=_fecha(el.get("FechaFinalPago")) or datetime.min,
        num_dias_pagados=_dec(el.get("NumDiasPagados")),
        total_percepciones=_dec(el.get("TotalPercepciones")),
        total_deducciones=_dec(el.get("TotalDeducciones")),
        total_otros_pagos=_dec(el.get("TotalOtrosPagos")),
        registro_patronal=_attr(emisor, "RegistroPatronal"),
        curp=_attr(receptor, "Curp"),
        num_empleado=_attr(receptor, "NumEmpleado"),
        puesto=_attr(receptor, "Puesto"),
        periodicidad_pago=_attr(receptor, "PeriodicidadPago"),
        salario_base_cot_apor=_dec(_attr(receptor, "SalarioBaseCotApor")),
        salario_diario_integrado=_dec(_attr(receptor, "SalarioDiarioIntegrado")),
        total_sueldos=total_sueldos,
        total_gravado=total_gravado,
        total_exento=total_exento,
        total_impuestos_retenidos=total_impuestos_retenidos,
        percepciones=percepciones,
        deducciones=deducciones,
    )


def parse_nomina(
    comprobante: Comprobante, arbol: etree._ElementTree | None = None
) -> Nomina | None:
    """Extrae nómina del CFDI. Si `arbol` viene, no relee el disco."""
    if arbol is not None:
        return parse_nomina_desde_raiz(arbol.getroot())
    tree = cargar_arbol(comprobante.ruta)
    return parse_nomina_desde_raiz(tree.getroot())