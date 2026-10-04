"""Cliente del WebService oficial de descarga masiva de CFDI del SAT.

Las credenciales se cargan para cada operación y permanecen solo en memoria.
El historial guarda únicamente filtros, estados e identificadores del SAT.
"""
from __future__ import annotations

import base64
import binascii
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

import requests
from lxml import etree

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
WSA_NS = "http://schemas.microsoft.com/ws/2005/05/addressing/none"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
SAT_NS = "http://DescargaMasivaTerceros.sat.gob.mx"
SAT_AUTH_NS = "http://DescargaMasivaTerceros.gob.mx"
EXC_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
XML_C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA1 = f"{DS_NS}rsa-sha1"
SHA1 = f"{DS_NS}sha1"

ENDPOINT_AUTH = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc"
ENDPOINT_SOLICITUD = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc"
ENDPOINT_VERIFICACION = "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc"
ENDPOINT_DESCARGA = "https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc"
ACTION_AUTH = "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica"
ACTION_SOLICITUD = f"{SAT_NS}/ISolicitaDescargaService/SolicitaDescarga"
ACTION_VERIFICACION = f"{SAT_NS}/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
ACTION_DESCARGA = f"{SAT_NS}/IDescargaMasivaTercerosService/Descargar"
_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


class ErrorDescargaSAT(RuntimeError):
    """Error legible al consumir el servicio SAT."""


@dataclass
class CredencialEFirma:
    certificado: Any
    llave: Any
    certificado_der: bytes
    rfc: str

    @classmethod
    def cargar(cls, ruta_cer: str | Path, ruta_key: str | Path, contrasena: str) -> "CredencialEFirma":
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
        except ImportError as exc:  # pragma: no cover - depende de instalación
            raise ErrorDescargaSAT("Falta instalar la dependencia cryptography. Reinstala ConXml actualizado.") from exc

        try:
            cer_bytes = Path(ruta_cer).read_bytes()
            key_bytes = Path(ruta_key).read_bytes()
        except OSError as exc:
            raise ErrorDescargaSAT("No se pudo leer el certificado .cer o la llave privada .key seleccionados.") from exc
        try:
            certificado = x509.load_pem_x509_certificate(cer_bytes) if cer_bytes.startswith(b"-----BEGIN") else x509.load_der_x509_certificate(cer_bytes)
            llave = serialization.load_pem_private_key(
                key_bytes, password=contrasena.encode("utf-8") or None,
            ) if key_bytes.startswith(b"-----BEGIN") else serialization.load_der_private_key(
                key_bytes, password=contrasena.encode("utf-8") or None,
            )
        except (ValueError, TypeError) as exc:
            raise ErrorDescargaSAT("No se pudo abrir la e.firma. Revisa los archivos y la contraseña de la llave .key.") from exc
        if not isinstance(llave, rsa.RSAPrivateKey):
            raise ErrorDescargaSAT("La llave de e.firma no es RSA y el WebService del SAT no la acepta.")
        if not isinstance(certificado.public_key(), rsa.RSAPublicKey) or certificado.public_key().public_numbers() != llave.public_key().public_numbers():
            raise ErrorDescargaSAT("El certificado .cer y la llave .key no pertenecen al mismo par de e.firma.")
        ahora = datetime.now(timezone.utc)
        if certificado.not_valid_before_utc > ahora or certificado.not_valid_after_utc < ahora:
            raise ErrorDescargaSAT("El certificado de e.firma está vencido o aún no es válido.")
        try:
            rfc = certificado.subject.get_attributes_for_oid(x509.NameOID.SERIAL_NUMBER)[0].value.split("/")[0].strip().upper()
        except (IndexError, AttributeError):
            rfc = ""
        if not rfc:
            raise ErrorDescargaSAT("El certificado no incluye un RFC que ConXml pueda validar.")
        der = certificado.public_bytes(serialization.Encoding.DER)
        return cls(certificado, llave, der, rfc)


@dataclass
class RespuestaSAT:
    id_solicitud: str = ""
    cod_estatus: str = ""
    mensaje: str = ""
    estado: int | None = None
    numero_cfdis: int = 0
    paquetes: list[str] = field(default_factory=list)


@dataclass
class FiltroDescarga:
    rfc: str
    direccion: str
    fecha_inicial: date
    fecha_final: date
    tipo_comprobante: str = ""

    def validar(self) -> None:
        self.rfc = self.rfc.strip().upper()
        if not re.fullmatch(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}", self.rfc):
            raise ErrorDescargaSAT("El RFC del cliente no tiene un formato válido.")
        if self.direccion not in {"Emitidos", "Recibidos"}:
            raise ErrorDescargaSAT("Selecciona Emitidos o Recibidos.")
        if self.fecha_final < self.fecha_inicial:
            raise ErrorDescargaSAT("La fecha final debe ser igual o posterior a la inicial.")
        if self.tipo_comprobante not in {"", "I", "E", "T", "N", "P"}:
            raise ErrorDescargaSAT("El tipo de comprobante no es válido.")


class ClienteDescargaSAT:
    """Autentica, solicita, verifica y recupera paquetes desde el SAT."""

    def __init__(self, fiel: CredencialEFirma, session: requests.Session | None = None, timeout: float = 40.0):
        self.fiel = fiel
        self.session = session or requests.Session()
        self._sesion_propia = session is None
        self.timeout = timeout

    def cerrar(self) -> None:
        if self._sesion_propia:
            self.session.close()

    def autenticar(self) -> str:
        envelope = self._envelope_autenticacion()
        respuesta = self._post(ENDPOINT_AUTH, ACTION_AUTH, envelope)
        valor = _buscar_texto(respuesta, "AutenticaResult") or _buscar_texto(respuesta, "Token")
        if not valor:
            raise ErrorDescargaSAT(_mensaje_fault(respuesta) or "El SAT no devolvió un token de autenticación.")
        return valor.strip()

    def solicitar(self, filtro: FiltroDescarga) -> RespuestaSAT:
        filtro.validar()
        if self.fiel.rfc and filtro.rfc != self.fiel.rfc:
            raise ErrorDescargaSAT(f"El RFC de la e.firma ({self.fiel.rfc}) no coincide con el cliente ({filtro.rfc}).")
        token = self.autenticar()
        root = etree.Element(f"{{{SAT_NS}}}SolicitaDescarga", nsmap={"des": SAT_NS})
        attrs = {
            "FechaInicial": _fecha_sat(filtro.fecha_inicial, inicio=True),
            "FechaFinal": _fecha_sat(filtro.fecha_final, inicio=False),
            "RfcSolicitante": filtro.rfc,
            "TipoSolicitud": "CFDI",
        }
        if filtro.direccion == "Emitidos":
            attrs["RfcEmisor"] = filtro.rfc
        solicitud = etree.SubElement(root, f"{{{SAT_NS}}}solicitud", attrib=attrs)
        if filtro.direccion == "Recibidos":
            receptores = etree.SubElement(solicitud, f"{{{SAT_NS}}}RfcReceptores")
            etree.SubElement(receptores, f"{{{SAT_NS}}}RfcReceptor").text = filtro.rfc
        if filtro.tipo_comprobante:
            solicitud.set("TipoComprobante", filtro.tipo_comprobante)
        _firmar_peticion(solicitud, self.fiel)
        soap = _envolver(root)
        respuesta = self._post(ENDPOINT_SOLICITUD, ACTION_SOLICITUD, soap, token)
        return RespuestaSAT(
            id_solicitud=_buscar_texto(respuesta, "IdSolicitud"),
            cod_estatus=_buscar_texto(respuesta, "CodEstatus"),
            mensaje=_buscar_texto(respuesta, "Mensaje"),
        )

    def verificar(self, rfc: str, id_solicitud: str) -> RespuestaSAT:
        token = self.autenticar()
        root = etree.Element(f"{{{SAT_NS}}}VerificaSolicitudDescarga", nsmap={"des": SAT_NS})
        solicitud = etree.SubElement(root, f"{{{SAT_NS}}}solicitud", IdSolicitud=id_solicitud, RfcSolicitante=rfc.upper())
        _firmar_peticion(solicitud, self.fiel)
        respuesta = self._post(ENDPOINT_VERIFICACION, ACTION_VERIFICACION, _envolver(root), token)
        estado = _buscar_texto(respuesta, "EstadoSolicitud")
        paquetes = [
            _texto(el) for el in respuesta.iter()
            if etree.QName(el).localname.casefold() in {"idsPaquete".casefold(), "idpaquete"}
            and _texto(el)
        ]
        for contenedor in respuesta.iter():
            if etree.QName(contenedor).localname.casefold() == "idspaquetes":
                paquetes.extend(_texto(hijo) for hijo in contenedor if _texto(hijo))
        paquetes = list(dict.fromkeys(paquetes))
        return RespuestaSAT(
            id_solicitud=id_solicitud,
            cod_estatus=_buscar_texto(respuesta, "CodEstatus"),
            mensaje=_buscar_texto(respuesta, "Mensaje"),
            estado=int(estado) if estado.isdigit() else None,
            numero_cfdis=_entero(_buscar_texto(respuesta, "NumeroCFDIs")),
            paquetes=paquetes,
        )

    def descargar_paquete(self, rfc: str, id_paquete: str) -> bytes:
        token = self.autenticar()
        root = etree.Element(f"{{{SAT_NS}}}PeticionDescargaMasivaTercerosEntrada", nsmap={"des": SAT_NS})
        peticion = etree.SubElement(root, f"{{{SAT_NS}}}peticionDescarga", IdPaquete=id_paquete, RfcSolicitante=rfc.upper())
        _firmar_peticion(peticion, self.fiel)
        respuesta = self._post(ENDPOINT_DESCARGA, ACTION_DESCARGA, _envolver(root), token)
        contenido = _buscar_texto(respuesta, "Paquete") or _buscar_texto(respuesta, "PaqueteB64")
        if not contenido:
            raise ErrorDescargaSAT(_mensaje_fault(respuesta) or "El SAT no devolvió el archivo ZIP del paquete.")
        try:
            return base64.b64decode("".join(contenido.split()), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ErrorDescargaSAT("El paquete recibido del SAT no contiene Base64 válido.") from exc

    def _post(self, url: str, action: str, xml: bytes, token: str | None = None) -> etree._Element:
        headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{action}"', "User-Agent": "ConXml/0.1"}
        if token:
            headers["Authorization"] = f'WRAP access_token="{token}"'
        try:
            response = self.session.post(url, data=xml, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            root = etree.fromstring(response.content, parser=_XML_PARSER)
        except requests.RequestException as exc:
            raise ErrorDescargaSAT(f"No fue posible comunicarse con el WebService del SAT: {exc}") from exc
        except etree.XMLSyntaxError as exc:
            raise ErrorDescargaSAT("El SAT respondió con contenido XML que no se pudo interpretar.") from exc
        fault = _mensaje_fault(root)
        if fault:
            raise ErrorDescargaSAT(f"El SAT rechazó la operación: {fault}")
        return root

    def _envelope_autenticacion(self) -> bytes:
        now = datetime.now(timezone.utc)
        ident = "_conxml_timestamp"
        envelope = etree.Element(f"{{{SOAP_NS}}}Envelope", nsmap={"s": SOAP_NS, "o": WSSE_NS, "u": WSU_NS, "a": WSA_NS})
        header = etree.SubElement(envelope, f"{{{SOAP_NS}}}Header")
        etree.SubElement(header, f"{{{WSA_NS}}}Action", attrib={f"{{{SOAP_NS}}}mustUnderstand": "1"}).text = ACTION_AUTH
        etree.SubElement(header, f"{{{WSA_NS}}}To", attrib={f"{{{SOAP_NS}}}mustUnderstand": "1"}).text = ENDPOINT_AUTH
        security = etree.SubElement(header, f"{{{WSSE_NS}}}Security", attrib={f"{{{SOAP_NS}}}mustUnderstand": "1"})
        timestamp = etree.SubElement(security, f"{{{WSU_NS}}}Timestamp", attrib={f"{{{WSU_NS}}}Id": ident})
        created = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        etree.SubElement(timestamp, f"{{{WSU_NS}}}Created").text = created
        etree.SubElement(timestamp, f"{{{WSU_NS}}}Expires").text = (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        bst_id = "conxml_certificate"
        bst = etree.SubElement(security, f"{{{WSSE_NS}}}BinarySecurityToken", attrib={
            f"{{{WSU_NS}}}Id": bst_id,
            "ValueType": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3",
            "EncodingType": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary",
        })
        bst.text = base64.b64encode(self.fiel.certificado_der).decode("ascii")
        firma = _firmar_timestamp(timestamp, self.fiel, ident, bst_id)
        security.append(firma)
        body = etree.SubElement(envelope, f"{{{SOAP_NS}}}Body")
        etree.SubElement(body, f"{{{SAT_AUTH_NS}}}Autentica")
        return etree.tostring(envelope, encoding="utf-8", xml_declaration=True)


def guardar_paquete_zip(contenido: bytes, destino: str | Path) -> list[Path]:
    """Extrae solo XML, rechazando ZIPs corruptos y rutas inseguras."""
    destino = Path(destino).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    extraidos: list[Path] = []
    bytes_totales = 0
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as archivo_zip:
            for entrada in archivo_zip.infolist():
                if entrada.is_dir() or Path(entrada.filename).suffix.lower() != ".xml":
                    continue
                nombre = PurePosixPath(entrada.filename.replace("\\", "/")).name
                if not nombre or nombre in {".", ".."}:
                    continue
                bytes_totales += entrada.file_size
                if entrada.file_size > 250 * 1024 * 1024 or bytes_totales > 2 * 1024 * 1024 * 1024:
                    raise ErrorDescargaSAT("El ZIP excede el tamaño permitido para extraer XML.")
                salida = (destino / nombre).resolve()
                if destino not in salida.parents:
                    continue
                with archivo_zip.open(entrada) as origen, salida.open("wb") as archivo_salida:
                    archivo_salida.write(origen.read())
                extraidos.append(salida)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ErrorDescargaSAT("El paquete ZIP descargado está dañado o no se pudo extraer.") from exc
    return extraidos


def _envolver(contenido: etree._Element) -> bytes:
    envelope = etree.Element(f"{{{SOAP_NS}}}Envelope", nsmap={"s": SOAP_NS})
    body = etree.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    body.append(contenido)
    return etree.tostring(envelope, encoding="utf-8", xml_declaration=True)


def _firmar_peticion(elemento: etree._Element, fiel: CredencialEFirma) -> None:
    ds = f"{{{DS_NS}}}"
    firma = etree.SubElement(elemento, f"{ds}Signature", nsmap={None: DS_NS})
    signed_info = etree.SubElement(firma, f"{ds}SignedInfo")
    etree.SubElement(signed_info, f"{ds}CanonicalizationMethod", Algorithm=XML_C14N)
    etree.SubElement(signed_info, f"{ds}SignatureMethod", Algorithm=RSA_SHA1)
    referencia = etree.SubElement(signed_info, f"{ds}Reference", URI="")
    transforms = etree.SubElement(referencia, f"{ds}Transforms")
    etree.SubElement(transforms, f"{ds}Transform", Algorithm=f"{DS_NS}enveloped-signature")
    etree.SubElement(referencia, f"{ds}DigestMethod", Algorithm=SHA1)
    etree.SubElement(referencia, f"{ds}DigestValue")
    # Referencia URI vacía del protocolo SAT: firma el nodo solicitud sin su ds:Signature.
    sin_firma = etree.fromstring(etree.tostring(elemento), parser=_XML_PARSER)
    for nodo in sin_firma.xpath(".//ds:Signature", namespaces={"ds": DS_NS}):
        nodo.getparent().remove(nodo)
    digest = base64.b64encode(__import__("hashlib").sha1(etree.tostring(sin_firma, method="c14n")).digest()).decode("ascii")
    referencia.find(f"{ds}DigestValue").text = digest
    signature_value = etree.SubElement(firma, f"{ds}SignatureValue")
    signed = etree.tostring(signed_info, method="c14n")
    signature_value.text = base64.b64encode(fiel.llave.sign(signed, __import__("cryptography.hazmat.primitives.asymmetric.padding", fromlist=["PKCS1v15"]).PKCS1v15(), __import__("cryptography.hazmat.primitives.hashes", fromlist=["SHA1"]).SHA1())).decode("ascii")
    key_info = etree.SubElement(firma, f"{ds}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{ds}X509Data")
    issuer_serial = etree.SubElement(x509_data, f"{ds}X509IssuerSerial")
    etree.SubElement(issuer_serial, f"{ds}X509IssuerName").text = fiel.certificado.issuer.rfc4514_string()
    etree.SubElement(issuer_serial, f"{ds}X509SerialNumber").text = str(fiel.certificado.serial_number)
    etree.SubElement(x509_data, f"{ds}X509Certificate").text = base64.b64encode(fiel.certificado_der).decode("ascii")


def _firmar_timestamp(timestamp: etree._Element, fiel: CredencialEFirma, ident: str, bst_id: str) -> etree._Element:
    ds = f"{{{DS_NS}}}"
    firma = etree.Element(f"{ds}Signature", nsmap={None: DS_NS})
    signed_info = etree.SubElement(firma, f"{ds}SignedInfo")
    etree.SubElement(signed_info, f"{ds}CanonicalizationMethod", Algorithm=EXC_C14N)
    etree.SubElement(signed_info, f"{ds}SignatureMethod", Algorithm=RSA_SHA1)
    referencia = etree.SubElement(signed_info, f"{ds}Reference", URI=f"#{ident}")
    transforms = etree.SubElement(referencia, f"{ds}Transforms")
    etree.SubElement(transforms, f"{ds}Transform", Algorithm=EXC_C14N)
    etree.SubElement(referencia, f"{ds}DigestMethod", Algorithm=SHA1)
    etree.SubElement(referencia, f"{ds}DigestValue").text = base64.b64encode(__import__("hashlib").sha1(etree.tostring(timestamp, method="c14n", exclusive=True)).digest()).decode("ascii")
    etree.SubElement(firma, f"{ds}SignatureValue").text = base64.b64encode(fiel.llave.sign(etree.tostring(signed_info, method="c14n", exclusive=True), __import__("cryptography.hazmat.primitives.asymmetric.padding", fromlist=["PKCS1v15"]).PKCS1v15(), __import__("cryptography.hazmat.primitives.hashes", fromlist=["SHA1"]).SHA1())).decode("ascii")
    key_info = etree.SubElement(firma, f"{ds}KeyInfo")
    str_ref = etree.SubElement(key_info, f"{{{WSSE_NS}}}SecurityTokenReference", nsmap={"o": WSSE_NS})
    etree.SubElement(str_ref, f"{{{WSSE_NS}}}Reference", URI=f"#{bst_id}", ValueType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3")
    return firma


def _buscar_texto(root: etree._Element, nombre: str) -> str:
    for elemento in root.iter():
        if etree.QName(elemento).localname.casefold() == nombre.casefold():
            return _texto(elemento) or next(
                (valor for clave, valor in elemento.attrib.items()
                 if etree.QName(clave).localname.casefold() == nombre.casefold()),
                "",
            )
        for clave, valor in elemento.attrib.items():
            if etree.QName(clave).localname.casefold() == nombre.casefold():
                return valor.strip()
    return ""


def _texto(elemento: etree._Element) -> str:
    return "".join(elemento.itertext()).strip()


def _mensaje_fault(root: etree._Element) -> str:
    for elemento in root.iter():
        if etree.QName(elemento).localname.casefold() == "fault":
            return " ".join(_texto(hijo) for hijo in elemento if _texto(hijo))
    return ""


def _fecha_sat(valor: date, *, inicio: bool) -> str:
    hora = "00:00:00" if inicio else "23:59:59"
    return f"{valor.isoformat()}T{hora}"


def _entero(valor: str) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0
