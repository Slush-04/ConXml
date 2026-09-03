"""Utilidades compartidas de parseo CFDI (lxml seguro + conversiones).

Centraliza lo que antes estaba triplicado en parser/pagos/nomina/soap:
el ``XMLParser`` anti-XXE y los helpers ``_dec/_fecha/_int``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:  # solo para tipado, sin costo en runtime
    from conxml.cfdi.parser import CFDIParseError as _CFDIParseError

CFDI_NS = "http://www.sat.gob.mx/cfd/4"
TFD_NS = "http://www.sat.gob.mx/TimbreFiscalDigital"
NSMAP = {"cfdi": CFDI_NS, "tfd": TFD_NS}

PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def dec(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def fecha(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def entero(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def primero(valores: list[str]) -> str | None:
    return valores[0] if valores else None


def cargar_arbol(ruta: str | Path):
    """Parsea el XML una sola vez con parser seguro. Lanza CFDIParseError."""
    from conxml.cfdi.parser import CFDIParseError

    path = Path(ruta)
    try:
        with path.open("rb") as fh:
            return etree.parse(fh, parser=PARSER)
    except etree.XMLSyntaxError as exc:
        raise CFDIParseError(path, f"no es un XML válido: {exc}") from exc
    except OSError as exc:
        raise CFDIParseError(path, f"no se pudo leer: {exc}") from exc


# Aliases de compatibilidad (los módulos viejos importaban estos privados).
_dec = dec
_fecha = fecha
_int = entero
_primero = primero
_PARSER = PARSER

__all__ = [
    "CFDI_NS",
    "TFD_NS",
    "NSMAP",
    "PARSER",
    "_PARSER",
    "dec",
    "_dec",
    "fecha",
    "_fecha",
    "entero",
    "_int",
    "primero",
    "_primero",
    "cargar_arbol",
]
