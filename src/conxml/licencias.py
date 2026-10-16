"""Verificador del protocolo de licencias v1, consumido por licensing_client.

Solo acepta claves públicas fijadas por el distribuidor. La clave privada y la
credencial del administrador permanecen en el servicio. No hace solicitudes de red.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import re
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class LicenseError(Exception):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Campo duplicado")
        result[key] = value
    return result


def _decode(value):
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError()
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if base64.urlsafe_b64encode(raw).decode().rstrip("=") != value:
        raise ValueError()
    return raw


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError()
    parsed = UUID(value)
    if str(parsed) != value or parsed.version != 4:
        raise ValueError()
    return value


@dataclass(frozen=True)
class LicenseLease:
    license_id: str
    device_id: str
    issued_at: int
    expires_at: int
    trial_expires_at: int
    status: str
    license_revision: int
    device_revision: int
    nonce: str

    def permits_use(self, trusted_now: int) -> bool:
        """El llamador mantiene el reloj anclado al servidor y evita retrocesos.

        Esta función no convierte el reloj local del equipo en una fuente fiable.
        Un bloqueo recibido se conserva aparte hasta recibir un desbloqueo nuevo.
        """
        return (type(trusted_now) is int and self.status == "trial"
                and self.issued_at <= trusted_now < self.expires_at)


def verify_lease(compact: str, trusted_keys: dict[str, bytes], *, device_id: str,
                 expected_nonce: str | None = None, minimum_license_revision: int = 0,
                 minimum_device_revision: int = 0) -> LicenseLease:
    """Valida firma, identidad y límites; no persiste ni concede acceso por sí sola.

    En respuestas de red hay que pasar el nonce generado para esa solicitud.
    Al cargar un permiso guardado se verifican las mismas claves públicas y se
    conservan las mayores revisiones previamente recibidas de esta identidad.
    """
    try:
        if not isinstance(compact, str) or len(compact) > 8192:
            raise ValueError()
        _uuid(device_id)
        if expected_nonce is not None:
            _uuid(expected_nonce)
        for revision in (minimum_license_revision, minimum_device_revision):
            if type(revision) is not int or revision < 0:
                raise ValueError()
        header_text, payload_text, signature_text = compact.split(".")
        header = json.loads(_decode(header_text), object_pairs_hook=_object)
        if (not isinstance(header, dict) or set(header) != {"alg", "typ", "kid"}
                or header["alg"] != "EdDSA" or header["typ"] != "JWT"
                or not isinstance(header["kid"], str)):
            raise ValueError()
        public = trusted_keys.get(header["kid"])
        if not isinstance(public, bytes) or len(public) != 32:
            raise ValueError()
        signature = _decode(signature_text)
        if len(signature) != 64:
            raise ValueError()
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, f"{header_text}.{payload_text}".encode("ascii"))
        payload = json.loads(_decode(payload_text), object_pairs_hook=_object)
        required = {"schema", "iss", "aud", "license_id", "device_id", "iat", "exp",
                    "trial_expires_at", "status", "license_revision", "device_revision", "nonce"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError()
        if (type(payload["schema"]) is not int or payload["schema"] != 1
                or payload["iss"] != "conxml-licensing" or payload["aud"] != "conxml"):
            raise ValueError()
        _uuid(payload["license_id"])
        _uuid(payload["device_id"])
        _uuid(payload["nonce"])
        if payload["device_id"] != device_id or (expected_nonce is not None and payload["nonce"] != expected_nonce):
            raise ValueError()
        for name in ("iat", "exp", "trial_expires_at", "license_revision", "device_revision"):
            if type(payload[name]) is not int or not 0 <= payload[name] <= 2**53 - 1:
                raise ValueError()
        if (payload["license_revision"] < minimum_license_revision
                or payload["device_revision"] < minimum_device_revision):
            raise ValueError()
        if payload["status"] == "trial":
            if not payload["iat"] < payload["exp"] <= min(payload["iat"] + 86400, payload["trial_expires_at"]):
                raise ValueError()
        elif payload["status"] in ("blocked", "revoked", "expired"):
            if payload["exp"] != payload["iat"]:
                raise ValueError()
        else:
            raise ValueError()
        return LicenseLease(payload["license_id"], payload["device_id"], payload["iat"],
                            payload["exp"], payload["trial_expires_at"], payload["status"],
                            payload["license_revision"], payload["device_revision"], payload["nonce"])
    except (ValueError, TypeError, KeyError, InvalidSignature, UnicodeError, AttributeError):
        raise LicenseError("El permiso de licencia no es válido o no corresponde a esta instalación.") from None
