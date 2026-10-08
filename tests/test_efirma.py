from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from conxml.sat.descarga_masiva import CredencialEFirma, ErrorDescargaSAT


@pytest.fixture(scope="module")
def llave():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def guardar_efirma(tmp_path, llave, identificador, serial, encoding=serialization.Encoding.DER):
    atributos = [x509.NameAttribute(x509.NameOID.COMMON_NAME, "Certificado de prueba")]
    for oid, valor in (("2.5.4.45", identificador), ("2.5.4.5", serial)):
        if valor is not None:
            atributos.append(x509.NameAttribute(x509.ObjectIdentifier(oid), valor))
    nombre = x509.Name(atributos)
    ahora = datetime.now(timezone.utc)
    certificado = (
        x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre)
        .public_key(llave.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=1)).sign(llave, hashes.SHA256())
    )
    cer, key = tmp_path / "prueba.cer", tmp_path / "prueba.key"
    cer.write_bytes(certificado.public_bytes(encoding))
    key.write_bytes(llave.private_bytes(
        encoding, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"prueba"),
    ))
    return cer, key


@pytest.mark.parametrize("encoding", [serialization.Encoding.DER, serialization.Encoding.PEM])
@pytest.mark.parametrize("identificador,serial,esperado", [
    ("EKU9003173C9 / COSC8001137NA", " / COSC800113HDFRRN09", "EKU9003173C9"),
    ("COSC8001137NA", "COSC800113HDFRRN09", "COSC8001137NA"),
    (" eku9003173c9 ", "COSC8001137NA", "EKU9003173C9"),
    (None, "EKU9003173C9 / COSC8001137NA", "EKU9003173C9"),
])
def test_carga_rfc_del_titular(tmp_path, llave, identificador, serial, esperado, encoding):
    cer, key = guardar_efirma(tmp_path, llave, identificador, serial, encoding)
    assert CredencialEFirma.cargar(cer, key, "prueba").rfc == esperado


@pytest.mark.parametrize("identificador,serial", [
    (None, None), (None, "COSC800113HDFRRN09"),
    (" / COSC8001137NA", "COSC8001137NA"),
    ("INVALIDO", "COSC8001137NA"),
])
def test_rechaza_identidad_invalida_sin_usar_representante(tmp_path, llave, identificador, serial):
    cer, key = guardar_efirma(tmp_path, llave, identificador, serial)
    with pytest.raises(ErrorDescargaSAT, match="no incluye un RFC"):
        CredencialEFirma.cargar(cer, key, "prueba")


def test_contrasena_incorrecta_conserva_error_legible(tmp_path, llave):
    cer, key = guardar_efirma(tmp_path, llave, "EKU9003173C9", None)
    with pytest.raises(ErrorDescargaSAT, match="contraseña de la llave"):
        CredencialEFirma.cargar(cer, key, "incorrecta")
