"""Parser de CFDI 4.0 basado en lxml.

Solo soporta la versión 4.0 del esquema cfdi; cualquier otro documento
(3.3, nómina como raíz, XML malformado) produce un error claro sin crash.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from conxml.cfdi._common import (
    CFDI_NS as _COMMON_CFDI_NS,
    NSMAP,
    PARSER as _PARSER,
    TFD_NS as _COMMON_TFD_NS,
    _dec,
    _fecha,
    _primero,
    cargar_arbol,
)
from conxml.cfdi.models import Comprobante, Retencion, Traslado

CFDI_NS = _COMMON_CFDI_NS
TFD_NS = _COMMON_TFD_NS


class CFDIParseError(Exception):
    """Error al parsear un XML de CFDI."""

    def __init__(self, ruta: Path, mensaje: str) -> None:
        self.ruta = ruta
        super().__init__(f"{ruta}: {mensaje}")


class UnsupportedVersionError(CFDIParseError):
    """El XML no es un CFDI versión 4.0."""


def _dec(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def _fecha(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_impuestos(el_impuestos: etree._Element | None, nodo: str, clase):
    """Genérico para Traslados/Retenciones (antes dos funciones idénticas)."""
    if el_impuestos is None:
        return []
    plural = {"Traslado": "Traslados", "Retencion": "Retenciones"}[nodo]
    return [
        clase(
            base=_dec(el.get("Base")),
            impuesto=el.get("Impuesto", ""),
            tipo_factor=el.get("TipoFactor", ""),
            tasa_o_cuota=_dec(el.get("TasaOCuota")),
            importe=_dec(el.get("Importe")),
        )
        for el in el_impuestos.xpath(
            f"cfdi:{plural}/cfdi:{nodo}", namespaces=NSMAP
        )
    ]


def _parse_traslados(el_impuestos: etree._Element | None) -> list[Traslado]:
    return _parse_impuestos(el_impuestos, "Traslado", Traslado)


def _parse_retenciones(el_impuestos: etree._Element | None) -> list[Retencion]:
    return _parse_impuestos(el_impuestos, "Retencion", Retencion)


def parse_comprobante_desde_raiz(path: Path, root: etree._Element) -> Comprobante:
    version = root.get("Version")
    match (etree.QName(root).localname, version):
        case ("Comprobante", "4.0"):
            pass
        case _:
            raise UnsupportedVersionError(
                path, f"solo se soporta CFDI 4.0 (se recibió '{version}')"
            )

    emisor = root.find("cfdi:Emisor", NSMAP)
    receptor = root.find("cfdi:Receptor", NSMAP)
    tfd = root.find("cfdi:Complemento/tfd:TimbreFiscalDigital", NSMAP)
    complemento = root.find("cfdi:Complemento", NSMAP)
    conceptos_el = root.findall("cfdi:Conceptos/cfdi:Concepto", NSMAP)

    return Comprobante(
        ruta=path,
        version=version,
        serie=root.get("Serie"),
        folio=root.get("Folio"),
        fecha=_fecha(root.get("Fecha")) or datetime.min,
        forma_pago=root.get("FormaPago"),
        metodo_pago=root.get("MetodoPago"),
        tipo_comprobante=root.get("TipoDeComprobante", ""),
        exportacion=root.get("Exportacion"),
        moneda=root.get("Moneda", ""),
        tipo_cambio=_dec(root.get("TipoCambio")),
        subtotal=_dec(root.get("SubTotal")) or Decimal(0),
        descuento=_dec(root.get("Descuento")),
        total=_dec(root.get("Total")) or Decimal(0),
        lugar_expedicion=root.get("LugarExpedicion"),
        emisor_rfc=emisor.get("Rfc", "") if emisor is not None else "",
        emisor_nombre=emisor.get("Nombre") if emisor is not None else None,
        emisor_regimen_fiscal=emisor.get("RegimenFiscal") if emisor is not None else None,
        receptor_rfc=receptor.get("Rfc", "") if receptor is not None else "",
        receptor_nombre=receptor.get("Nombre") if receptor is not None else None,
        receptor_uso_cfdi=receptor.get("UsoCFDI") if receptor is not None else None,
        receptor_regimen_fiscal=(
            receptor.get("RegimenFiscalReceptor") if receptor is not None else None
        ),
        receptor_domicilio_fiscal=(
            receptor.get("DomicilioFiscalReceptor") if receptor is not None else None
        ),
        uuid=tfd.get("UUID") if tfd is not None else None,
        fecha_timbrado=_fecha(tfd.get("FechaTimbrado")) if tfd is not None else None,
        rfc_pac=tfd.get("RfcProvCertif") if tfd is not None else None,
        no_certificado_sat=tfd.get("NoCertificadoSAT") if tfd is not None else None,
        no_certificado_emisor=root.get("NoCertificado"),
        conceptos=[el.get("Descripcion", "") for el in conceptos_el],
        complementos=sorted(
            {etree.QName(el).localname for el in complemento} if complemento is not None else []
        ),
        traslados=_parse_traslados(root.find("cfdi:Impuestos", NSMAP)),
        retenciones=_parse_retenciones(root.find("cfdi:Impuestos", NSMAP)),
        tipo_relacion=_primero(
            root.xpath("cfdi:CfdiRelacionados/@TipoRelacion", namespaces=NSMAP)
        ),
        relaciones=root.xpath("cfdi:CfdiRelacionados/cfdi:Relacionado/@UUID", namespaces=NSMAP),
    )


def parse_comprobante(ruta: str | Path) -> Comprobante:
    """Parsea un archivo XML de CFDI 4.0 y devuelve su modelo tipado."""
    path = Path(ruta)
    tree = cargar_arbol(path)
    return parse_comprobante_desde_raiz(path, tree.getroot())


def parse_comprobante_con_arbol(ruta: str | Path) -> tuple[Comprobante, etree._ElementTree]:
    """Parsea una sola vez y devuelve (comprobante, árbol) para reutilizar.

    Evita el doble I/O que hacían parse_pagos/parse_nomina al releer el archivo.
    """
    path = Path(ruta)
    tree = cargar_arbol(path)
    return parse_comprobante_desde_raiz(path, tree.getroot()), tree


def _primero(valores: list[str]) -> str | None:  # compat: ahora en _common
    from conxml.cfdi._common import primero

    return primero(valores)