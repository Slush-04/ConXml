"""Parser de CFDI 4.0 basado en lxml.

Solo soporta la versión 4.0 del esquema cfdi; cualquier otro documento
(3.3, nómina como raíz, XML malformado) produce un error claro sin crash.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from conxml.cfdi.models import Comprobante, Retencion, Traslado

CFDI_NS = "http://www.sat.gob.mx/cfd/4"
TFD_NS = "http://www.sat.gob.mx/TimbreFiscalDigital"
NSMAP = {"cfdi": CFDI_NS, "tfd": TFD_NS}

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


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


def _parse_traslados(el_impuestos: etree._Element | None) -> list[Traslado]:
    if el_impuestos is None:
        return []
    return [
        Traslado(
            base=_dec(el.get("Base")),
            impuesto=el.get("Impuesto", ""),
            tipo_factor=el.get("TipoFactor", ""),
            tasa_o_cuota=_dec(el.get("TasaOCuota")),
            importe=_dec(el.get("Importe")),
        )
        for el in el_impuestos.xpath("cfdi:Traslados/cfdi:Traslado", namespaces=NSMAP)
    ]


def _parse_retenciones(el_impuestos: etree._Element | None) -> list[Retencion]:
    if el_impuestos is None:
        return []
    return [
        Retencion(
            base=_dec(el.get("Base")),
            impuesto=el.get("Impuesto", ""),
            tipo_factor=el.get("TipoFactor", ""),
            tasa_o_cuota=_dec(el.get("TasaOCuota")),
            importe=_dec(el.get("Importe")),
        )
        for el in el_impuestos.xpath("cfdi:Retenciones/cfdi:Retencion", namespaces=NSMAP)
    ]


def parse_comprobante(ruta: str | Path) -> Comprobante:
    """Parsea un archivo XML de CFDI 4.0 y devuelve su modelo tipado."""
    path = Path(ruta)
    try:
        tree = etree.parse(str(path), parser=_PARSER)
    except etree.XMLSyntaxError as exc:
        raise CFDIParseError(path, f"no es un XML válido: {exc}") from exc

    root = tree.getroot()
    version = root.get("Version")
    if etree.QName(root).localname != "Comprobante" or version != "4.0":
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


def _primero(valores: list[str]) -> str | None:
    return valores[0] if valores else None