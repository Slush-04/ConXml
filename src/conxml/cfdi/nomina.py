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

from conxml.cfdi.models import Comprobante
from conxml.cfdi.parser import NSMAP, CFDIParseError, _dec, _fecha

NOMINA_NS = "http://www.sat.gob.mx/nomina12"

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


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


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


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


def parse_nomina(comprobante: Comprobante) -> Nomina | None:
    """Extrae el complemento de nómina del CFDI dado.

    Devuelve None si el comprobante no trae complemento de nómina.
    """
    ruta: Path = comprobante.ruta
    try:
        tree = etree.parse(str(ruta), parser=_PARSER)
    except etree.XMLSyntaxError as exc:
        raise CFDIParseError(ruta, f"no es un XML válido: {exc}") from exc

    nsmap = {**NSMAP, "n12": NOMINA_NS}
    root = tree.getroot()
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
        registro_patronal=emisor[0].get("RegistroPatronal") if emisor else None,
        curp=receptor[0].get("Curp") if receptor else None,
        num_empleado=receptor[0].get("NumEmpleado") if receptor else None,
        puesto=receptor[0].get("Puesto") if receptor else None,
        periodicidad_pago=receptor[0].get("PeriodicidadPago") if receptor else None,
        salario_base_cot_apor=_dec(receptor[0].get("SalarioBaseCotApor")) if receptor else None,
        salario_diario_integrado=_dec(receptor[0].get("SalarioDiarioIntegrado")) if receptor else None,
        total_sueldos=total_sueldos,
        total_gravado=total_gravado,
        total_exento=total_exento,
        total_impuestos_retenidos=total_impuestos_retenidos,
        percepciones=percepciones,
        deducciones=deducciones,
    )