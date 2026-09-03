"""Modelos de datos de CFDI 4.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path


@dataclass(slots=True)
class Impuesto:
    """Base de Traslado/Retencion (antes dos clases idénticas)."""

    base: Decimal | None
    impuesto: str
    tipo_factor: str
    tasa_o_cuota: Decimal | None
    importe: Decimal | None


@dataclass(slots=True)
class Traslado(Impuesto):
    pass


@dataclass(slots=True)
class Retencion(Impuesto):
    pass


@dataclass(slots=True)
class Comprobante:
    ruta: Path
    version: str
    serie: str | None
    folio: str | None
    fecha: datetime
    forma_pago: str | None
    metodo_pago: str | None
    tipo_comprobante: str
    exportacion: str | None
    moneda: str
    tipo_cambio: Decimal | None
    subtotal: Decimal
    descuento: Decimal | None
    total: Decimal
    emisor_rfc: str
    emisor_nombre: str | None
    emisor_regimen_fiscal: str | None
    receptor_rfc: str
    receptor_nombre: str | None
    receptor_uso_cfdi: str | None
    uuid: str | None
    fecha_timbrado: datetime | None
    rfc_pac: str | None
    lugar_expedicion: str | None = None
    traslados: list[Traslado] = field(default_factory=list)
    retenciones: list[Retencion] = field(default_factory=list)
    tipo_relacion: str | None = None
    relaciones: list[str] = field(default_factory=list)
    receptor_regimen_fiscal: str | None = None
    receptor_domicilio_fiscal: str | None = None
    no_certificado_sat: str | None = None
    no_certificado_emisor: str | None = None
    conceptos: list[str] = field(default_factory=list)
    complementos: list[str] = field(default_factory=list)

    @classmethod
    def from_xml(cls, ruta: str | Path) -> "Comprobante":
        from conxml.cfdi.parser import parse_comprobante

        return parse_comprobante(ruta)

    @property
    def iva(self) -> Decimal:
        return sum(
            (t.importe for t in self.traslados if t.impuesto == "002" and t.importe is not None),
            Decimal(0),
        )