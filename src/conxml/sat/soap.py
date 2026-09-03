"""Cliente SOAP del ConsultaCFDIService público del SAT (sin e.firma).

El servicio se consulta con una "expresión impresa" que concatena RFC
emisor, receptor, total y UUID. La respuesta se parsea por nombre local
para ser inmune a cambios de namespace.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from xml.sax.saxutils import escape as _sax_escape

import requests
from lxml import etree

from conxml.cfdi._common import PARSER as _PARSER

URL = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"
SOAP_ACTION = "http://tempuri.org/IConsultaCFDIService/Consulta"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
USER_AGENT = "conxml/1.0 (+gestor CFDI local)"


@dataclass
class ResultadoEstatus:
    estado: str
    codigo_estatus: str | None = None
    es_cancelable: str | None = None
    estatus_cancelacion: str | None = None

    @property
    def es_vigente(self) -> bool:
        return self.estado == "Vigente"

    @property
    def es_cancelado(self) -> bool:
        return self.estado == "Cancelado"


def _envelope(expresion: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap:Envelope xmlns:soap="{NS_SOAP}">'
        "<soap:Body>"
        '<Consulta xmlns="http://tempuri.org/">'
        f"<expresionImpresa>{expresion}</expresionImpresa>"
        "</Consulta>"
        "</soap:Body>"
        "</soap:Envelope>"
    )


def _xml_escape(valor: str) -> str:
    return _sax_escape(valor, entities={'"': "&quot;", "'": "&apos;"})


def _parse_respuesta(xml_texto: str | bytes) -> ResultadoEstatus:
    if isinstance(xml_texto, str):
        xml_texto = xml_texto.encode("utf-8")
    root = etree.fromstring(xml_texto, parser=_PARSER)
    valores: dict[str, str] = {}
    fault = None
    for el in root.iter():
        nombre = etree.QName(el).localname
        if nombre in {"Estado", "CodigoEstatus", "EsCancelable", "EstatusCancelacion"}:
            valores[nombre] = (el.text or "").strip()
        elif nombre in {"Fault", "faultstring", "faultcode"} and el.text:
            fault = (el.text or "").strip()

    estado_raw = valores.get("Estado", "").strip()
    if not estado_raw:
        return ResultadoEstatus(estado="Desconocido", codigo_estatus=fault or None)
    return ResultadoEstatus(
        estado=estado_raw,
        codigo_estatus=valores.get("CodigoEstatus"),
        es_cancelable=valores.get("EsCancelable"),
        estatus_cancelacion=valores.get("EstatusCancelacion"),
    )


def consultar(
    uuid: str,
    rfc_emisor: str,
    rfc_receptor: str,
    total: Decimal | str,
    timeout: float = 15.0,
    session: requests.Session | None = None,
) -> ResultadoEstatus:
    """Consulta el estatus de un CFDI ante el servicio público del SAT."""
    expresion = f"?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}"
    sesion = session or requests.Session()
    sesion_propia = session is None
    try:
        respuesta = sesion.post(
            URL,
            data=_envelope(_xml_escape(expresion)).encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": SOAP_ACTION,
                "User-Agent": USER_AGENT,
            },
            timeout=timeout,
        )
        respuesta.raise_for_status()
        return _parse_respuesta(respuesta.content)
    finally:
        if sesion_propia:
            sesion.close()