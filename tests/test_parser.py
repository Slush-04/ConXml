from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from conxml.cfdi.parser import CFDIParseError, UnsupportedVersionError, parse_comprobante

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(nombre: str):
    return parse_comprobante(FIXTURES / nombre)


def test_ingreso_basico_con_iva():
    c = _parse("ingreso_iva.xml")

    assert c.version == "4.0"
    assert c.serie == "A"
    assert c.folio == "124"
    assert c.fecha == datetime(2024, 2, 1, 9, 15, 0)
    assert c.forma_pago == "03"
    assert c.metodo_pago == "PUE"
    assert c.tipo_comprobante == "I"
    assert c.moneda == "MXN"
    assert c.tipo_cambio is None
    assert c.subtotal == Decimal("1000.00")
    assert c.descuento is None
    assert c.total == Decimal("1160.00")
    assert c.emisor_rfc == "EKU9003173C9"
    assert c.emisor_nombre == "EMPRESA DE PRUEBA SA DE CV"
    assert c.receptor_rfc == "XAXX010101000"
    assert c.receptor_uso_cfdi == "G03"
    assert c.uuid == "123E4567-E89B-12D3-A456-426614174000"
    assert c.fecha_timbrado == datetime(2024, 2, 1, 9, 20, 0)
    assert c.rfc_pac == "SAT970701NX3"
    assert c.iva == Decimal("160.00")
    assert len(c.traslados) == 1
    assert c.traslados[0].importe == Decimal("160.00")
    assert c.retenciones == []
    assert c.tipo_relacion is None
    assert c.relaciones == []


def test_ingreso_sin_impuestos():
    c = _parse("ingreso_sin_iva.xml")

    assert c.total == Decimal("500.00")
    assert c.traslados == []
    assert c.retenciones == []
    assert c.iva == Decimal(0)


def test_ingreso_con_descuento():
    c = _parse("ingreso_descuento.xml")

    assert c.subtotal == Decimal("1000.00")
    assert c.descuento == Decimal("100.00")
    assert c.total == Decimal("1044.00")
    assert c.iva == Decimal("144.00")


def test_ingreso_traslados_multiples_y_retenciones():
    c = _parse("ingreso_traslados_mult.xml")

    assert c.moneda == "USD"
    assert c.tipo_cambio == Decimal("17.5000")
    assert c.metodo_pago == "PPD"
    assert len(c.traslados) == 2
    assert [t.impuesto for t in c.traslados] == ["002", "008"]
    assert [t.importe for t in c.traslados] == [Decimal("160.00"), Decimal("80.00")]
    assert c.iva == Decimal("160.00")
    assert len(c.retenciones) == 2
    assert [r.impuesto for r in c.retenciones] == ["001", "002"]
    assert [r.importe for r in c.retenciones] == [Decimal("100.00"), Decimal("106.67")]


def test_egreso_con_relaciones():
    c = _parse("egreso_nota_credito.xml")

    assert c.tipo_comprobante == "E"
    assert c.metodo_pago is None
    assert c.forma_pago is None
    assert c.tipo_relacion == "01"
    assert c.relaciones == [
        "123E4567-E89B-12D3-A456-426614174000",
        "5A6B7C8D-9E0F-4A1B-8C2D-3E4F5A6B7C8D",
    ]


def test_cfdi_33_rechazado_con_error_claro(tmp_path):
    xml33 = (
        '<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/3" '
        'Version="3.3" Fecha="2024-01-01T00:00:00" SubTotal="0" Total="0" '
        'TipoDeComprobante="I" LugarExpedicion="45000"/>'
    )
    archivo = tmp_path / "cfdi33.xml"
    archivo.write_text(xml33, encoding="utf-8")

    with pytest.raises(UnsupportedVersionError) as exc:
        parse_comprobante(archivo)
    assert "3.3" in str(exc.value)


def test_xml_malformado_genera_error_claro(tmp_path):
    archivo = tmp_path / "basura.xml"
    archivo.write_text("esto no es xml", encoding="utf-8")

    with pytest.raises(CFDIParseError):
        parse_comprobante(archivo)


def test_sin_timbre_es_tolerante(tmp_path):
    xml_sin_tfd = (
        '<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
        'Version="4.0" Fecha="2024-01-01T00:00:00" SubTotal="0" Total="0" '
        'TipoDeComprobante="I" Exportacion="01" LugarExpedicion="45000">'
        "<cfdi:Emisor Rfc='XAXX010101000'/><cfdi:Receptor Rfc='XAXX010101000'/>"
        "</cfdi:Comprobante>"
    )
    archivo = tmp_path / "sin_tfd.xml"
    archivo.write_text(xml_sin_tfd, encoding="utf-8")

    c = parse_comprobante(archivo)
    assert c.uuid is None
    assert c.fecha_timbrado is None
    assert c.traslados == []
    assert c.total == Decimal(0)