"""Contraseña de e.firma en el almacén seguro del sistema, separada de los datos."""
from __future__ import annotations

import hashlib
import sys

from conxml.config import Config
from conxml.sat.boveda_firma import archivos_guardados, guardar_archivos
from conxml.sat.descarga_masiva import CredencialEFirma, ErrorDescargaSAT


def _almacen():
    # Seleccionar explícitamente un backend nativo evita alternativas en texto plano.
    try:
        if sys.platform == 'darwin':
            from keyring.backends.macOS import Keyring
        elif sys.platform == 'win32':
            from keyring.backends.Windows import WinVaultKeyring as Keyring
        else:
            from keyring.backends.SecretService import Keyring
        return Keyring()
    except Exception as exc:
        raise ErrorDescargaSAT('No está disponible el almacén seguro de contraseñas del sistema.') from exc


def servicio(config: Config) -> str:
    identificador = hashlib.sha256(str(config.base).encode()).hexdigest()[:16]
    return f'ConXml.SAT.{identificador}'


def autorizar(config: Config, cliente: str, rfc: str, cer: str, key: str, password: str) -> None:
    fiel = CredencialEFirma.cargar(cer, key, password)
    if fiel.rfc != rfc:
        raise ErrorDescargaSAT('La e.firma no corresponde al cliente seleccionado.')
    guardar_archivos(config, cliente, cer, key)
    try:
        _almacen().set_password(servicio(config), cliente, password)
    except Exception as exc:
        raise ErrorDescargaSAT('No se pudo guardar la autorización en el almacén seguro del sistema.') from exc


def cargar_firma(config: Config, cliente: str, rfc: str) -> CredencialEFirma:
    archivos = archivos_guardados(config, cliente)
    if not archivos:
        raise ErrorDescargaSAT('Autoriza la e.firma de este cliente en Descargas SAT.')
    try:
        password = _almacen().get_password(servicio(config), cliente)
    except Exception as exc:
        raise ErrorDescargaSAT('No se pudo abrir el almacén seguro; inicia sesión en el equipo y autoriza la e.firma.') from exc
    if not password:
        raise ErrorDescargaSAT('Falta autorizar la e.firma para las descargas periódicas.')
    fiel = CredencialEFirma.cargar(*archivos, password)
    if fiel.rfc != rfc:
        raise ErrorDescargaSAT('El RFC del cliente cambió; vuelve a autorizar su e.firma.')
    return fiel


def revocar(config: Config, cliente: str) -> None:
    from keyring.errors import PasswordDeleteError
    try:
        _almacen().delete_password(servicio(config), cliente)
    except PasswordDeleteError:
        pass
