"""Tests del cliente SOAP con respuestas simuladas (sin red)."""

import pytest
import requests

from conxml.sat.soap import ResultadoEstatus, _parse_respuesta, consultar

RESPUESTA_VIGENTE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <ConsultaResponse xmlns="http://tempuri.org/">
      <ConsultaResult xmlns:a="http://schemas.datacontract.org/2004/07/ConsultaCFDI">
        <a:Estado>Vigente</a:Estado>
        <a:CodigoEstatus>500</a:CodigoEstatus>
        <a:EsCancelable>No cancelable</a:EsCancelable>
        <a:EstatusCancelacion>0</a:EstatusCancelacion>
      </ConsultaResult>
    </ConsultaResponse>
  </s:Body>
</s:Envelope>"""

RESPUESTA_CANCELADO = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <ConsultaResponse xmlns="http://tempuri.org/">
      <ConsultaResult>
        <a:Estado xmlns:a="http://schemas.datacontract.org/2004/07/ConsultaCFDI">Cancelado</a:Estado>
        <a:CodigoEstatus xmlns:a="http://schemas.datacontract.org/2004/07/ConsultaCFDI">202</a:CodigoEstatus>
        <a:EsCancelable xmlns:a="http://schemas.datacontract.org/2004/07/ConsultaCFDI">Cancelado sin aceptación</a:EsCancelable>
      </ConsultaResult>
    </ConsultaResponse>
  </s:Body>
</s:Envelope>"""

RESPUESTA_NO_ENCONTRADO = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <ConsultaResponse xmlns="http://tempuri.org/">
      <ConsultaResult>
        <a:Estado xmlns:a="http://schemas.datacontract.org/2004/07/ConsultaCFDI">No Encontrado</a:Estado>
      </ConsultaResult>
    </ConsultaResponse>
  </s:Body>
</s:Envelope>"""

RESPUESTA_DESCONOCIDA = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <ConsultaResponse xmlns="http://tempuri.org/">
      <ConsultaResult><a:Estado xmlns:a="x">Raro nuevo</a:Estado></ConsultaResult>
    </ConsultaResponse>
  </s:Body>
</s:Envelope>"""

RESPUESTA_VACIA = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <ConsultaResponse xmlns="http://tempuri.org/">
      <ConsultaResult><a:Estado xmlns:a="x"></a:Estado></ConsultaResult>
    </ConsultaResponse>
  </s:Body>
</s:Envelope>"""


class RespuestaFalsa:
    def __init__(self, texto: str, status: int = 200):
        self.text = texto
        self.status_code = status

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_parse_vigente():
    r = _parse_respuesta(RESPUESTA_VIGENTE)
    assert r.estado == "Vigente"
    assert r.codigo_estatus == "500"
    assert r.es_cancelable == "No cancelable"
    assert r.es_vigente
    assert not r.es_cancelado


def test_parse_cancelado():
    r = _parse_respuesta(RESPUESTA_CANCELADO)
    assert r.estado == "Cancelado"
    assert r.es_cancelado
    assert not r.es_vigente


def test_parse_no_encontrado():
    assert _parse_respuesta(RESPUESTA_NO_ENCONTRADO).estado == "No Encontrado"


def test_parse_estado_desconocido_se_mapea():
    assert _parse_respuesta(RESPUESTA_DESCONOCIDA).estado == "Raro nuevo"


def test_parse_sin_estado_devuelve_desconocido():
    assert _parse_respuesta(RESPUESTA_VACIA).estado == "Desconocido"


def test_consultar_construye_peticion_correcta(monkeypatch):
    """Verifica URL, SOAPAction y la expresión impresa enviada."""
    capturados = {}

    def post_falso(self, url, data, headers, timeout):
        capturados["url"] = url
        capturados["headers"] = headers
        capturados["data"] = data.decode("utf-8")
        capturados["timeout"] = timeout
        return RespuestaFalsa(RESPUESTA_VIGENTE)

    monkeypatch.setattr(requests.Session, "post", post_falso)

    r = consultar(
        uuid="123E4567-E89B-12D3-A456-426614174000",
        rfc_emisor="EKU9003173C9",
        rfc_receptor="XAXX010101000",
        total="1160.00",
    )

    assert r.estado == "Vigente"
    assert capturados["url"] == "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"
    assert capturados["headers"]["SOAPAction"] == "http://tempuri.org/IConsultaCFDIService/Consulta"
    assert capturados["timeout"] == 15
    assert "?re=EKU9003173C9&amp;rr=XAXX010101000&amp;tt=1160.00&amp;id=123E4567-E89B-12D3-A456-426614174000" in capturados["data"]


def test_consultar_http_error_propaga(monkeypatch):
    def post_falso(self, url, data, headers, timeout):
        return RespuestaFalsa("error", status=500)

    monkeypatch.setattr(requests.Session, "post", post_falso)

    with pytest.raises(requests.HTTPError):
        consultar(uuid="x", rfc_emisor="y", rfc_receptor="z", total="1")