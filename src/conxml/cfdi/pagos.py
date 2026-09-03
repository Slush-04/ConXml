"""Modelos y parser del Complemento de Pago 2.0 (Pago20 / REP).

Soporta el complemento standalone: un CFDI TipoDeComprobante="P" cuyo
cfdi:Complemento contiene el nodo Pagos. Las facturas normales devuelven
una lista vacía (tolerante), lo que permite al importador procesar toda
la carpeta sin distinguir tipos.
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

PAGOS_NS = "http://www.sat.gob.mx/Pagos20"
# Pagos 1.0 legacy (tolerante: algunos REP viejos aún circulan)
PAGOS_NS_10 = "http://www.sat.gob.mx/Pagos"


@dataclass(slots=True)
class DoctoRelacionado:
    uuid: str
    moneda: str
    num_parcialidad: int | None
    imp_saldo_ant: Decimal | None
    imp_pagado: Decimal | None
    imp_saldo_insoluto: Decimal | None
    serie: str | None = None
    folio: str | None = None
    equivalencia_dr: Decimal | None = None


@dataclass(slots=True)
class Pago:
    fecha: datetime
    forma_pago: str
    moneda: str
    monto: Decimal
    tipo_cambio: Decimal | None = None
    num_operacion: str | None = None
    rfc_emisor_cta_ord: str | None = None
    cta_ordenante: str | None = None
    rfc_emisor_cta_ben: str | None = None
    cta_beneficiario: str | None = None
    doctos_relacionados: list[DoctoRelacionado] = field(default_factory=list)


def _int(value: str | None) -> int | None:  # compat: ahora en _common
    from conxml.cfdi._common import entero

    return entero(value)


def parse_pagos_desde_raiz(root: etree._Element) -> list[Pago]:
    """Extrae pagos desde una raíz ya parseada (sin re-leer disco)."""
    for ns in (PAGOS_NS, PAGOS_NS_10):
        nsmap = {**NSMAP, "p20": ns}
        pagos_el = root.xpath("cfdi:Complemento/p20:Pagos/p20:Pago", namespaces=nsmap)
        if pagos_el:
            break
    else:
        return []

    resultados: list[Pago] = []
    for el in pagos_el:
        pago = Pago(
            fecha=_fecha(el.get("FechaPago")) or datetime.min,
            forma_pago=el.get("FormaDePagoP", ""),
            moneda=el.get("MonedaP", ""),
            monto=_dec(el.get("Monto")) or Decimal(0),
            tipo_cambio=_dec(el.get("TipoCambioP")),
            num_operacion=el.get("NumOperacion"),
            rfc_emisor_cta_ord=el.get("RfcEmisorCtaOrd"),
            cta_ordenante=el.get("CtaOrdenante"),
            rfc_emisor_cta_ben=el.get("RfcEmisorCtaBen"),
            cta_beneficiario=el.get("CtaBeneficiario"),
        )
        for doc in el.xpath("p20:DoctoRelacionado", namespaces=nsmap):
            pago.doctos_relacionados.append(
                DoctoRelacionado(
                    uuid=doc.get("IdDocumento", ""),
                    moneda=doc.get("MonedaDR", ""),
                    num_parcialidad=_int(doc.get("NumParcialidad")),
                    imp_saldo_ant=_dec(doc.get("ImpSaldoAnt")),
                    imp_pagado=_dec(doc.get("ImpPagado")),
                    imp_saldo_insoluto=_dec(doc.get("ImpSaldoInsoluto")),
                    serie=doc.get("Serie"),
                    folio=doc.get("Folio"),
                    equivalencia_dr=_dec(doc.get("EquivalenciaDR")),
                )
            )
        resultados.append(pago)
    return resultados


def parse_pagos(
    comprobante: Comprobante, arbol: etree._ElementTree | None = None
) -> list[Pago]:
    """Extrae los pagos del CFDI dado. Si `arbol` viene, no relee el disco."""
    if arbol is not None:
        return parse_pagos_desde_raiz(arbol.getroot())
    ruta: Path = comprobante.ruta
    tree = cargar_arbol(ruta)
    return parse_pagos_desde_raiz(tree.getroot())