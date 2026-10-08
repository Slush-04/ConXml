"""Contrato SOAP y firmas sobre los bytes enviados, sin credenciales reales ni red."""
import base64
import hashlib
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from conxml.sat.descarga_masiva import (
    ACTION_AUTH, DS_NS, EXC_C14N, SAT_AUTH_NS, SAT_NS, SOAP_NS, WSSE_NS, WSU_NS,
    ClienteDescargaSAT, CredencialEFirma, ErrorDescargaSAT, FiltroDescarga,
)


@pytest.fixture(scope="module")
def fiel():
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "Prueba")])
    ahora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre)
            .public_key(llave.public_key()).serial_number(1)
            .not_valid_before(ahora-timedelta(days=1)).not_valid_after(ahora+timedelta(days=1))
            .sign(llave, hashes.SHA256()))
    return CredencialEFirma(cert, llave, cert.public_bytes(serialization.Encoding.DER), "EKU9003173C9")


def verificar_firma(root, fiel):
    firma = root.find(f".//{{{DS_NS}}}Signature")
    info = firma.find(f"{{{DS_NS}}}SignedInfo")
    assert info.find(f"{{{DS_NS}}}CanonicalizationMethod").get("Algorithm") == EXC_C14N
    fiel.llave.public_key().verify(
        base64.b64decode(firma.findtext(f"{{{DS_NS}}}SignatureValue")),
        etree.tostring(info, method="c14n", exclusive=True), padding.PKCS1v15(), hashes.SHA1(),
    )
    return firma


def test_autenticacion_basic_http_sin_addressing_y_firma_valida(fiel):
    sat = ClienteDescargaSAT(fiel, session=SimpleNamespace())
    root = etree.fromstring(sat._envelope_autenticacion())
    header = root.find(f"{{{SOAP_NS}}}Header")
    assert [n.tag for n in header] == [f"{{{WSSE_NS}}}Security"]
    assert root.find(f"{{{SOAP_NS}}}Body/{{{SAT_AUTH_NS}}}Autentica") is not None
    firma = verificar_firma(root, fiel)
    timestamp = header.find(f".//{{{WSU_NS}}}Timestamp")
    ref = firma.find(f".//{{{DS_NS}}}Reference")
    assert ref.get("URI") == "#" + timestamp.get(f"{{{WSU_NS}}}Id")
    assert base64.b64decode(ref.findtext(f"{{{DS_NS}}}DigestValue")) == hashlib.sha1(
        etree.tostring(timestamp, method="c14n", exclusive=True)
    ).digest()


@pytest.mark.parametrize("operacion", ["Emitidos", "Recibidos", "Verificar", "Descargar"])
def test_operaciones_y_firma_del_contenedor_completo(fiel, operacion):
    capturado = {}
    sat = ClienteDescargaSAT(fiel, session=SimpleNamespace())
    sat.autenticar = lambda: "token-prueba"
    def post(url, action, xml, token):
        capturado.update(action=action, xml=xml, token=token)
        return etree.fromstring(b'<Respuesta IdSolicitud="SOL1" CodEstatus="5000" EstadoSolicitud="3"><IdsPaquetes>P1</IdsPaquetes><IdsPaquetes>P2</IdsPaquetes><Paquete>WklQ</Paquete></Respuesta>')
    sat._post = post
    if operacion in ("Emitidos", "Recibidos"):
        result = sat.solicitar(FiltroDescarga(fiel.rfc, operacion, date(2026, 9, 1), date(2026, 10, 7), "I"))
        assert result.id_solicitud == "SOL1"
        nombre = "SolicitaDescarga" + operacion
        assert capturado["action"] == f"{SAT_NS}/ISolicitaDescargaService/{nombre}"
    elif operacion == "Verificar":
        result = sat.verificar(fiel.rfc, "SOL1")
        assert result.paquetes == ["P1", "P2"]
        nombre = "VerificaSolicitudDescarga"
    else:
        assert sat.descargar_paquete(fiel.rfc, "P1") == b"ZIP"
        nombre = "PeticionDescargaMasivaTercerosEntrada"
    root = etree.fromstring(capturado["xml"])
    nodo = root.find(f"{{{SOAP_NS}}}Body/{{{SAT_NS}}}{nombre}")
    assert nodo is not None
    firma = verificar_firma(root, fiel)
    esperado = base64.b64decode(firma.findtext(f".//{{{DS_NS}}}DigestValue"))
    firma.getparent().remove(firma)
    assert esperado == hashlib.sha1(etree.tostring(nodo, method="c14n", exclusive=True)).digest()
    if operacion in ("Emitidos", "Recibidos"):
        solicitud = nodo[0]
        assert solicitud.get("FechaInicial") == "2026-09-01T00:00:00"
        assert solicitud.get("FechaFinal") == "2026-10-07T23:59:59"
        assert solicitud.get("TipoComprobante") == "I"
        atributo = "RfcEmisor" if operacion == "Emitidos" else "RfcReceptor"
        assert solicitud.get(atributo) == fiel.rfc
        assert not len(solicitud)
        if operacion == "Recibidos":
            assert solicitud.get("EstadoComprobante") == "Vigente"


@pytest.mark.parametrize("status,contenido,mensaje", [
    (500, b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><s:Fault><faultcode>s:Client</faultcode><faultstring>Firma invalida</faultstring></s:Fault></s:Body></s:Envelope>', "Firma invalida"),
    (400, b"", "HTTP 400"),
    (503, b"<html>Unavailable</html>", "HTTP 503"),
    (200, b"no es XML", "no se pudo interpretar"),
])
def test_errores_http_conservan_fault_soap(fiel, status, contenido, mensaje):
    response = requests.Response()
    response.status_code = status
    response._content = contenido
    sat = ClienteDescargaSAT(fiel, session=SimpleNamespace(post=lambda *a, **kw: response))
    with pytest.raises(ErrorDescargaSAT, match=mensaje):
        sat._post("https://example.invalid", ACTION_AUTH, b"<xml/>")


def test_autenticacion_envia_soapaction_y_lee_token(fiel):
    response = requests.Response()
    response.status_code = 200
    response._content = b'<AutenticaResponse><AutenticaResult>token-ficticio</AutenticaResult></AutenticaResponse>'
    def post(url, data, headers, timeout):
        assert headers["SOAPAction"] == f'"{ACTION_AUTH}"'
        assert "Authorization" not in headers
        return response
    sat = ClienteDescargaSAT(fiel, session=SimpleNamespace(post=post))
    assert sat.autenticar() == "token-ficticio"
